"""
Script pour exécuter tout le pipeline en une seule commande
Usage: python run_all.py
"""

import os
import sys
from datetime import datetime
from scraper import DataGouvScraper
from enricher import PappersEnricher
from qualifier import ProspectQualifier
import config


def run_pipeline(custom_filtres=None):
    """
    Exécute le pipeline complet : scraping → enrichissement → qualification
    
    Args:
        custom_filtres: Dict de filtres personnalisés (optionnel)
    
    Returns:
        Chemin du fichier Excel final
    """
    
    # Utilise les filtres custom ou ceux du config
    filtres = custom_filtres if custom_filtres else config.FILTRES
    
    print("\n" + "="*60)
    print("🎯 PIPELINE SCRAPING PROSPECTS B2B")
    print("="*60)
    
    # Crée le dossier outputs
    os.makedirs("outputs", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # ================================================
    # ÉTAPE 1 : SCRAPING DATA.GOUV
    # ================================================
    print("\n📍 ÉTAPE 1/4 : Scraping data.gouv.fr")
    print("-" * 60)
    
    try:
        scraper = DataGouvScraper()
        companies = scraper.search_companies(filtres)
        
        if not companies:
            print("\n❌ ERREUR : Aucune entreprise trouvée avec ces critères")
            print("\n💡 Suggestions :")
            print("   - Élargis la fourchette de CA")
            print("   - Essaie sans filtre région")
            print("   - Vérifie le code NAF")
            return None
        
        df = scraper.to_dataframe(companies)
        
        # Sauvegarde intermédiaire
        file_raw = f"outputs/raw_{timestamp}.xlsx"
        df.to_excel(file_raw, index=False)
        
        print(f"\n✅ {len(df)} entreprises récupérées")
        print(f"📄 Sauvegardé : {file_raw}")
        
    except Exception as e:
        print(f"\n❌ ERREUR lors du scraping : {e}")
        return None
    
    # ================================================
    # ÉTAPE 2 : ENRICHISSEMENT PAPPERS
    # ================================================
    print("\n📍 ÉTAPE 2/4 : Enrichissement Pappers")
    print("-" * 60)
    
    try:
        original_limit = filtres.get('limit', 100)
        enricher = PappersEnricher()
        df = enricher.enrich_dataframe(df, target_limit=original_limit)
        
        # Sauvegarde enrichie
        file_enriched = f"outputs/enriched_{timestamp}.xlsx"
        df.to_excel(file_enriched, index=False)
        
        print(f"\n✅ Données enrichies")
        print(f"📄 Sauvegardé : {file_enriched}")
        
    except Exception as e:
        print(f"\n⚠️ AVERTISSEMENT : Enrichissement partiel ({e})")
        print("   → Le fichier brut est disponible")
    
    # ================================================
    # ÉTAPE 3 : VÉRIFICATION CLÉ API
    # ================================================
    print("\n📍 ÉTAPE 3/4 : Vérification API Anthropic")
    print("-" * 60)
    
    if not config.ANTHROPIC_API_KEY or config.ANTHROPIC_API_KEY == "sk-ant-xxxxx":
        print("\n⚠️ AVERTISSEMENT : Clé API Anthropic manquante")
        print("   → Qualification IA sautée")
        print("\n💡 Pour activer la qualification :")
        print("   1. Obtiens une clé sur https://console.anthropic.com/")
        print("   2. Ajoute-la dans config.py : ANTHROPIC_API_KEY = 'sk-ant-xxxxx'")
        print(f"\n📄 Fichier enrichi disponible : {file_enriched}")
        return file_enriched
    
    # ================================================
    # ÉTAPE 4 : QUALIFICATION IA
    # ================================================
    print("\n📍 ÉTAPE 4/4 : Qualification IA")
    print("-" * 60)
    
    try:
        qualifier = ProspectQualifier(config.ANTHROPIC_API_KEY)
        df = qualifier.qualify_dataframe(df)
        
        # Export final
        file_final = f"outputs/prospects_qualified_{timestamp}.xlsx"
        qualifier.format_excel_output(df, file_final)
        
        # ================================================
        # RÉSUMÉ FINAL
        # ================================================
        print("\n" + "="*60)
        print("✅ PIPELINE TERMINÉ AVEC SUCCÈS")
        print("="*60)
        
        print(f"\n📊 STATISTIQUES")
        print("-" * 60)
        print(f"Total entreprises analysées : {len(df)}")
        
        if 'score' in df.columns:
            print("\nRépartition des scores :")
            score_counts = df['score'].value_counts().sort_index()
            for score, count in score_counts.items():
                label = config.SCORING_CATEGORIES.get(score, '')
                print(f"   {score} - {label} : {count}")
        
        print(f"\n📄 FICHIER FINAL")
        print("-" * 60)
        print(f"   {file_final}")
        
        # Affiche les top prospects
        if 'score' in df.columns:
            top_prospects = df[df['score'] == 'A'].head(5)
            if len(top_prospects) > 0:
                print(f"\n🎯 TOP {len(top_prospects)} PROSPECTS (Score A)")
                print("-" * 60)
                for idx, row in top_prospects.iterrows():
                    nom = row.get('nom_entreprise', 'N/A')
                    ville = row.get('ville', 'N/A')
                    ca = row.get('ca_m_euros', row.get('ca_euros', 0))
                    if ca and ca > 1000:
                        ca = ca / 1_000_000
                    print(f"   • {nom} ({ville}) - CA: {ca:.1f}M€")
        
        print("\n" + "="*60 + "\n")
        
        return file_final
        
    except Exception as e:
        print(f"\n❌ ERREUR lors de la qualification : {e}")
        print(f"\n📄 Fichier enrichi disponible : {file_enriched}")
        import traceback
        traceback.print_exc()
        return file_enriched


def main():
    """Point d'entrée principal"""
    
    print("\n🚀 Démarrage du pipeline avec les filtres du config.py")
    print("\nFiltres actifs :")
    print(f"   - CA : {config.FILTRES['ca_min']/1_000_000:.0f}M€ → {config.FILTRES['ca_max']/1_000_000:.0f}M€")
    print(f"   - Région : {config.REGIONS.get(config.FILTRES.get('region', ''), 'Toute la France')}")
    print(f"   - Secteur : {config.SECTEURS_NAF.get(config.FILTRES.get('secteur_naf', ''), 'Tous')}")
    print(f"   - Forme : {config.FILTRES.get('forme_juridique', 'Toutes')}")
    print(f"   - Limite : {config.FILTRES.get('limit', 'Aucune')}")
    
    input("\nAppuie sur ENTRÉE pour continuer (ou Ctrl+C pour annuler)...\n")
    
    result = run_pipeline()
    
    if result:
        print(f"✅ Succès ! Fichier disponible : {result}")
    else:
        print("❌ Échec du pipeline")
        sys.exit(1)


if __name__ == "__main__":
    main()
