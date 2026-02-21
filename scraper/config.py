"""
config.py — Configuration centralisée pour EliteKits Scraper
"""
from pathlib import Path

# ── Répertoires ───────────────────────────────────────────────────────────────
ROOT_DIR    = Path(__file__).parent.parent       # EliteKits/
SCRAPER_DIR = Path(__file__).parent              # EliteKits/scraper/
DATA_DIR    = SCRAPER_DIR / "data"               # EliteKits/scraper/data/
LOGS_DIR    = SCRAPER_DIR / "logs"               # EliteKits/scraper/logs/

# Créer automatiquement les dossiers
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ── Fichiers de sortie ────────────────────────────────────────────────────────
RAW_DATA_FILE  = DATA_DIR / "raw_catalog.json"   # données brutes du scraping
PRODUCTS_JSON  = ROOT_DIR / "products.json"       # base de données produits (frontend)
PRODUCTS_DB    = DATA_DIR / "products.db"         # SQLite pour requêtes avancées
UNMATCHED_CSV  = DATA_DIR / "unmatched.csv"       # produits non identifiés
UPDATE_LOG     = LOGS_DIR / "update.log"

# ── Catalogues Yupoo ──────────────────────────────────────────────────────────
CATALOGS = [
    {
        "id":        "fan_hongpin",
        "name":      "Fan Version — HongPin",
        "url":       "https://hongpintiyu.x.yupoo.com/albums",
        "version":   "fan",
        "price_usd": 6,
        "price_eur": 25,
    },
    {
        "id":        "fan_tang",
        "name":      "Fan Version — Tang",
        "url":       "https://tang2075.x.yupoo.com/albums",
        "version":   "fan",
        "price_usd": 6,
        "price_eur": 25,
    },
    {
        "id":        "player",
        "name":      "Player Version",
        "url":       "https://baocheng3f888.x.yupoo.com/albums",
        "version":   "player",
        "price_usd": 8,
        "price_eur": 30,
    },
    {
        "id":        "retro",
        "name":      "Retro",
        "url":       "https://classic-football-fhirts052.x.yupoo.com/albums",
        "version":   "retro",
        "price_usd": 8,
        "price_eur": 30,
    },
    {
        "id":        "kit",
        "name":      "Kits Complets",
        "url":       "https://boshang668.x.yupoo.com/albums",
        "version":   "kit",
        "price_usd": 6,
        "price_eur": 25,
    },
]

# ── Prix en euros par type ────────────────────────────────────────────────────
PRICES_EUR = {
    "fan":         25,
    "player":      30,
    "player_long": 35,
    "retro":       30,
    "kit_adult":   25,
    "kit_enfant":  25,
}

# ── Paramètres Playwright ─────────────────────────────────────────────────────
SCRAPER = {
    "delay_min":    1.2,    # secondes min entre requêtes
    "delay_max":    2.8,    # secondes max entre requêtes
    "timeout":      30000,  # ms — timeout page
    "max_retries":  3,
    "headless":     True,
    "viewport":     {"width": 1280, "height": 800},
    "user_agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    # max d'albums par catalogue (None = tous)
    "max_albums": None,
    # max d'images par album (None = toutes)
    "max_images_per_album": None,
}

# ── API de recherche ──────────────────────────────────────────────────────────
API = {
    "host": "0.0.0.0",
    "port": 8001,
    # Mot de passe admin (changer en production !)
    "admin_password": "elitekits2024",
    # Origines CORS autorisées
    "cors_origins": [
        "http://localhost",
        "http://localhost:3000",
        "http://127.0.0.1:5500",
        "https://elitekits.netlify.app",
        # Ajouter l'URL Netlify réelle ici
    ],
}

# ── Seuils de confiance ───────────────────────────────────────────────────────
CONFIDENCE = {
    "min_score_exact":  100,   # score minimum pour considérer un match exact
    "min_score_fuzzy":   75,   # score minimum pour fuzzy match (sur 100)
    "log_unmatched":     True, # logger les produits sans match
}
