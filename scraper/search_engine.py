"""
search_engine.py — API de recherche FastAPI pour EliteKits

Usage : python search_engine.py
        ou : uvicorn search_engine:app --host 0.0.0.0 --port 8001 --reload

Endpoints :
  GET  /api/search?q=PSG&version=fan&country=France&page=1
  GET  /api/suggest?q=par
  GET  /api/teams
  GET  /api/filters
  GET  /api/product/{id}
  GET  /admin                    (mot de passe requis)
  GET  /admin/unmatched
  POST /admin/rescrape
  POST /admin/fix-team           (correction manuelle)
"""
import json
import logging
import os
import secrets
import sys
from collections import Counter
from pathlib import Path
from typing import Optional

# Force UTF-8 on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from rapidfuzz import fuzz, process

sys.path.insert(0, str(Path(__file__).parent))
from config import PRODUCTS_JSON, UNMATCHED_CSV, API, LOGS_DIR
from team_extractor import TEAM_DATABASE, _ALIAS_INDEX, normalize_text

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOGS_DIR / "api.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("search_engine")

# ── App FastAPI ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="EliteKits Search API",
    description="API de recherche pour les maillots de foot",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=API["cors_origins"] + ["*"],  # "*" pour dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBasic()

# ── Index en mémoire ──────────────────────────────────────────────────────────
class SearchIndex:
    """Index de recherche en mémoire chargé depuis products.json."""

    def __init__(self):
        self.products: list[dict] = []
        self.by_id: dict[str, dict] = {}
        self.teams: list[str] = []        # noms canoniques
        self.team_keys: list[str] = []    # clés normalisées
        self.leagues: list[str] = []
        self.countries: list[str] = []
        self.seasons: list[str] = []
        self.versions: list[str] = []
        self.loaded = False

    def load(self, path: Path = PRODUCTS_JSON) -> int:
        """Charge et indexe les produits depuis products.json."""
        if not path.exists():
            log.warning(f"products.json introuvable : {path}")
            return 0

        with open(path, encoding="utf-8") as f:
            self.products = json.load(f)

        self.by_id = {p["id"]: p for p in self.products}

        # Construire les listes pour les filtres et l'autocomplete
        teams_seen   = set()
        leagues_seen = set()
        countries_seen = set()
        seasons_seen = set()
        versions_seen = set()

        for p in self.products:
            if p.get("team_short") and p.get("matched"):
                teams_seen.add(p["team"])
            if p.get("league"):
                leagues_seen.add(p["league"])
            if p.get("country"):
                countries_seen.add(p["country"])
            if p.get("season"):
                seasons_seen.add(p["season"])
            if p.get("version"):
                versions_seen.add(p["version"])

        self.teams     = sorted(teams_seen)
        self.leagues   = sorted(leagues_seen)
        self.countries = sorted(countries_seen)
        self.seasons   = sorted(seasons_seen, reverse=True)
        self.versions  = sorted(versions_seen)
        self.loaded    = True

        log.info(f"Index chargé : {len(self.products)} produits, {len(self.teams)} équipes")
        return len(self.products)

    def reload(self):
        """Recharge l'index depuis le disque."""
        self.load()


# Instance globale de l'index
index = SearchIndex()


@app.on_event("startup")
async def startup():
    index.load()


# ── Logique de recherche ──────────────────────────────────────────────────────

def parse_query(q: str) -> dict:
    """
    Analyse une requête utilisateur et en extrait les composantes.
    Ex: "maillot extérieur real madrid 2024" → {team, type, season, raw}
    """
    q_lower = q.lower().strip()

    # Détecter les types de maillot dans la requête
    type_keywords = {
        "home": "Home", "domicile": "Home", "主场": "Home",
        "away": "Away", "extérieur": "Away", "exterieur": "Away", "客场": "Away",
        "third": "Third", "troisième": "Third",
        "retro": None,   # filtre version retro
        "vintage": None,
    }
    detected_type    = None
    detected_version = None
    for kw, jersey_type in type_keywords.items():
        if kw in q_lower:
            if jersey_type:
                detected_type = jersey_type
            else:
                detected_version = kw

    # Détecter une saison
    import re
    season_match = re.search(r"\b(20\d{2})[/-]?(\d{0,2})\b", q_lower)
    detected_season = season_match.group(0).replace("/", "-") if season_match else None

    # Construire la chaîne "équipe nettoyée"
    team_query = q_lower
    for kw in list(type_keywords.keys()) + ["maillot", "jersey", "shirt", "kit", "foot", "football", "soccer"]:
        team_query = team_query.replace(kw, " ")
    if detected_season:
        team_query = team_query.replace(detected_season, " ")
    team_query = " ".join(team_query.split())

    return {
        "raw":     q,
        "team":    team_query,
        "type":    detected_type,
        "version": detected_version,
        "season":  detected_season,
    }


