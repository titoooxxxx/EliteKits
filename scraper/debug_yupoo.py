"""
debug_yupoo.py — Diagnostic de la structure des pages Yupoo
Ouvre la page, dump le HTML et tente d'extraire les albums
"""
import asyncio, json, sys
from pathlib import Path
from playwright.async_api import async_playwright

URL = "https://hongpintiyu.x.yupoo.com/albums"
OUT = Path(__file__).parent / "data" / "debug_page.html"
(Path(__file__).parent / "data").mkdir(exist_ok=True)

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            locale="fr-FR",
        )
        page = await ctx.new_page()

        print(f"Navigation vers {URL} ...")
        try:
            # IMPORTANT: ne pas attendre networkidle, juste domcontentloaded
            await page.goto(URL, timeout=30000, wait_until="domcontentloaded")
            print("Page chargee (domcontentloaded)")
        except Exception as e:
            print(f"Erreur goto: {e}")
            await browser.close()
            return

        # Attendre 3 secondes que le JS s'execute
        await asyncio.sleep(3)
        print("Attente JS terminee")

        # Dump du HTML
        html = await page.content()
        out_html = Path(__file__).parent / "data" / "debug_page.html"
        out_html.write_text(html, encoding="utf-8")
        print(f"HTML sauvegarde : {out_html} ({len(html)} chars)")

        # Titre de la page
        title = await page.title()
        print(f"Titre : {title}")

        # Tenter d'extraire les albums avec plusieurs selecteurs
        selectors_to_try = [
            ".album__main",
            ".album",
            "[class*='album']",
            ".showalbumlist",
            "a[href*='/albums/']",
            ".p-item",
            "li",
            ".items",
            ".grid",
        ]

        print("\n--- Test des selecteurs ---")
        found_any = False
        for sel in selectors_to_try:
            try:
                els = await page.locator(sel).all()
                if els:
                    print(f"  [{sel}] : {len(els)} elements")
                    found_any = True
                    # Afficher le contenu du premier
                    first_html = await els[0].inner_html()
                    print(f"    Premier element (100 chars) : {first_html[:100].strip()}")
            except Exception as e:
                print(f"  [{sel}] : ERREUR {e}")

        if not found_any:
            print("  Aucun selecteur n'a trouve d'elements")

        # Chercher les liens vers /albums/XXXXXX
        print("\n--- Liens vers albums ---")
        album_links = await page.locator("a[href*='/albums/']").all()
        print(f"  {len(album_links)} liens trouves")
        for lnk in album_links[:5]:
            href  = await lnk.get_attribute("href") or ""
            text  = (await lnk.inner_text()).strip()[:60]
            print(f"  href={href}  |  text={text}")

        # Chercher des donnees JSON dans les scripts
        print("\n--- Donnees JSON dans les scripts ---")
        script_els = await page.locator("script").all()
        print(f"  {len(script_els)} balises <script>")
        for i, scr in enumerate(script_els[:20]):
            content = (await scr.inner_html())[:200].strip()
            if content and ("album" in content.lower() or "photo" in content.lower() or "__" in content):
                print(f"  script[{i}] (contient 'album'/'photo') : {content[:150]}")

        # Tenter d'extraire window.__data
        js_data = await page.evaluate("""() => {
            const keys = ['__data', 'data', 'pageData', '__INITIAL_STATE__', '__NUXT__', 'albumList'];
            for (const k of keys) {
                if (window[k]) return {key: k, data: JSON.stringify(window[k]).slice(0, 500)};
            }
            return null;
        }""")
        if js_data:
            print(f"\n--- window.{js_data['key']} ---")
            print(f"  {js_data['data']}")
        else:
            print("\n--- Aucune donnee window.X trouvee ---")

        # Screenshot pour debug visuel
        screenshot = Path(__file__).parent / "data" / "debug_screenshot.png"
        await page.screenshot(path=str(screenshot), full_page=False)
        print(f"\nScreenshot : {screenshot}")

        await browser.close()
        print("\nDiagnostic termine !")

asyncio.run(main())
