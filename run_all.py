"""
MiraScrap - Pipeline local complet (sans limite de temps)

Usage interactif :  python run_all.py
Usage direct :      python run_all.py --limit 500 --ca-min 5 --ca-max 50 --region 11
"""

import os
import sys
import argparse
import zipfile
from datetime import datetime
from pathlib import Path

# Charger .env si present (cle API locale)
_env_path = Path(__file__).parent / '.env'
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, val = line.split('=', 1)
            os.environ.setdefault(key.strip(), val.strip())

from scraper import DataGouvScraper, TRANCHES_PME
from scraper_pappers import PappersScraper
from enricher import SocieteEnricher
from qualifier import AutoScorer, ProspectQualifier, format_excel_output
from letter_generator import LetterGenerator
import config


def run_pipeline(custom_filtres=None):
    """
    Execute le pipeline complet :
    1. Scraping API data.gouv (CA + dirigeant + age inclus)
    2. Enrichissement API JSON + recherche site web (DDG)
    3. Scoring auto ou IA
    4. Deduplication + generation lettres
    5. Export Excel + ZIP
    """
    filtres = custom_filtres if custom_filtres else config.FILTRES

    print("\n" + "="*60)
    print("MIRASCRAP - PIPELINE PROSPECTS B2B")
    print("="*60)

    os.makedirs("outputs", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # ================================================
    # ETAPE 1 : SCRAPING (data.gouv -> fallback Pappers)
    # ================================================
    print("\n ETAPE 1/5 : Scraping data.gouv.fr (CA, dirigeants, finances)")
    print("-" * 60)

    try:
        scraper = DataGouvScraper()
        companies = scraper.search_companies(filtres)
    except RuntimeError as e:
        print(f"\n data.gouv inaccessible: {e}")
        companies = None

    if not companies and config.PAPPERS_API_KEY:
        print("\n Fallback Pappers...")
        try:
            scraper = PappersScraper(config.PAPPERS_API_KEY)
            companies = scraper.search_companies(filtres)
        except RuntimeError as e:
            print(f"\n Pappers aussi en erreur: {e}")

    if not companies:
        print("\n ERREUR : Aucune entreprise trouvee")
        return None

    try:
        df = scraper.to_dataframe(companies)

        ca_filled = df['ca_euros'].notna().sum()
        age_filled = df['age_dirigeant'].notna().sum()
        print(f"\n {len(df)} entreprises (CA: {ca_filled}/{len(df)}, Age: {age_filled}/{len(df)})")

    except Exception as e:
        print(f"\n ERREUR scraping : {e}")
        return None

    # ================================================
    # ETAPE 2 : ENRICHISSEMENT API JSON + SITE WEB
    # ================================================
    print("\n ETAPE 2/5 : Enrichissement API JSON + recherche site web")
    print("-" * 60)

    try:
        enricher = SocieteEnricher()
        df = enricher.enrich_dataframe(df, filter_ca=False)

        file_enriched = f"outputs/enriched_{timestamp}.xlsx"
        df.to_excel(file_enriched, index=False)
        print(f" Sauvegarde : {file_enriched}")

    except Exception as e:
        print(f"\n Enrichissement partiel ({e})")

    # ================================================
    # ETAPE 3 : SCORING
    # ================================================
    print("\n ETAPE 3/5 : Scoring")
    print("-" * 60)

    has_api_key = config.ANTHROPIC_API_KEY and config.ANTHROPIC_API_KEY != "sk-ant-xxxxx"

    if has_api_key:
        print("  Qualification IA (Claude)...")
        try:
            qualifier = ProspectQualifier(config.ANTHROPIC_API_KEY)
            df = qualifier.qualify_dataframe(df)
        except Exception as e:
            print(f"  Erreur IA: {e} -> scoring automatique")
            scorer = AutoScorer()
            df = scorer.score_dataframe(df)
    else:
        print("  Scoring automatique (pas de cle API)")
        scorer = AutoScorer()
        df = scorer.score_dataframe(df)

    # ================================================
    # ETAPE 4 : DEDUPLICATION + GENERATION LETTRES
    # ================================================
    print("\n ETAPE 4/5 : Deduplication + Generation lettres")
    print("-" * 60)

    # Deduplication par SIREN
    if 'siren' in df.columns:
        before = len(df)
        df = df.drop_duplicates(subset=['siren'], keep='first')
        if len(df) < before:
            print(f"  Dedup: {before} -> {len(df)} ({before - len(df)} doublons supprimes)")

    lettres_dir = f"outputs/lettres_{timestamp}"
    letter_api_key = config.ANTHROPIC_API_KEY if has_api_key else ""
    gen = LetterGenerator(output_dir=lettres_dir, api_key=letter_api_key)

    # Generer lettres Word
    letter_files = []
    total = len(df)
    for i, (_, row) in enumerate(df.iterrows()):
        prospect = row.to_dict()
        try:
            buf = gen.generate_letter(prospect)
            filename = gen.generate_filename(prospect)
            filepath = os.path.join(lettres_dir, filename)
            with open(filepath, 'wb') as f:
                f.write(buf.getvalue())
            letter_files.append(filepath)
        except Exception as e:
            print(f"  Erreur lettre pour {prospect.get('nom_entreprise', '?')}: {e}")
        if total > 50 and (i + 1) % 50 == 0:
            print(f"  Lettres : {i+1}/{total}...")
    print(f"  {len(letter_files)} lettres generees dans {lettres_dir}/")

    # ================================================
    # ETAPE 5 : EXPORT EXCEL + ZIP
    # ================================================
    print("\n ETAPE 5/5 : Export Excel + ZIP")
    print("-" * 60)

    file_final = f"outputs/prospects_{timestamp}.xlsx"
    excel_bytes = format_excel_output(df, file_final)

    # ZIP
    zip_path = f"outputs/MiraScrap_{timestamp}.zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(file_final, "prospects.xlsx")
        for letter_path in letter_files:
            letter_name = os.path.basename(letter_path)
            zf.write(letter_path, f"lettres/{letter_name}")

    print(f"  ZIP : {zip_path}")

    # Resume
    print("\n" + "="*60)
    print("PIPELINE TERMINE")
    print("="*60)

    print(f"\n {len(df)} entreprises analysees")

    if 'score' in df.columns:
        print("\nScores :")
        score_counts = df['score'].value_counts().sort_index()
        for score, count in score_counts.items():
            label = config.SCORING_CATEGORIES.get(score, '')
            print(f"   {score} - {label} : {count}")

    print(f"\n Excel  : {file_final}")
    print(f"   Lettres : {lettres_dir}/")
    print(f"   ZIP     : {zip_path}")
    print("="*60 + "\n")

    return file_final


def interactive_setup():
    """Configuration interactive des filtres."""
    print("\n" + "="*60)
    print("MIRASCRAP - Configuration")
    print("="*60)

    # Region
    print("\nRegions disponibles :")
    for code, nom in sorted(config.REGIONS.items()):
        print(f"  {code} = {nom}")
    region = input("\nCode region (vide = toute la France) : ").strip() or None

    # CA
    ca_min = input("CA minimum en M euros [5] : ").strip()
    ca_min = float(ca_min) if ca_min else 5.0
    ca_max = input("CA maximum en M euros [50] : ").strip()
    ca_max = float(ca_max) if ca_max else 50.0

    # Secteur
    print("\nSecteurs disponibles :")
    for code, nom in sorted(config.SECTEURS_NAF.items()):
        print(f"  {code} = {nom}")
    secteur = input("\nCode secteur (vide = tous) : ").strip() or None

    # Forme juridique
    forme = input("Forme juridique (SAS/SARL/SA, vide = toutes) : ").strip() or None

    # Nombre
    limit = input("Nombre d'entreprises [500] : ").strip()
    limit = int(limit) if limit else 500

    filtres = {
        'tranches_effectif': TRANCHES_PME,
        'region': region,
        'secteur_naf': secteur,
        'forme_juridique': forme,
        'age_min': 0,
        'age_dirigeant_min': 0,
        'age_dirigeant_max': 0,
        'ca_min': ca_min * 1_000_000,
        'ca_max': ca_max * 1_000_000,
        'limit': limit,
    }

    print(f"\n  Region : {config.REGIONS.get(region, 'Toute la France') if region else 'Toute la France'}")
    print(f"  CA : {ca_min:.0f}M - {ca_max:.0f}M")
    print(f"  Secteur : {config.SECTEURS_NAF.get(secteur, 'Tous') if secteur else 'Tous'}")
    print(f"  Forme : {forme or 'Toutes'}")
    print(f"  Limite : {limit} entreprises")

    input("\nAppuie sur ENTREE pour lancer (Ctrl+C pour annuler)...\n")

    return filtres


def main():
    parser = argparse.ArgumentParser(description="MiraScrap - Pipeline local")
    parser.add_argument('--limit', type=int, help='Nombre d\'entreprises')
    parser.add_argument('--ca-min', type=float, help='CA minimum en M euros')
    parser.add_argument('--ca-max', type=float, help='CA maximum en M euros')
    parser.add_argument('--region', type=str, help='Code region INSEE')
    parser.add_argument('--secteur', type=str, help='Code secteur NAF')
    parser.add_argument('--forme', type=str, help='Forme juridique (SAS/SARL/SA)')
    args = parser.parse_args()

    # Mode CLI direct si des arguments sont passes
    if any(v is not None for v in [args.limit, args.ca_min, args.ca_max, args.region]):
        filtres = {
            'tranches_effectif': TRANCHES_PME,
            'region': args.region,
            'secteur_naf': args.secteur,
            'forme_juridique': args.forme,
            'age_min': 0,
            'age_dirigeant_min': 0,
            'age_dirigeant_max': 0,
            'ca_min': (args.ca_min or 5) * 1_000_000,
            'ca_max': (args.ca_max or 50) * 1_000_000,
            'limit': args.limit or 500,
        }
    else:
        # Mode interactif
        filtres = interactive_setup()

    result = run_pipeline(filtres)

    if result:
        print(f"Succes ! Fichier : {result}")
    else:
        print("Echec du pipeline")
        sys.exit(1)


if __name__ == "__main__":
    main()
