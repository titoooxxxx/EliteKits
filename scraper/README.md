# EliteKits Scraper & Search Engine

Système complet de scraping, base de données et recherche pour les catalogues Yupoo.

## Architecture

```
scraper/
├── config.py           — Configuration (URLs, prix, paramètres)
├── scraper.py          — Scraper Playwright pour les catalogues Yupoo
├── team_extractor.py   — Base de données 200+ équipes + extraction NLP
├── database_builder.py — Construit products.json + products.db
├── search_engine.py    — API FastAPI de recherche
├── update_catalog.py   — Orchestrateur de mise à jour complète
├── data/               — Données générées (raw_catalog.json, products.db)
└── logs/               — Logs (scraper.log, api.log, update.log)
```

## Installation

```bash
# Depuis le dossier EliteKits/
pip install -r scraper/requirements.txt

# Installer les navigateurs Playwright
playwright install chromium
```

## Utilisation

### 1. Lancer la mise à jour complète (scraping + BDD)

```bash
# Tout scraper (tous les catalogues)
python scraper/update_catalog.py

# Test rapide (5 albums par catalogue)
python scraper/update_catalog.py --test

# Un seul catalogue
python scraper/update_catalog.py --catalog fan_hongpin

# Avec le navigateur visible (debug)
python scraper/update_catalog.py --headful

# Reconstruire la BDD sans re-scraper
python scraper/update_catalog.py --build-only
```

### 2. Lancer l'API de recherche

```bash
python scraper/search_engine.py
# Disponible sur http://localhost:8001

# Ou avec uvicorn (production)
uvicorn scraper.search_engine:app --host 0.0.0.0 --port 8001 --reload
```

#### Endpoints API

| Endpoint | Description |
|----------|-------------|
| `GET /api/search?q=PSG` | Recherche de maillots |
| `GET /api/search?q=PSG&version=fan` | Filtrer par version |
| `GET /api/search?q=france&country=France` | Filtrer par pays |
| `GET /api/suggest?q=par` | Autocomplete |
| `GET /api/teams` | Liste de toutes les équipes |
| `GET /api/filters` | Options de filtres disponibles |
| `GET /api/stats` | Statistiques de la base |
| `GET /admin` | Page d'administration (user: admin) |
| `GET /docs` | Documentation API interactive (Swagger) |

### 3. Page d'administration

Accéder à `http://localhost:8001/admin`
- Identifiant : `admin`
- Mot de passe : défini dans `config.py` → `API["admin_password"]`

### 4. Tester l'extraction des équipes

```bash
python scraper/team_extractor.py
```

## Intégration Frontend

### Option A — Client-side (static hosting)

Le `products.json` est chargé directement par `js/script.js`.
Aucun serveur supplémentaire requis.

### Option B — API FastAPI (recommandé)

1. Déployer `search_engine.py` sur votre hébergeur
2. Ajouter dans le HTML (avant le `</head>`) :
```html
<script>window.ELITEKITS_SEARCH_API = 'https://votre-api.onrender.com';</script>
```
3. L'autocomplete et la recherche utiliseront l'API serveur

## Configuration

Modifier `scraper/config.py` pour :
- Changer l'URL des catalogues Yupoo
- Modifier les prix
- Ajuster les délais du scraper
- Changer le mot de passe admin
- Configurer les origines CORS

## Format products.json

```json
[
  {
    "id": "fan_paris_saint_germ_2425_hom_0001",
    "team": "Paris Saint-Germain FC",
    "team_short": "PSG",
    "team_key": "paris saint-germain",
    "team_aliases": ["psg", "paris sg", "巴黎圣日耳曼"],
    "league": "Ligue 1",
    "country": "France",
    "season": "2024-25",
    "type": "Home",
    "version": "fan",
    "sleeve": "short",
    "price": 25,
    "currency": "EUR",
    "images": ["https://photo.yupoo.com/..."],
    "thumbnail": "https://photo.yupoo.com/...",
    "source_url": "https://hongpintiyu.x.yupoo.com/albums/12345",
    "tags": ["psg", "paris", "ligue 1", "france", "home", "2024-25"],
    "confidence_score": 0.98,
    "matched": true
  }
]
```

## Ajouter une nouvelle équipe

Dans `team_extractor.py`, ajouter dans `TEAM_DATABASE` :

```python
"mon equipe": {
    "canonical_name": "Mon Équipe FC",
    "short_name":     "Mon Équipe",
    "aliases":        ["mon equipe", "mef", "别名中文"],
    "league":         "Ligue X",
    "country":        "Pays",
},
```

## Automatisation (cron)

Pour une mise à jour quotidienne à 3h du matin :

```
# Windows Task Scheduler ou Linux cron
0 3 * * * cd /path/to/EliteKits && python scraper/update_catalog.py >> logs/cron.log 2>&1
```
