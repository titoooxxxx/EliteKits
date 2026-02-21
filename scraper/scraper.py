"""
scraper.py — Scraper Playwright pour les catalogues Yupoo
Usage : python scraper.py [--catalog ID] [--headful] [--max-albums N]
"""
import asyncio
import json
import logging
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# Force UTF-8 on Windows (évite UnicodeEncodeError avec cp1252)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from playwright.async_api import async_playwright, Page, Browser, BrowserContext

# Ajouter le dossier parent au path pour les imports
sys.path.insert(0, str(Path(__file__).parent))
from config import CATALOGS, SCRAPER, RAW_DATA_FILE, LOGS_DIR

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOGS_DIR / "scraper.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("scraper")

# ── Sélecteurs Yupoo (ordre de priorité) ─────────────────────────────────────
# Yupoo peut changer ses classes CSS ; on essaie plusieurs sélecteurs
# ── Sélecteurs Yupoo (confirmés par diagnostic live) ─────────────────────────
# Structure réelle : <a class="album__main" title="NOM" href="/albums/ID?uid=1&...">
#                     <div class="album__imgwrap"><img src="...medium.jpeg"></div>
#                     <div class="album__title">NOM</div>
#                   </a>

ALBUM_CONTAINER_SELECTOR = "a.album__main"  # L'<a> EST le container

PHOTO_SELECTORS = [
    # data-src contient "big.jpeg" ou l'original — priorité maximale
    "img[data-src*='photo.yupoo.com']",
    "img[data-origin-src*='photo.yupoo.com']",
    # src standard après scroll + rendu JS
    "img[src*='photo.yupoo.com']",
]

PAGINATION_NEXT_SELECTORS = [
    "a[href*='page=']",
    ".pagination__item--next",
    ".next-page",
    "a.next",
]


# ── Helpers ───────────────────────────────────────────────────────────────────
async def random_delay(min_s: float = None, max_s: float = None):
    min_s = min_s or SCRAPER["delay_min"]
    max_s = max_s or SCRAPER["delay_max"]
    await asyncio.sleep(random.uniform(min_s, max_s))


def normalize_image_url(url: str) -> str:
    """Convertit les URLs relatives en URLs absolues Yupoo."""
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("http"):
        # Remplacer les tailles basses par des tailles plus grandes
        url = re.sub(r"/[sm]\/", "/b/", url)   # small/medium → big
        url = re.sub(r"_s\.(jpg|jpeg|png|webp)", r"_b.\1", url)
        return url
    return url


def extract_album_id(url: str) -> Optional[str]:
    """Extrait l'ID numérique d'une URL d'album Yupoo."""
    m = re.search(r"/albums/(\d+)", url)
    return m.group(1) if m else None


async def try_selector(page: Page, selectors: list, base: str = None) -> list:
    """Essaie une liste de sélecteurs et retourne les éléments du premier qui fonctionne."""
    context = page if not base else page.locator(base)
    for sel in selectors:
        try:
            els = await context.locator(sel).all()
            if els:
                log.debug(f"Sélecteur fonctionnel : {sel} → {len(els)} éléments")
                return els
        except Exception:
            continue
    return []


# ── Scraping d'un album (photos) ─────────────────────────────────────────────
async def scrape_album_photos(page: Page, album_url: str, max_images: int = None) -> list:
    """
    Récupère toutes les URLs d'images d'un album Yupoo.
    IMPORTANT : l'URL doit inclure les query params (uid=1&...) sinon 404.
    """
    photos = []
    seen   = set()
    retries = 0

    while retries < SCRAPER["max_retries"]:
        try:
            log.debug(f"  -> Album : {album_url}")
            # IMPORTANT : wait_until=domcontentloaded (networkidle bloque indéfiniment)
            await page.goto(album_url, timeout=SCRAPER["timeout"], wait_until="domcontentloaded")
            await asyncio.sleep(2.5)  # Laisser le JS s'exécuter

            # Scroll progressif pour déclencher le lazy loading
            await _scroll_page(page, steps=6)

            # Récupérer toutes les images et inspecter src + data-src
            # (approche confirmée par diagnostic : vérifier les deux attributs par élément)
            all_imgs = await page.locator("img").all()
            for el in all_imgs:
                src  = await el.get_attribute("src")  or ""
                dsrc = await el.get_attribute("data-src") or ""
                # Prendre data-src en priorité (qualité originale), sinon src
                raw = dsrc if "photo.yupoo.com" in dsrc else src
                if "photo.yupoo.com" not in raw:
                    continue
                url = normalize_image_url(raw)
                if not url or url in seen:
                    continue
                if _is_product_photo(url, page.url):
                    url_hq = _upgrade_photo_quality(url)
                    if url_hq not in seen:
                        seen.add(url_hq)
                        photos.append(url_hq)
                        if max_images and len(photos) >= max_images:
                            break

            if photos:
                break

            retries += 1
            if retries < SCRAPER["max_retries"]:
                await random_delay(2, 4)

        except Exception as e:
            retries += 1
            log.warning(f"  Erreur album (essai {retries}): {e}")
            if retries < SCRAPER["max_retries"]:
                await random_delay(3, 6)

    # Dédupliquer et trier (par photo_id pour garder un ordre cohérent)
    photos = list(dict.fromkeys(photos))  # préserve l'ordre, élimine les doublons
    log.debug(f"  -> {len(photos)} photos")
    return photos