def resolve_team_query(team_query: str) -> Optional[str]:
    """
    Résout une requête en clé d'équipe.
    Ordre : exact alias → fuzzy alias
    Retourne la team_key ou None.
    """
    if not team_query or len(team_query) < 2:
        return None

    # 1. Exact match
    q_lower = team_query.lower().strip()
    if q_lower in _ALIAS_INDEX:
        return _ALIAS_INDEX[q_lower]

    # 2. Chercher si la requête contient un alias connu
    q_norm = normalize_text(q_lower)
    best_key   = None
    best_score = 0

    for alias, team_key in _ALIAS_INDEX.items():
        # Autoriser alias CJK de 2 chars (ex: 皇马, 巴西) ; ignorer Latin < 3 chars
        if len(alias) < 2:
            continue
        if len(alias) == 2 and all(ord(c) < 0x4E00 for c in alias):
            continue
        alias_norm = normalize_text(alias)
        # L'alias est-il contenu dans la requête ? (ou inversement ?)
        if alias_norm in q_norm or q_norm in alias_norm:
            score = len(alias_norm)
            if score > best_score:
                best_score = score
                best_key   = team_key

    if best_key:
        return best_key

    # 3. Fuzzy match (seuil 85 pour éviter les faux positifs)
    result = process.extractOne(
        q_norm,
        list(_ALIAS_INDEX.keys()),
        scorer=fuzz.token_set_ratio,
        score_cutoff=85,
    )
    if result:
        matched_alias, score, _ = result
        return _ALIAS_INDEX[matched_alias]

    return None


def search_products(
    q: str,
    version: Optional[str] = None,
    country: Optional[str] = None,
    league: Optional[str] = None,
    season: Optional[str] = None,
    jersey_type: Optional[str] = None,
    page: int = 1,
    per_page: int = 60,
) -> dict:
    """
    Recherche principale.
    Priorité : exact team name > alias > fuzzy > tags > full-text
    JAMAIS de tri par couleur par défaut.
    """
    if not index.loaded:
        return {"results": [], "total": 0, "page": page, "query": q}

    results = index.products[:]  # copie

    # ── Filtres stricts (non-textuels) ────────────────────────────────────────
    if version:
        results = [p for p in results if p.get("version") == version]
    if country:
        c = country.lower()
        results = [p for p in results if c in (p.get("country") or "").lower()]
    if league:
        lg = league.lower()
        results = [p for p in results if lg in (p.get("league") or "").lower()]
    if season:
        results = [p for p in results if season in (p.get("season") or "")]
    if jersey_type:
        jt = jersey_type.lower()
        type_map = {"home": "Home", "away": "Away", "third": "Third"}
        jersey_type_canonical = type_map.get(jt, jersey_type.capitalize())
        results = [p for p in results if p.get("type") == jersey_type_canonical]

    # ── Recherche textuelle ───────────────────────────────────────────────────
    if q and q.strip():
        parsed    = parse_query(q)
        team_key  = resolve_team_query(parsed["team"])

        # Appliquer les filtres détectés dans la requête
        if parsed["type"]:
            results = [p for p in results if p.get("type") == parsed["type"]]
        if parsed["season"]:
            results = [p for p in results if parsed["season"] in (p.get("season") or "")]

        if team_key:
            # Match sur la clé d'équipe — tri par pertinence
            def score_product(p: dict) -> int:
                s = 0
                if p.get("team_key") == team_key:
                    s += 100
                # Booster les matchs haute confiance
                s += int(p.get("confidence_score", 0) * 20)
                # Booster par saison récente
                try:
                    yr = int((p.get("season") or "0")[:4])
                    s += max(0, yr - 2010)
                except ValueError:
                    pass
                return s

            results = [p for p in results if p.get("team_key") == team_key]
            results.sort(key=score_product, reverse=True)

        else:
            # Pas d'équipe trouvée : fallback sur full-text (tags, raw_title)
            q_tokens = set(normalize_text(q).split())
            if q_tokens:
                def text_score(p: dict) -> int:
                    s = 0
                    tags     = [normalize_text(t) for t in (p.get("tags") or [])]
                    raw      = normalize_text(p.get("raw_title") or "")
                    team_low = normalize_text(p.get("team") or "")

                    for token in q_tokens:
                        if len(token) < 2:
                            continue
                        if token in team_low:
                            s += 50
                        if any(token == tag for tag in tags):
                            s += 30
                        if any(token in tag for tag in tags):
                            s += 15
                        if token in raw:
                            s += 10
                    return s

                scored  = [(p, text_score(p)) for p in results]
                scored  = [(p, s) for p, s in scored if s > 0]
                scored.sort(key=lambda x: x[1], reverse=True)
                results = [p for p, _ in scored]

    # ── Pagination ────────────────────────────────────────────────────────────
    total      = len(results)
    start      = (page - 1) * per_page
    end        = start + per_page
    page_items = results[start:end]

    return {
        "results":    page_items,
        "total":      total,
        "page":       page,
        "per_page":   per_page,
        "total_pages": (total + per_page - 1) // per_page,
        "query":      q,
    }


