"""
Script pour executer tout le pipeline en une seule commande
Usage: python run_all.py
"""

import os
import sys
import zipfile
from datetime import datetime
from scraper import DataGouvScraper
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
    4. Export Excel
    """
    filtres = custom_filtres if custom_filtres else config.FILTRES

    print("\n" + "="*60)
    print("MIRASCRAP - PIPELINE PROSPECTS B2B")
    print("="*60)

    os.makedirs("outputs", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # ================================================
    # ETAPE 1 : SCRAPING DATA.GOUV (CA + dirigeant + age)
    # ================================================
    print("\n ETAPE 1/5 : Scraping data.gouv.fr (CA, dirigeants, finances)")
    print("-" * 60)

    try:
        scraper = DataGouvScraper()
        companies = scraper.search_companies(filtres)

        if not companies:
            print("\n ERREUR : Aucune entreprise trouvee")
            return None

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
    # ETAPE 4 : EXPORT EXCEL
    # ================================================
    print("\n ETAPE 4/5 : Export Excel")
    print("-" * 60)

    file_final = f"outputs/prospects_{timestamp}.xlsx"
    excel_bytes = format_excel_output(df, file_final)

    # ================================================
    # ETAPE 5 : GENERATION LETTRES + ZIP
    # ================================================
    print("\n ETAPE 5/5 : Generation lettres Word + ZIP")
    print("-" * 60)

    lettres_dir = f"outputs/lettres_{timestamp}"
    gen = LetterGenerator(output_dir=lettres_dir)
    letter_files = gen.generate_all(df)

    print(f"  {len(letter_files)} lettres generees dans {lettres_dir}/")

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


def main():
    print("\n Demarrage du pipeline avec les filtres du config.py")
    print(f"   CA : {config.FILTRES['ca_min']/1e6:.0f}M - {config.FILTRES['ca_max']/1e6:.0f}M")
    print(f"   Region : {config.REGIONS.get(config.FILTRES.get('region', ''), 'Toute la France')}")
    print(f"   Limite : {config.FILTRES.get('limit', 'Aucune')}")

    input("\nAppuie sur ENTREE pour continuer (ou Ctrl+C pour annuler)...\n")

    result = run_pipeline()

    if result:
        print(f"Succes ! Fichier : {result}")
    else:
        print("Echec du pipeline")
        sys.exit(1)


if __name__ == "__main__":
    main()