def _is_product_photo(url: str, album_url: str) -> bool:
    """Vérifie si l'URL est une photo produit (pas une icône/logo/UI)."""
    # Exclure les thumbnails carrés et les petits logos
    if "/square." in url or "/small." in url:
        return False
    # Exclure les icônes de l'interface Yupoo
    if "s.yupoo.com" in url or "/icons/" in url or "logo" in url.lower():
        return False
    # Doit être du même compte que l'album
    # URL album : https://{user}.x.yupoo.com/... → extraire {user} avec regex
    try:
        m = re.match(r'https?://([^.]+)(?:\.[^.]+)?\.yupoo\.com', album_url)
        if m:
            album_user = m.group(1)
            if album_user and album_user not in url:
                return False
    except Exception:
        pass
    return True


def _upgrade_photo_quality(url: str) -> str:
    """Remplace la taille dans l'URL par la meilleure qualité disponible."""
    import re
    # big.jpeg > large.jpeg > medium.jpeg > small.jpeg
    # Remplacer les tailles basses par 'big'
    url = re.sub(r"/(small|medium|thumb|square)\.", "/big.", url)
    url = re.sub(r"/(small|medium|thumb|square)\.", "/big.", url)
    return url


async def _scroll_page(page: Page, steps: int = 4):
    """Scroll progressif pour déclencher le lazy loading.
    On re-calcule scrollHeight à chaque pas car il augmente avec le lazy loading."""
    try:
        for i in range(1, steps + 1):
            # Re-calculer la hauteur à chaque étape (augmente avec le lazy loading)
            height = await page.evaluate("document.body.scrollHeight")
            await page.evaluate(f"window.scrollTo(0, {int(height * i / steps)})")
            await asyncio.sleep(0.6)
        # Scroll jusqu'en bas pour charger les dernières images
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(0.5)
        await page.evaluate("window.scrollTo(0, 0)")
    except Exception:
        pass


# ── Scraping de la liste des albums ──────────────────────────────────────────
async def scrape_album_list(page: Page, catalog_url: str, max_albums: int = None) -> list:
    """
    Scrape tous les albums d'un catalogue Yupoo (gère la pagination).
    Retourne une liste de dicts : {title, url, cover_url, album_id}
    """
    albums = []
    page_num = 1
    seen_ids = set()

    while True:
        url = f"{catalog_url}?page={page_num}" if page_num > 1 else catalog_url
        log.info(f"  Page {page_num} : {url}")

        retries = 0
        page_albums = []

        while retries < SCRAPER["max_retries"]:
            try:
                await page.goto(url, timeout=SCRAPER["timeout"], wait_until="domcontentloaded")
                await asyncio.sleep(3)  # Laisser le JS s'exécuter (networkidle bloque)
                await _scroll_page(page, steps=2)

                # Tenter d'extraire depuis le JS (window.__data ou similaire)
                js_albums = await _try_extract_js_data(page, catalog_url)
                if js_albums:
                    page_albums = js_albums
                    log.info(f"  → {len(js_albums)} albums via JS data")
                    break

                # Sinon, parser le HTML
                page_albums = await _parse_albums_from_html(page, catalog_url)
                if page_albums:
                    log.info(f"  → {len(page_albums)} albums via HTML")
                    break

                retries += 1
                await random_delay(2, 4)

            except Exception as e:
                retries += 1
                log.warning(f"  Erreur page {page_num} (essai {retries}): {e}")
                if retries < SCRAPER["max_retries"]:
                    await random_delay(3, 6)

        # Filtrer les doublons
        new_albums = []
        for a in page_albums:
            aid = a.get("album_id") or a.get("url", "")
            if aid and aid not in seen_ids:
                seen_ids.add(aid)
                new_albums.append(a)

        albums.extend(new_albums)
        log.info(f"  Total accumulé : {len(albums)} albums")

        if max_albums and len(albums) >= max_albums:
            albums = albums[:max_albums]
            break

        # Vérifier si une page suivante existe
        has_next = await _has_next_page(page, page_num)
        if not has_next or not new_albums:
            break

        page_num += 1
        await random_delay()

    return albums


