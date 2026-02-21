"""
update_catalog.py — Orchestrateur de mise à jour complète du catalogue EliteKits

Usage :
  python update_catalog.py                    # mise à jour complète
  python update_catalog.py --catalog fan      # catalogue spécifique
  python update_catalog.py --test             # test rapide (5 albums max)
  python update_catalog.py --build-only       # reconstruire la BDD sans re-scraper

Peut être lancé via cron : 0 3 * * * python /path/to/update_catalog.py
"""
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Force UTF-8 on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    CATALOGS, RAW_DATA_FILE, PRODUCTS_JSON, PRODUCTS_DB,
    UNMATCHED_CSV, UPDATE_LOG, LOGS_DIR
)

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(UPDATE_LOG, encoding="utf-8"),
    ],
)
log = logging.getLogger("update_catalog")


async def run_full_update(
    catalog_ids: list = None,
    max_albums:  int  = None,
    max_images:  int  = None,
    headless:    bool = True,
    build_only:  bool = False,
) -> dict:
    """
    Pipeline complet :
    1. Scraping des catalogues Yupoo
    2. Comparaison avec la base existante
    3. Construction de products.json + products.db
    4. Rapport de mise à jour
    """
    start_time = datetime.now()
    log.info("=" * 60)
    log.info("ÉLITE KITS — MISE À JOUR DU CATALOGUE")
    log.info(f"Démarré à : {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 60)

    report = {
        "started_at":   start_time.isoformat(),
        "catalog_ids":  catalog_ids or "all",
        "success":      False,
        "new_products": 0,
        "removed_products": 0,
        "total_products": 0,
        "matched_products": 0,
        "errors": [],
    }

    # ── Étape 1 : Scraping ────────────────────────────────────────────────────
    if not build_only:
        log.info("\n[SCRAPING] ÉTAPE 1 : SCRAPING DES CATALOGUES YUPOO")
        try:
            from scraper import run_scraper
            raw_data = await run_scraper(
                catalog_ids=catalog_ids,
                max_albums=max_albums,
                max_images=max_images,
                headless=headless,
            )
            total_albums = sum(len(c.get("albums", [])) for c in raw_data.get("catalogs", []))
            log.info(f"[OK] Scraping terminé : {total_albums} albums récupérés")
        except Exception as e:
            log.error(f"[ERR] Erreur scraping : {e}")
            import traceback
            traceback.print_exc()
            report["errors"].append(f"Scraping: {e}")
            report["finished_at"] = datetime.now().isoformat()
            _save_report(report)
            return report
    else:
        log.info("\n[SKIP]  Scraping ignoré (--build-only)")
        if not RAW_DATA_FILE.exists():
            log.error("Aucun fichier raw_catalog.json. Lancez sans --build-only d'abord.")
            return report

    # ── Étape 2 : Comparaison avec la base existante ──────────────────────────
    log.info("\n[COMPARE] ÉTAPE 2 : COMPARAISON AVEC LA BASE EXISTANTE")
    existing_ids = _load_existing_ids()
    log.info(f"Produits existants : {len(existing_ids)}")

    # ── Étape 3 : Construction de la base de données ──────────────────────────
    log.info("\n[BUILD]  ÉTAPE 3 : CONSTRUCTION DE LA BASE DE DONNÉES")
    try:
        from database_builder import build_database, load_raw_data
        raw_data = load_raw_data(RAW_DATA_FILE)
        if not raw_data:
            raise RuntimeError("Impossible de charger raw_catalog.json")

        products = build_database(
            raw_data,
            output_json=PRODUCTS_JSON,
            output_db=PRODUCTS_DB,
            unmatched_csv=UNMATCHED_CSV,
        )

        new_ids = {p["id"] for p in products}

        # Calculer les différences
        added   = new_ids - existing_ids
        removed = existing_ids - new_ids
        matched = sum(1 for p in products if p.get("matched"))

        report.update({
            "total_products":   len(products),
            "new_products":     len(added),
            "removed_products": len(removed),
            "matched_products": matched,
            "match_rate":       round(matched / len(products) * 100, 1) if products else 0,
        })

        log.info(f"[OK] {len(products)} produits total")
        log.info(f"  + {len(added)} nouveaux produits")
        log.info(f"  - {len(removed)} produits supprimés")
        log.info(f"  [OK] {matched} matchés ({report['match_rate']}%)")

    except Exception as e:
        log.error(f"[ERR] Erreur construction BDD : {e}")
        import traceback
        traceback.print_exc()
        report["errors"].append(f"Database: {e}")

    # ── Étape 4 : Rapport ─────────────────────────────────────────────────────
    end_time    = datetime.now()
    duration    = (end_time - start_time).total_seconds()
    report.update({
        "success":     len(report["errors"]) == 0,
        "finished_at": end_time.isoformat(),
        "duration_s":  round(duration, 1),
    })

    _save_report(report)
    _print_summary(report, duration)

    return report


def _load_existing_ids() -> set:
    """Charge les IDs des produits déjà en base."""
    if not PRODUCTS_JSON.exists():
        return set()
    try:
        with open(PRODUCTS_JSON, encoding="utf-8") as f:
            products = json.load(f)
        return {p["id"] for p in products}
    except Exception:
        return set()


def _save_report(report: dict):
    """Sauvegarde le rapport de mise à jour."""
    report_file = LOGS_DIR / "last_update.json"
    report_file.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _print_summary(report: dict, duration: float):
    """Affiche un résumé lisible de la mise à jour."""
    status = "[OK] SUCCÈS" if report["success"] else "[ERR] ÉCHEC"
    log.info(f"\n{'='*60}")
    log.info(f"RÉSUMÉ DE LA MISE À JOUR — {status}")
    log.info(f"{'='*60}")
    log.info(f"Durée             : {duration:.1f}s")
    log.info(f"Produits total    : {report.get('total_products', 0)}")
    log.info(f"Nouveaux          : {report.get('new_products', 0)}")
    log.info(f"Supprimés         : {report.get('removed_products', 0)}")
    log.info(f"Taux de matching  : {report.get('match_rate', 0)}%")

    if report.get("errors"):
        log.error("\nERREURS :")
        for err in report["errors"]:
            log.error(f"  - {err}")

    log.info(f"\nFichiers générés :")
    log.info(f"  {PRODUCTS_JSON}")
    log.info(f"  {PRODUCTS_DB}")
    log.info(f"  {UNMATCHED_CSV}")
    log.info(f"{'='*60}")


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="EliteKits — Mise à jour complète du catalogue",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  python update_catalog.py                     # mise à jour complète
  python update_catalog.py --catalog fan       # fans uniquement
  python update_catalog.py --test              # test (5 albums par catalogue)
  python update_catalog.py --build-only        # reconstruire sans scraper
  python update_catalog.py --headful           # voir le navigateur (debug)
        """,
    )
    parser.add_argument(
        "--catalog", nargs="+",
        choices=[c["id"] for c in CATALOGS] + ["all"],
        default=["all"],
    )
    parser.add_argument("--max-albums", type=int, default=None)
    parser.add_argument("--max-images", type=int, default=None)
    parser.add_argument("--headful",    action="store_true")
    parser.add_argument("--test",       action="store_true", help="5 albums max par catalogue")
    parser.add_argument("--build-only", action="store_true", help="Reconstruire la BDD sans scraper")
    args = parser.parse_args()

    catalog_ids = None if "all" in args.catalog else args.catalog
    max_albums  = 5 if args.test else args.max_albums

    report = asyncio.run(run_full_update(
        catalog_ids=catalog_ids,
        max_albums=max_albums,
        max_images=args.max_images,
        headless=not args.headful,
        build_only=args.build_only,
    ))

    sys.exit(0 if report["success"] else 1)
