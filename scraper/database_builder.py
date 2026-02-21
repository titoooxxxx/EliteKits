"""
database_builder.py — Construit products.json et products.db depuis les données scrapées

Usage : python database_builder.py [--input raw_catalog.json] [--output products.json]
"""
import csv
import json
import logging
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Force UTF-8 on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    RAW_DATA_FILE, PRODUCTS_JSON, PRODUCTS_DB,
    UNMATCHED_CSV, PRICES_EUR, CONFIDENCE,
)
from team_extractor import extract_product_info

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("database_builder")


# ── Construction d'un produit depuis un album Yupoo ───────────────────────────
def build_product(album: dict, catalog: dict, product_index: int) -> dict:
    """
    Construit un objet produit structuré depuis les données d'un album Yupoo.
    """
    version   = catalog.get("version", "fan")
    title     = album.get("title", "")
    photos    = album.get("photos", [])
    cover_url = album.get("cover_url") or (photos[0] if photos else "")

    # Extraire les informations de l'équipe et du maillot
    info = extract_product_info(title, version)

    # Déterminer le prix selon la version et les manches
    price = _get_price(version, info.get("sleeve", "short"))

    # Construire un ID unique
    product_id = _build_id(version, product_index, info)

    # Construire les tags pour la recherche
    tags = _build_tags(info)

    return {
        "id":               product_id,
        # Équipe
        "team":             info["team"],
        "team_short":       info["team_short"],
        "team_key":         info.get("team_key"),
        "team_aliases":     info.get("team_aliases", []),
        "league":           info.get("league", ""),
        "country":          info.get("country", ""),
        # Maillot
        "season":           info.get("season", ""),
        "type":             info.get("type", "Unknown"),
        "version":          version,
        "sleeve":           info.get("sleeve", "short"),
        # Prix
        "price":            price,
        "currency":         "EUR",
        # Images
        "images":           photos[:10],     # max 10 images
        "thumbnail":        cover_url,
        # Source
        "source_url":       album.get("url", ""),
        "album_id":         album.get("album_id", ""),
        "catalog_id":       catalog.get("catalog_id", catalog.get("id", "")),
        "raw_title":        title,
        # Métadonnées
        "tags":             tags,
        "confidence_score": info.get("confidence", 0.0),
        "matched":          info.get("matched", False),
        "created_at":       datetime.now().isoformat(),
    }


def _get_price(version: str, sleeve: str) -> int:
    """Retourne le prix en euros selon la version et le type de manches."""
    if sleeve == "long":
        if version == "player":
            return PRICES_EUR.get("player_long", 35)
    return PRICES_EUR.get(version, 25)


def _build_id(version: str, index: int, info: dict) -> str:
    """Construit un ID unique et lisible pour le produit."""
    team_key = info.get("team_key") or "unknown"
    # Nettoyer le team_key pour l'URL
    clean_key = team_key.replace(" ", "_").replace("-", "_")[:20]
    season = info.get("season", "").replace("-", "")
    jersey_type = info.get("type", "")[:3].lower()
    return f"{version}_{clean_key}_{season}_{jersey_type}_{index:04d}"


def _build_tags(info: dict) -> list:
    """Construit la liste de tags pour la recherche."""
    tags = set()

    # Nom d'équipe et aliases
    if info.get("team_short"):
        tags.add(info["team_short"].lower())
    if info.get("team"):
        tags.update(info["team"].lower().split())
    for alias in info.get("team_aliases", []):
        # Éviter les caractères CJK dans les tags (gardés dans aliases mais pas les tags)
        if not _is_cjk(alias):
            tags.add(alias.lower())

    # Ligue et pays
    if info.get("league"):
        tags.add(info["league"].lower())
    if info.get("country"):
        tags.add(info["country"].lower())

    # Saison
    if info.get("season"):
        tags.add(info["season"])
        # Ajouter les années individuelles
        parts = re.split(r"[/-]", info["season"])
        for p in parts:
            if p.isdigit():
                tags.add(p)

    # Type
    if info.get("type") and info["type"] != "Unknown":
        tags.add(info["type"].lower())
        # Traductions
        type_map = {"Home": "domicile", "Away": "extérieur", "Third": "third"}
        fr = type_map.get(info["type"])
        if fr:
            tags.add(fr)

    # Version
    version_map = {"fan": "fan version", "player": "player version", "retro": "rétro", "kit": "kit complet"}
    tags.add(version_map.get(info.get("version", ""), info.get("version", "")))

    return sorted(t for t in tags if t and len(t) >= 2)


import re

def _is_cjk(text: str) -> bool:
    """Vérifie si une chaîne contient principalement des caractères CJK."""
    cjk_count = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    return cjk_count > len(text) * 0.3