async def _try_extract_js_data(page: Page, base_url: str) -> list:
    """
    Tente d'extraire les données d'album depuis les objets JS de la page.
    Yupoo injecte parfois window.__data ou window.pageData.
    """
    albums = []
    try:
        data = await page.evaluate("""() => {
            const candidates = [
                window.__data, window.data, window.pageData,
                window.__INITIAL_STATE__, window.__NUXT__,
            ];
            for (const d of candidates) {
                if (d && typeof d === 'object') return JSON.stringify(d);
            }
            return null;
        }""")

        if not data:
            return []

        obj = json.loads(data)
        # Chercher une clé contenant des albums
        album_list = _find_key_recursive(obj, ["albums", "albumList", "list"])
        if not album_list or not isinstance(album_list, list):
            return []

        domain = "/".join(base_url.split("/")[:3])  # https://user.x.yupoo.com
        for item in album_list:
            if not isinstance(item, dict):
                continue
            title = item.get("name") or item.get("title") or item.get("albumName") or ""
            aid   = str(item.get("id") or item.get("albumId") or "")
            cover = item.get("coverPhoto", {}) or {}
            cover_url = cover.get("imgUrl") or cover.get("thumb") or ""
            if aid:
                albums.append({
                    "title":     title.strip(),
                    "url":       f"{domain}/albums/{aid}",
                    "album_id":  aid,
                    "cover_url": normalize_image_url(cover_url),
                })
    except Exception:
        pass

    return albums


def _find_key_recursive(obj, keys: list, depth: int = 0):
    """Cherche récursivement une clé dans un objet JSON imbriqué."""
    if depth > 5:
        return None
    if isinstance(obj, dict):
        for k in keys:
            if k in obj:
                return obj[k]
        for v in obj.values():
            result = _find_key_recursive(v, keys, depth + 1)
            if result:
                return result
    elif isinstance(obj, list) and obj and isinstance(obj[0], dict):
        # Peut-être la liste elle-même ?
        if any(k in obj[0] for k in ["id", "albumId", "name", "title"]):
            return obj
    return None


async def _parse_albums_from_html(page: Page, base_url: str) -> list:
    """
    Parse les albums depuis le HTML Yupoo.
    Structure confirmée : <a class="album__main" title="NOM" href="/albums/ID?uid=1&...">
    IMPORTANT : conserver les query params dans l'URL (nécessaires pour album detail)
    """
    albums = []
    domain = "/".join(base_url.split("/")[:3])  # https://user.x.yupoo.com

    # Sélecteur confirmé par diagnostic
    album_els = await page.locator(ALBUM_CONTAINER_SELECTOR).all()

    if not album_els:
        # Fallback : chercher toutes les <a> vers /albums/
        album_els = await page.locator("a[href*='/albums/']").all()

    seen_ids = set()
    for el in album_els:
        try:
            # URL — GARDER les query params (uid=1 requis pour le detail)
            href = await el.get_attribute("href") or ""
            if not re.search(r"/albums/\d+", href):
                continue
            full_url = href if href.startswith("http") else domain + href
            album_id = extract_album_id(full_url)

            if not album_id or album_id in seen_ids:
                continue
            seen_ids.add(album_id)

            # Titre — attribut title de la <a> (plus fiable que le texte)
            title = await el.get_attribute("title") or ""
            if not title:
                try:
                    title_el = el.locator(".album__title").first
                    title = (await title_el.inner_text()).strip()
                except Exception:
                    title = (await el.inner_text()).strip()[:60]

            # Image de couverture — src (pas data-src, déjà chargée)
            cover_url = ""
            try:
                img_el = el.locator("img").first
                cover_url = await img_el.get_attribute("src") or await img_el.get_attribute("data-src") or ""
                cover_url = normalize_image_url(cover_url)
                # Upgrader la qualité
                cover_url = _upgrade_photo_quality(cover_url)
            except Exception:
                pass

            albums.append({
                "title":     title.strip() or f"Album {album_id}",
                "url":       full_url,       # URL complète avec params
                "album_id":  album_id,
                "cover_url": cover_url,
            })

        except Exception as e:
            log.debug(f"  Erreur parsing album: {e}")
            continue

    return albums


async def _has_next_page(page: Page, current_page: int) -> bool:
    """
    Vérifie si une page suivante existe.
    Sur Yupoo : les liens de pagination ont href="/albums?page=N"
    """
    try:
        next_num = current_page + 1
        # Chercher un lien vers la page suivante
        links = await page.locator(f"a[href*='page={next_num}']").all()
        return len(links) > 0
    except Exception:
        return False


