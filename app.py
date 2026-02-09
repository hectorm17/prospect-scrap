"""
Interface Streamlit pour le scraper de prospects B2B
Permet de configurer les filtres et lancer l'analyse en un clic
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import os
import sys

# Import des modules
from scraper import DataGouvScraper, TRANCHES_EFFECTIF, TRANCHES_PME
from enricher import SocieteEnricher
from qualifier import ProspectQualifier
import config

# Configuration de la page
st.set_page_config(
    page_title="Scraper Prospects B2B",
    page_icon="🎯",
    layout="wide"
)

# Style CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .success-box {
        padding: 1rem;
        background-color: #d4edda;
        border-left: 4px solid #28a745;
        border-radius: 4px;
        margin: 1rem 0;
    }
    .info-box {
        padding: 1rem;
        background-color: #d1ecf1;
        border-left: 4px solid #17a2b8;
        border-radius: 4px;
        margin: 1rem 0;
    }
    .warning-box {
        padding: 1rem;
        background-color: #fff3cd;
        border-left: 4px solid #ffc107;
        border-radius: 4px;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)


def main():
    """Interface principale"""
    
    # Header
    st.markdown('<div class="main-header">Scraper Prospects B2B</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Data.gouv + Societe.com + Claude IA</div>', unsafe_allow_html=True)
    
    # Sidebar : Configuration
    st.sidebar.title("⚙️ Configuration")
    
    # Vérification clé API
    api_key = st.sidebar.text_input(
        "Clé API Anthropic",
        value=config.ANTHROPIC_API_KEY if config.ANTHROPIC_API_KEY != "sk-ant-xxxxx" else "",
        type="password",
        help="Obtiens ta clé sur https://console.anthropic.com/"
    )
    
    if not api_key or api_key == "sk-ant-xxxxx":
        st.sidebar.warning("⚠️ Configure ta clé API Anthropic pour activer la qualification IA")
    
    st.sidebar.markdown("---")
    
    # Onglets
    tab1, tab2 = st.tabs(["🔍 Nouvelle recherche", "📊 Historique"])
    
    with tab1:
        run_search_interface(api_key)
    
    with tab2:
        show_history()


def run_search_interface(api_key: str):
    """Interface de recherche"""
    
    st.header("1️⃣ Définir les filtres de recherche")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("💰 Chiffre d'affaires")
        ca_min = st.number_input(
            "CA minimum (M€)",
            min_value=0.0,
            max_value=1000.0,
            value=5.0,
            step=1.0
        )
        ca_max = st.number_input(
            "CA maximum (M€)",
            min_value=0.0,
            max_value=1000.0,
            value=50.0,
            step=1.0
        )
        
        st.subheader("🏭 Secteur d'activité")
        secteur_options = ["Tous"] + [f"{code} - {lib}" for code, lib in config.SECTEURS_NAF.items()]
        secteur = st.selectbox("Code NAF", secteur_options)
        secteur_code = None if secteur == "Tous" else secteur.split(" - ")[0]
    
    with col2:
        st.subheader("📍 Localisation")
        region_options = ["Toute la France"] + [f"{code} - {lib}" for code, lib in config.REGIONS.items()]
        region = st.selectbox("Région", region_options)
        region_code = None if region == "Toute la France" else region.split(" - ")[0]
        
        st.subheader("🏢 Forme juridique")
        forme_options = ["Toutes", "SAS", "SARL", "SA", "SCI"]
        forme = st.selectbox("Forme juridique", forme_options)
        forme_code = None if forme == "Toutes" else forme
    
    st.markdown("---")
    
    col3, col4 = st.columns(2)
    
    with col3:
        st.subheader("⏳ Autres filtres")
        age_min = st.number_input(
            "Âge minimum entreprise (années)",
            min_value=0,
            max_value=100,
            value=3
        )
    
    with col4:
        st.subheader("🎯 Limite de résultats")
        limit = st.number_input(
            "Nombre max d'entreprises (0 = illimité)",
            min_value=0,
            max_value=1000,
            value=50,
            help="Pour tests, commence par 10-20"
        )
        limit_value = None if limit == 0 else limit
    
    st.markdown("---")
    
    # Options avancées
    with st.expander("⚙️ Options avancées"):
        skip_enrichment = st.checkbox("Sauter l'enrichissement Pappers", value=False)
        skip_qualification = st.checkbox("Sauter la qualification IA", value=False)
        
        if skip_qualification:
            st.info("💡 L'enrichissement Pappers sera quand même effectué pour avoir les données complètes")
    
    # Résumé
    st.header("📋 Résumé de la recherche")
    
    filters_summary = f"""
    - **CA** : {ca_min} M€ → {ca_max} M€
    - **Région** : {region}
    - **Secteur** : {secteur}
    - **Forme** : {forme}
    - **Âge min** : {age_min} ans
    - **Limite** : {limit if limit > 0 else 'Aucune'}
    """
    
    st.markdown(f'<div class="info-box">{filters_summary}</div>', unsafe_allow_html=True)
    
    # Bouton de lancement
    st.markdown("---")
    
    col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
    
    with col_btn2:
        if st.button("🚀 LANCER LA RECHERCHE", type="primary", use_container_width=True):
            run_scraping_pipeline(
                ca_min=ca_min * 1_000_000,
                ca_max=ca_max * 1_000_000,
                region_code=region_code,
                secteur_code=secteur_code,
                forme_code=forme_code,
                age_min=age_min,
                limit=limit_value,
                api_key=api_key,
                skip_enrichment=skip_enrichment,
                skip_qualification=skip_qualification
            )


def run_scraping_pipeline(ca_min, ca_max, region_code, secteur_code, forme_code, 
                          age_min, limit, api_key, skip_enrichment, skip_qualification):
    """Exécute le pipeline complet"""
    
    os.makedirs("outputs", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Configuration des filtres
    # Note: ca_min/ca_max sont utilisés après enrichissement (l'API data.gouv ne les supporte pas)
    config.FILTRES['ca_min'] = ca_min
    config.FILTRES['ca_max'] = ca_max

    filtres = {
        'tranches_effectif': TRANCHES_PME,  # 20-249 salariés (proxy pour CA 5-50M)
        'region': region_code,
        'secteur_naf': secteur_code,
        'forme_juridique': forme_code,
        'age_min': age_min,
        'limit': limit,
    }
    
    # Barre de progression globale
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        # ÉTAPE 1 : Scraping Data.gouv
        status_text.text("🔍 Étape 1/4 : Recherche sur data.gouv.fr...")
        progress_bar.progress(10)
        
        scraper = DataGouvScraper()
        companies = scraper.search_companies(filtres)
        
        if not companies:
            st.error("❌ Aucune entreprise trouvée avec ces critères")
            return
        
        df = scraper.to_dataframe(companies)
        
        progress_bar.progress(25)
        st.success(f"✅ {len(df)} entreprises trouvées sur data.gouv.fr")
        
        # Sauvegarde intermédiaire
        file_raw = f"outputs/raw_{timestamp}.xlsx"
        df.to_excel(file_raw, index=False)
        
        # ÉTAPE 2 : Enrichissement Societe.com
        if not skip_enrichment:
            status_text.text("🔄 Étape 2/4 : Enrichissement via Societe.com...")
            progress_bar.progress(30)

            enricher = SocieteEnricher()
            df = enricher.enrich_dataframe(df, filter_ca=True, target_limit=limit)
            
            progress_bar.progress(55)
            st.success(f"✅ Données enrichies")
            
            # Sauvegarde enrichie
            file_enriched = f"outputs/enriched_{timestamp}.xlsx"
            df.to_excel(file_enriched, index=False)
        else:
            progress_bar.progress(55)
            st.info("⏭️ Enrichissement Pappers sauté")
        
        # ÉTAPE 3 : Qualification IA
        if not skip_qualification:
            if not api_key or api_key == "sk-ant-xxxxx":
                st.warning("⚠️ Clé API manquante : qualification IA sautée")
                progress_bar.progress(100)
            else:
                status_text.text("🤖 Étape 3/4 : Qualification IA + Recherche web...")
                progress_bar.progress(60)
                
                qualifier = ProspectQualifier(api_key)
                df = qualifier.qualify_dataframe(df)
                
                progress_bar.progress(90)
                st.success(f"✅ Prospects qualifiés")
                
                # ÉTAPE 4 : Export final
                status_text.text("📊 Étape 4/4 : Génération du fichier Excel final...")
                
                file_final = f"outputs/prospects_qualified_{timestamp}.xlsx"
                qualifier.format_excel_output(df, file_final)
                
                progress_bar.progress(100)
                status_text.text("✅ Terminé !")
                
                # Affichage résultat
                st.markdown("---")
                st.success("🎉 Analyse terminée avec succès !")
                
                # Stats
                col1, col2, col3, col4 = st.columns(4)
                
                score_counts = df['score'].value_counts()
                col1.metric("Score A", score_counts.get('A', 0))
                col2.metric("Score B", score_counts.get('B', 0))
                col3.metric("Score C", score_counts.get('C', 0))
                col4.metric("Score D", score_counts.get('D', 0))
                
                # Téléchargement
                with open(file_final, 'rb') as f:
                    st.download_button(
                        label="📥 Télécharger le fichier Excel",
                        data=f,
                        file_name=f"prospects_{timestamp}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                
                # Preview
                st.subheader("📊 Aperçu des résultats")
                preview_cols = ['score', 'score_label', 'nom_entreprise',
                                'ca_m_euros', 'evolution_ca', 'ville',
                                'signaux_ma', 'justification']
                existing_preview = [c for c in preview_cols if c in df.columns]
                st.dataframe(
                    df[existing_preview].head(10),
                    use_container_width=True
                )
        else:
            progress_bar.progress(100)
            status_text.text("✅ Terminé (sans qualification IA)")
            
            st.info("💡 Fichier brut disponible dans outputs/")
    
    except Exception as e:
        st.error(f"❌ Erreur : {e}")
        import traceback
        st.code(traceback.format_exc())


def show_history():
    """Affiche l'historique des fichiers générés"""
    
    st.header("📊 Historique des recherches")
    
    import glob
    
    files = glob.glob("outputs/prospects_qualified_*.xlsx")
    
    if not files:
        st.info("Aucun fichier trouvé. Lance une recherche d'abord !")
        return
    
    # Trie par date (plus récent d'abord)
    files.sort(key=os.path.getctime, reverse=True)
    
    for file in files:
        # Extrait la date
        timestamp = file.split("_")[-1].replace(".xlsx", "")
        date_str = f"{timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]} {timestamp[9:11]}:{timestamp[11:13]}"
        
        # Charge le fichier
        df = pd.read_excel(file)
        
        with st.expander(f"📁 {date_str} - {len(df)} prospects"):
            col1, col2, col3, col4, col5 = st.columns(5)
            
            score_counts = df['score'].value_counts()
            col1.metric("Total", len(df))
            col2.metric("Score A", score_counts.get('A', 0))
            col3.metric("Score B", score_counts.get('B', 0))
            col4.metric("Score C", score_counts.get('C', 0))
            col5.metric("Score D", score_counts.get('D', 0))
            
            # Téléchargement
            with open(file, 'rb') as f:
                st.download_button(
                    label="📥 Télécharger",
                    data=f,
                    file_name=os.path.basename(file),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=file
                )
            
            # Preview
            preview_cols = ['score', 'nom_entreprise', 'ville',
                            'signaux_ma', 'justification']
            # Gère les anciens fichiers sans les nouvelles colonnes
            score_col = 'score' if 'score' in df.columns else 'Score'
            existing_preview = [c for c in preview_cols if c in df.columns]
            st.dataframe(
                df[existing_preview].head(5),
                use_container_width=True
            )


if __name__ == "__main__":
    main()