# ── Construction de la base de données complète ────────────────────────────────
def build_database(
    raw_data: dict,
    output_json: Path = PRODUCTS_JSON,
    output_db: Path = PRODUCTS_DB,
    unmatched_csv: Path = UNMATCHED_CSV,
) -> list:
    """
    Construit products.json et products.db depuis les données brutes du scraper.
    Retourne la liste complète des produits.
    """
    products    = []
    unmatched   = []
    product_idx = 0

    for catalog in raw_data.get("catalogs", []):
        albums     = catalog.get("albums", [])
        log.info(f"\nTraitement : {catalog['catalog_name']} ({len(albums)} albums)")

        matched_count   = 0
        unmatched_count = 0

        for album in albums:
            product = build_product(album, catalog, product_idx)
            products.append(product)
            product_idx += 1

            if product["matched"]:
                matched_count += 1
                log.debug(f"  [OK] [{product['confidence_score']:.2f}] {album['title'][:50]} -> {product['team_short']}")
            else:
                unmatched_count += 1
                unmatched.append({
                    "catalog":    catalog["catalog_name"],
                    "title":      album.get("title", ""),
                    "url":        album.get("url", ""),
                    "confidence": product["confidence_score"],
                    "best_guess": product["team"],
                })
                log.warning(f"  [ERR] Non-matchée : {album.get('title', '')[:60]}")

        log.info(f"  -> {matched_count} matchées, {unmatched_count} non-matchées")

    # Trier par équipe puis saison
    products.sort(key=lambda p: (
        p.get("team", "ZZZ"),
        p.get("season", ""),
        p.get("version", ""),
    ))

    # ── Sauvegarder products.json ─────────────────────────────────────────────
    output_json.write_text(
        json.dumps(products, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log.info(f"\n[OK] products.json : {len(products)} produits -> {output_json}")

    # ── Sauvegarder products.db (SQLite) ──────────────────────────────────────
    _save_to_sqlite(products, output_db)
    log.info(f"[OK] products.db -> {output_db}")

    # ── Sauvegarder unmatched.csv ─────────────────────────────────────────────
    if unmatched and CONFIDENCE.get("log_unmatched"):
        with open(unmatched_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["catalog", "title", "url", "confidence", "best_guess"])
            writer.writeheader()
            writer.writerows(unmatched)
        log.info(f"[OK] unmatched.csv : {len(unmatched)} produits non-matchés -> {unmatched_csv}")

    # ── Stats ─────────────────────────────────────────────────────────────────
    total       = len(products)
    matched     = sum(1 for p in products if p["matched"])
    unmatched_n = total - matched
    log.info(f"\n{'='*50}")
    log.info(f"TOTAL     : {total} produits")
    log.info(f"Matchés   : {matched} ({matched/total*100:.1f}%)")
    log.info(f"Non-matchés: {unmatched_n} ({unmatched_n/total*100:.1f}%)")

    # Top équipes
    from collections import Counter
    team_counts = Counter(p["team_short"] for p in products if p["matched"])
    log.info("\nTop 10 équipes :")
    for team, count in team_counts.most_common(10):
        log.info(f"  {team:<25} {count} maillots")

    return products


def _save_to_sqlite(products: list, db_path: Path):
    """Sauvegarde les produits dans une base SQLite."""
    conn = sqlite3.connect(db_path)
    cur  = conn.cursor()

    # Créer la table
    cur.execute("DROP TABLE IF EXISTS products")
    cur.execute("""
        CREATE TABLE products (
            id              TEXT PRIMARY KEY,
            team            TEXT,
            team_short      TEXT,
            team_key        TEXT,
            league          TEXT,
            country         TEXT,
            season          TEXT,
            type            TEXT,
            version         TEXT,
            sleeve          TEXT,
            price           INTEGER,
            currency        TEXT,
            thumbnail       TEXT,
            images          TEXT,    -- JSON array
            source_url      TEXT,
            album_id        TEXT,
            catalog_id      TEXT,
            raw_title       TEXT,
            tags            TEXT,    -- JSON array
            confidence_score REAL,
            matched         INTEGER,
            created_at      TEXT
        )
    """)

    # Créer les index pour la recherche rapide
    cur.execute("CREATE INDEX IF NOT EXISTS idx_team    ON products (team_key)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_league  ON products (league)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_country ON products (country)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_season  ON products (season)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_version ON products (version)")

    # Insérer les produits
    rows = []
    for p in products:
        rows.append((
            p["id"],
            p["team"],
            p["team_short"],
            p.get("team_key"),
            p.get("league", ""),
            p.get("country", ""),
            p.get("season", ""),
            p.get("type", ""),
            p.get("version", ""),
            p.get("sleeve", "short"),
            p.get("price", 25),
            p.get("currency", "EUR"),
            p.get("thumbnail", ""),
            json.dumps(p.get("images", []), ensure_ascii=False),
            p.get("source_url", ""),
            p.get("album_id", ""),
            p.get("catalog_id", ""),
            p.get("raw_title", ""),
            json.dumps(p.get("tags", []), ensure_ascii=False),
            p.get("confidence_score", 0.0),
            1 if p.get("matched") else 0,
            p.get("created_at", ""),
        ))

    cur.executemany("""
        INSERT INTO products VALUES (
            ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
        )
    """, rows)

    conn.commit()
    conn.close()


def load_raw_data(path: Path = RAW_DATA_FILE) -> Optional[dict]:
    """Charge les données brutes du scraper."""
    if not path.exists():
        log.error(f"Fichier non trouvé : {path}")
        log.error("Lancez d'abord : python scraper.py")
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_products(path: Path = PRODUCTS_JSON) -> list:
    """Charge la base de données products.json."""
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="EliteKits — Database Builder")
    parser.add_argument("--input",  type=Path, default=RAW_DATA_FILE)
    parser.add_argument("--output", type=Path, default=PRODUCTS_JSON)
    args = parser.parse_args()

    log.info("Chargement des données brutes...")
    raw = load_raw_data(args.input)
    if not raw:
        sys.exit(1)

    total_albums = sum(len(c.get("albums", [])) for c in raw.get("catalogs", []))
    log.info(f"{total_albums} albums à traiter")

    build_database(raw, output_json=args.output)