# ── Scraper principal ─────────────────────────────────────────────────────────
async def scrape_catalog(
    catalog: dict,
    context: BrowserContext,
    max_albums: int = None,
    max_images: int = None,
) -> dict:
    """
    Scrape un catalogue Yupoo complet.
    Retourne un dict avec les métadonnées du catalogue et la liste des albums.
    """
    log.info(f"\n{'='*60}")
    log.info(f"Scraping : {catalog['name']}")
    log.info(f"URL      : {catalog['url']}")
    log.info(f"{'='*60}")

    page = await context.new_page()
    result = {
        "catalog_id":   catalog["id"],
        "catalog_name": catalog["name"],
        "version":      catalog["version"],
        "price_eur":    catalog["price_eur"],
        "scraped_at":   datetime.now().isoformat(),
        "albums":       [],
    }

    try:
        # Récupérer la liste des albums
        albums = await scrape_album_list(page, catalog["url"], max_albums=max_albums)
        log.info(f"Albums trouvés : {len(albums)}")

        # Pour chaque album, récupérer les photos
        for i, album in enumerate(albums):
            log.info(f"  [{i+1}/{len(albums)}] {album['title'][:60]}")
            photos = await scrape_album_photos(page, album["url"], max_images=max_images)
            album["photos"] = photos
            album["photo_count"] = len(photos)

            # Utiliser la cover déjà récupérée si pas de photos
            if not photos and album.get("cover_url"):
                album["photos"] = [album["cover_url"]]
                album["photo_count"] = 1

            await random_delay()

        result["albums"] = albums
        log.info(f"[OK] {catalog['name']} : {len(albums)} albums scrapés")

    except Exception as e:
        log.error(f"[ERR] Erreur catalogue {catalog['name']}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await page.close()

    return result


async def run_scraper(
    catalog_ids: list = None,
    max_albums: int = None,
    max_images: int = None,
    headless: bool = True,
) -> dict:
    """
    Lance le scraper pour tous les catalogues (ou une sélection).
    Retourne les données brutes et les sauvegarde dans raw_catalog.json.
    """
    catalogs_to_scrape = CATALOGS
    if catalog_ids:
        catalogs_to_scrape = [c for c in CATALOGS if c["id"] in catalog_ids]

    all_data = {
        "scraped_at": datetime.now().isoformat(),
        "catalogs":   [],
    }

    async with async_playwright() as pw:
        browser: Browser = await pw.chromium.launch(
            headless=headless,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )

        context: BrowserContext = await browser.new_context(
            user_agent=SCRAPER["user_agent"],
            viewport=SCRAPER["viewport"],
            locale="fr-FR",
            timezone_id="Europe/Paris",
            # Masquer que c'est Playwright
            extra_http_headers={
                "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8,zh-CN;q=0.7",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )

        # Masquer les propriétés de détection de bot
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
        """)

        for catalog in catalogs_to_scrape:
            catalog_data = await scrape_catalog(
                catalog, context,
                max_albums=max_albums or SCRAPER.get("max_albums"),
                max_images=max_images or SCRAPER.get("max_images_per_album"),
            )
            all_data["catalogs"].append(catalog_data)

        await browser.close()

    # Sauvegarder les données brutes
    RAW_DATA_FILE.write_text(
        json.dumps(all_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log.info(f"\n[OK] Donnees brutes sauvegardees : {RAW_DATA_FILE}")

    total_albums = sum(len(c["albums"]) for c in all_data["catalogs"])
    log.info(f"[OK] Total : {total_albums} albums dans {len(all_data['catalogs'])} catalogues")

    return all_data


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="EliteKits — Scraper Yupoo")
    parser.add_argument(
        "--catalog", nargs="+",
        choices=[c["id"] for c in CATALOGS] + ["all"],
        default=["all"],
        help="Catalogue(s) à scraper (défaut: all)",
    )
    parser.add_argument(
        "--max-albums", type=int, default=None,
        help="Nombre max d'albums par catalogue (pour les tests)",
    )
    parser.add_argument(
        "--max-images", type=int, default=None,
        help="Nombre max d'images par album",
    )
    parser.add_argument(
        "--headful", action="store_true",
        help="Lancer le navigateur en mode visible (debug)",
    )
    parser.add_argument(
        "--test", action="store_true",
        help="Mode test : 5 albums max par catalogue",
    )
    args = parser.parse_args()

    catalog_ids = None if "all" in args.catalog else args.catalog
    max_albums  = 5 if args.test else args.max_albums

    log.info("EliteKits Scraper démarré")
    log.info(f"Catalogues : {catalog_ids or 'tous'}")
    log.info(f"Max albums : {max_albums or 'illimité'}")

    asyncio.run(run_scraper(
        catalog_ids=catalog_ids,
        max_albums=max_albums,
        max_images=args.max_images,
        headless=not args.headful,
    ))
