# EliteKits — Football Jersey E-Commerce

Premium football jersey e-commerce site with semantic search powered by Yupoo catalog scraping.

## Architecture

```
EliteKits/
├── index.html          — Homepage with search engine
├── fan.html            — Fan version jerseys
├── player.html         — Player version jerseys
├── retro.html          — Retro / vintage jerseys
├── kids.html           — Kids jerseys
├── products.json       — Search database (auto-generated)
├── _redirects          — Netlify API proxy config
├── css/                — Stylesheets
├── js/
│   └── script.js       — Search engine + cart logic
├── images/             — Local product images (3900+)
├── scraper/            — Yupoo scraper + search API
│   ├── config.py       — Catalog URLs, prices, settings
│   ├── scraper.py      — Playwright scraper for Yupoo
│   ├── team_extractor.py — 200+ team database + NLP extraction
│   ├── database_builder.py — Builds products.json + products.db
│   ├── search_engine.py — FastAPI search server (optional)
│   ├── update_catalog.py — Full pipeline orchestrator
│   └── requirements.txt — Python dependencies
└── server.py           — Flask order handler (SMTP)
```

## Quick Start

### 1. Install scraper dependencies

```bash
pip install -r scraper/requirements.txt
playwright install chromium
```

### 2. Run the full scrape (builds products.json)

```bash
# Full scrape of all 5 catalogs
python scraper/update_catalog.py

# Test mode (5 albums per catalog, ~5 min)
python scraper/update_catalog.py --test

# Rebuild database without re-scraping
python scraper/update_catalog.py --build-only
```

### 3. (Optional) Start the search API server

```bash
python scraper/search_engine.py
# Available at http://localhost:8001
# Admin panel: http://localhost:8001/admin (user: admin)
```

### 4. Start the order handler

```bash
# Set environment variables first
export SMTP_HOST=smtp.mail.yahoo.com
export SMTP_PORT=587
export SMTP_USER=your@yahoo.com
export SMTP_PASS=your_app_password
export SELLER_EMAIL=seller@example.com

python server.py
```

## Deployment (Netlify)

1. Push to GitHub
2. Connect to Netlify
3. Deploy settings:
   - Build command: *(none)*
   - Publish directory: `.`
4. Update `_redirects` with your Flask API URL:
   ```
   /api/*  https://your-flask-api.onrender.com/api/:splat  200
   ```

## Search Engine

The search is **semantic** — it matches by **team name**, never by color.

Priority order:
1. Exact team key match (`psg` → Paris Saint-Germain)
2. Alias exact match (Chinese: `皇马` → Real Madrid)
3. Fuzzy match (threshold 85%)
4. Token-based full-text fallback

Supported query modifiers:
- Type: `home`, `away`, `third`, `domicile`, `extérieur`, `主场`, `客场`
- Season: `2024`, `2024-25`, `24-25`
- Version: `fan`, `player`, `retro`

## Adding New Teams

In `scraper/team_extractor.py`, add to `TEAM_DATABASE`:

```python
"my team": {
    "canonical_name": "My Team FC",
    "short_name":     "My Team",
    "aliases":        ["my team", "mtfc", "中文名"],
    "league":         "Premier League",
    "country":        "England",
},
```

## Auto-update (cron)

```bash
# Daily at 3am
0 3 * * * cd /path/to/EliteKits && python scraper/update_catalog.py >> scraper/logs/cron.log 2>&1
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `SMTP_HOST` | SMTP server (e.g. smtp.mail.yahoo.com) |
| `SMTP_PORT` | SMTP port (465 for SSL) |
| `SMTP_USER` | SMTP username |
| `SMTP_PASS` | SMTP password / app password |
| `SELLER_EMAIL` | Email to receive orders |
| `FROM_EMAIL` | Sender email |