# ── Endpoints API ─────────────────────────────────────────────────────────────

@app.get("/api/search")
async def api_search(
    q:       str = Query(default="", description="Requête de recherche"),
    version: Optional[str] = Query(default=None, description="fan|player|retro|kit"),
    country: Optional[str] = Query(default=None),
    league:  Optional[str] = Query(default=None),
    season:  Optional[str] = Query(default=None),
    type:    Optional[str] = Query(default=None, alias="type"),
    page:    int = Query(default=1, ge=1),
    limit:   int = Query(default=60, ge=1, le=200),
):
    """Recherche principale. Retourne les produits correspondants."""
    if not q and not version and not country and not league and not season:
        # Sans requête → retourner les derniers produits
        products = index.products[:limit]
        return {"results": products, "total": len(index.products), "page": 1, "query": ""}

    return search_products(q, version, country, league, season, type, page, limit)


@app.get("/api/suggest")
async def api_suggest(
    q: str = Query(..., min_length=1, description="Début de saisie"),
):
    """
    Autocomplete : retourne des suggestions d'équipes, ligues, saisons.
    Répond en < 50ms grâce à l'index en mémoire.
    """
    q_norm = normalize_text(q)
    suggestions = []
    seen = set()

    # 1. Équipes dont le nom ou alias commence par la requête
    for alias, team_key in _ALIAS_INDEX.items():
        if normalize_text(alias).startswith(q_norm) and team_key not in seen:
            team_data = TEAM_DATABASE.get(team_key, {})
            seen.add(team_key)
            suggestions.append({
                "type":    "team",
                "label":   team_data.get("canonical_name", team_key),
                "short":   team_data.get("short_name", ""),
                "league":  team_data.get("league", ""),
                "country": team_data.get("country", ""),
            })

    # 2. Équipes disponibles dans la base (contient q)
    for p in index.products:
        team_short = p.get("team_short", "")
        team_key   = p.get("team_key", "")
        if (
            team_key
            and team_key not in seen
            and q_norm in normalize_text(team_short)
        ):
            seen.add(team_key)
            suggestions.append({
                "type":    "team",
                "label":   p.get("team", team_short),
                "short":   team_short,
                "league":  p.get("league", ""),
                "country": p.get("country", ""),
            })

    # 3. Ligues
    for league in index.leagues:
        if q_norm in normalize_text(league) and league not in seen:
            seen.add(league)
            suggestions.append({"type": "league", "label": league})

    # 4. Pays
    for country in index.countries:
        if q_norm in normalize_text(country) and country not in seen:
            seen.add(country)
            suggestions.append({"type": "country", "label": country})

    # Limiter à 10 suggestions, équipes en priorité
    suggestions.sort(key=lambda x: (0 if x["type"] == "team" else 1, x["label"]))
    return {"suggestions": suggestions[:10], "query": q}


@app.get("/api/teams")
async def api_teams(
    league:  Optional[str] = Query(default=None),
    country: Optional[str] = Query(default=None),
):
    """Liste toutes les équipes disponibles dans la base."""
    teams = []
    seen  = set()

    for p in index.products:
        if not p.get("matched") or not p.get("team_key"):
            continue
        key = p["team_key"]
        if key in seen:
            continue
        if league  and league.lower()  not in (p.get("league", "")  or "").lower():
            continue
        if country and country.lower() not in (p.get("country", "") or "").lower():
            continue
        seen.add(key)
        teams.append({
            "key":      key,
            "name":     p["team"],
            "short":    p.get("team_short", ""),
            "league":   p.get("league", ""),
            "country":  p.get("country", ""),
            "count":    sum(1 for x in index.products if x.get("team_key") == key),
        })

    teams.sort(key=lambda t: t["name"])
    return {"teams": teams, "total": len(teams)}


@app.get("/api/filters")
async def api_filters():
    """Retourne toutes les options de filtres disponibles."""
    return {
        "versions":  [{"value": v, "label": _version_label(v)} for v in index.versions],
        "leagues":   sorted(index.leagues),
        "countries": sorted(index.countries),
        "seasons":   sorted(index.seasons, reverse=True),
        "types":     ["Home", "Away", "Third", "Goalkeeper", "Training", "Special"],
    }


@app.get("/api/product/{product_id}")
async def api_product(product_id: str):
    """Retourne les détails d'un produit spécifique."""
    product = index.by_id.get(product_id)
    if not product:
        raise HTTPException(404, detail="Produit non trouvé")
    return product


@app.get("/api/stats")
async def api_stats():
    """Statistiques de la base de données."""
    total   = len(index.products)
    matched = sum(1 for p in index.products if p.get("matched"))

    version_counts = Counter(p.get("version", "?") for p in index.products)
    league_counts  = Counter(p.get("league", "?") for p in index.products if p.get("matched"))

    return {
        "total_products":  total,
        "matched":         matched,
        "unmatched":       total - matched,
        "match_rate":      round(matched / total * 100, 1) if total else 0,
        "by_version":      dict(version_counts.most_common()),
        "top_leagues":     dict(league_counts.most_common(10)),
        "total_teams":     len(index.teams),
    }


def _version_label(v: str) -> str:
    return {"fan": "Fan Version", "player": "Player Version",
            "retro": "Rétro", "kit": "Kit Complet"}.get(v, v.capitalize())


# ── Admin ─────────────────────────────────────────────────────────────────────

def check_admin(credentials: HTTPBasicCredentials = Depends(security)):
    """Vérifie les credentials admin."""
    correct_password = API.get("admin_password", "elitekits2024")
    ok = (
        secrets.compare_digest(credentials.username.encode(), b"admin")
        and secrets.compare_digest(credentials.password.encode(), correct_password.encode())
    )
    if not ok:
        raise HTTPException(
            status_code=401,
            detail="Accès refusé",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(username: str = Depends(check_admin)):
    """Page d'administration EliteKits."""
    stats  = await api_stats()
    return HTMLResponse(_render_admin_html(stats))


@app.get("/admin/unmatched")
async def admin_unmatched(username: str = Depends(check_admin)):
    """Liste les produits non-matchés."""
    unmatched = [p for p in index.products if not p.get("matched")]
    return {
        "unmatched": unmatched[:200],
        "total": len(unmatched),
    }


@app.post("/admin/fix-team")
async def admin_fix_team(
    product_id: str,
    team_key:   str,
    username:   str = Depends(check_admin),
):
    """Corrige manuellement l'équipe associée à un produit."""
    from team_extractor import TEAM_DATABASE
    if product_id not in index.by_id:
        raise HTTPException(404, "Produit non trouvé")
    if team_key not in TEAM_DATABASE:
        raise HTTPException(400, f"Équipe inconnue : {team_key}")

    product   = index.by_id[product_id]
    team_data = TEAM_DATABASE[team_key]
    product.update({
        "team":             team_data["canonical_name"],
        "team_short":       team_data["short_name"],
        "team_key":         team_key,
        "team_aliases":     team_data.get("aliases", []),
        "league":           team_data.get("league", ""),
        "country":          team_data.get("country", ""),
        "confidence_score": 1.0,
        "matched":          True,
    })

    # Sauvegarder les changements
    _save_products()
    return {"status": "ok", "product_id": product_id, "team": team_data["canonical_name"]}


@app.post("/admin/rescrape")
async def admin_rescrape(
    catalog_id: Optional[str] = None,
    username:   str = Depends(check_admin),
):
    """Relance le scraping et reconstruit la base de données."""
    import asyncio
    import subprocess

    log.info(f"Rescraping demandé par admin : {catalog_id or 'all'}")
    cmd = [sys.executable, str(Path(__file__).parent / "update_catalog.py")]
    if catalog_id:
        cmd.extend(["--catalog", catalog_id])

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
        success = proc.returncode == 0
    except asyncio.TimeoutError:
        return {"status": "timeout", "message": "Scraping en cours (> 5 min), vérifier les logs"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

    if success:
        index.reload()
        return {"status": "ok", "products": len(index.products)}
    else:
        return {"status": "error", "stderr": stderr.decode("utf-8", errors="replace")[:2000]}


def _save_products():
    """Sauvegarde les modifications en mémoire dans products.json."""
    PRODUCTS_JSON.write_text(
        json.dumps(index.products, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _render_admin_html(stats: dict) -> str:
    """Génère la page HTML d'administration."""
    match_rate = stats.get("match_rate", 0)
    match_color = "#22c55e" if match_rate > 80 else "#f59e0b" if match_rate > 60 else "#ef4444"

    version_rows = "".join(
        f"<tr><td>{v}</td><td>{c}</td></tr>"
        for v, c in stats.get("by_version", {}).items()
    )
    league_rows = "".join(
        f"<tr><td>{l}</td><td>{c}</td></tr>"
        for l, c in stats.get("top_leagues", {}).items()
    )

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EliteKits — Admin</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #0f0f1a; color: #e2e8f0; padding: 2rem; }}
  h1 {{ font-size: 1.8rem; background: linear-gradient(135deg, #7c3aed, #2563eb);
       -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 2rem; }}
  h2 {{ font-size: 1.1rem; color: #a78bfa; margin: 1.5rem 0 0.8rem; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }}
  .card {{ background: rgba(30,30,60,0.8); border: 1px solid rgba(124,58,237,0.3); border-radius: 12px; padding: 1.2rem; }}
  .card .val {{ font-size: 2rem; font-weight: 700; color: #a78bfa; }}
  .card .lbl {{ font-size: 0.8rem; color: #94a3b8; margin-top: 0.3rem; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
  th, td {{ padding: 0.5rem 0.8rem; text-align: left; border-bottom: 1px solid rgba(124,58,237,0.2); }}
  th {{ color: #a78bfa; font-weight: 600; }}
  .btn {{ display: inline-flex; align-items: center; gap: 0.5rem; padding: 0.7rem 1.5rem;
          border-radius: 8px; font-size: 0.9rem; font-weight: 600; cursor: pointer;
          border: none; text-decoration: none; transition: all 0.2s; }}
  .btn-primary {{ background: linear-gradient(135deg, #7c3aed, #2563eb); color: white; }}
  .btn-primary:hover {{ opacity: 0.85; transform: translateY(-1px); }}
  .btn-danger  {{ background: #dc2626; color: white; }}
  .actions {{ display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 2rem; }}
  .badge {{ display: inline-block; padding: 0.2rem 0.6rem; border-radius: 99px; font-size: 0.75rem; font-weight: 600; }}
  .badge-ok {{ background: rgba(34,197,94,0.2); color: #22c55e; }}
  #toast {{ position: fixed; bottom: 2rem; right: 2rem; background: #7c3aed; color: white;
            padding: 1rem 1.5rem; border-radius: 10px; display: none; }}
</style>
</head>
<body>
<h1>⚡ EliteKits Admin</h1>

<div class="grid">
  <div class="card">
    <div class="val">{stats['total_products']}</div>
    <div class="lbl">Produits total</div>
  </div>
  <div class="card">
    <div class="val" style="color:{match_color}">{match_rate}%</div>
    <div class="lbl">Taux de matching</div>
  </div>
  <div class="card">
    <div class="val">{stats['total_teams']}</div>
    <div class="lbl">Équipes identifiées</div>
  </div>
  <div class="card">
    <div class="val" style="color:#ef4444">{stats['unmatched']}</div>
    <div class="lbl">Non-matchés</div>
  </div>
</div>

<div class="actions">
  <button class="btn btn-primary" onclick="rescrape()">🔄 Relancer le scraping</button>
  <a class="btn btn-primary" href="/admin/unmatched" target="_blank">⚠️ Voir non-matchés</a>
  <a class="btn btn-primary" href="/api/stats" target="_blank">📊 Stats JSON</a>
  <a class="btn btn-primary" href="/docs" target="_blank">📚 API Docs</a>
</div>

<h2>Par version</h2>
<table>
  <tr><th>Version</th><th>Produits</th></tr>
  {version_rows}
</table>

<h2>Top ligues</h2>
<table>
  <tr><th>Ligue</th><th>Produits</th></tr>
  {league_rows}
</table>

<h2>Correction manuelle</h2>
<div style="background:rgba(30,30,60,0.8);border:1px solid rgba(124,58,237,0.3);border-radius:12px;padding:1.2rem;margin-top:0.5rem">
  <p style="font-size:0.85rem;color:#94a3b8;margin-bottom:1rem">
    Entrez l'ID du produit et la clé de l'équipe correcte (ex: <code>paris saint-germain</code>).
  </p>
  <div style="display:flex;gap:1rem;flex-wrap:wrap">
    <input id="fixProductId"  placeholder="ID produit" style="flex:1;padding:0.6rem;background:#1e1e3f;border:1px solid #4c1d95;color:#e2e8f0;border-radius:6px">
    <input id="fixTeamKey"    placeholder="Clé équipe (ex: psg)" style="flex:1;padding:0.6rem;background:#1e1e3f;border:1px solid #4c1d95;color:#e2e8f0;border-radius:6px">
    <button class="btn btn-primary" onclick="fixTeam()">Corriger</button>
  </div>
</div>

<div id="toast"></div>

<script>
async function rescrape() {{
  const btn = event.target;
  btn.textContent = '⏳ Scraping en cours...';
  btn.disabled = true;
  try {{
    const r = await fetch('/admin/rescrape', {{method:'POST'}});
    const d = await r.json();
    showToast(d.status === 'ok' ? '✓ Base mise à jour : ' + d.products + ' produits' : '✗ Erreur: ' + d.message);
  }} finally {{
    btn.textContent = '🔄 Relancer le scraping';
    btn.disabled = false;
  }}
}}

async function fixTeam() {{
  const id  = document.getElementById('fixProductId').value.trim();
  const key = document.getElementById('fixTeamKey').value.trim().toLowerCase();
  if (!id || !key) {{ showToast('Remplissez les deux champs'); return; }}
  const r = await fetch(`/admin/fix-team?product_id=${{id}}&team_key=${{key}}`, {{method:'POST'}});
  const d = await r.json();
  showToast(d.status === 'ok' ? '✓ Corrigé : ' + d.team : '✗ Erreur: ' + (d.detail || d.message));
}}

function showToast(msg) {{
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.style.display = 'block';
  setTimeout(() => t.style.display = 'none', 4000);
}}
</script>
</body>
</html>"""


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "products": len(index.products), "loaded": index.loaded}


@app.get("/")
async def root():
    return {"message": "EliteKits Search API", "docs": "/docs", "admin": "/admin"}


# ── Lancement ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="EliteKits Search Engine")
    parser.add_argument("--host", default=API["host"])
    parser.add_argument("--port", type=int, default=API["port"])
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    log.info(f"Démarrage du serveur sur http://{args.host}:{args.port}")
    uvicorn.run(
        "search_engine:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )
