"""
Interface Streamlit pour le scraper de prospects B2B
Design moderne dark theme inspiré Linear.app / Vercel
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
import os
import sys

# Import des modules
from scraper import DataGouvScraper, TRANCHES_EFFECTIF, TRANCHES_PME
from enricher import SocieteEnricher
from qualifier import ProspectQualifier
import config

# Configuration de la page
st.set_page_config(
    page_title="Prospect Scraper B2B",
    page_icon="",
    layout="wide"
)

# Initialise l'historique en session
if 'search_history' not in st.session_state:
    st.session_state.search_history = []

# ============================================
# CSS DARK THEME
# ============================================
st.markdown("""
<style>
    /* === BASE DARK THEME === */
    .stApp {
        background-color: #0a0a0b;
        color: #e5e5e5;
    }

    /* Header principal */
    .app-header {
        padding: 2.5rem 0 1rem 0;
        border-bottom: 1px solid #1e1e21;
        margin-bottom: 2rem;
    }
    .app-title {
        font-size: 1.8rem;
        font-weight: 700;
        color: #fafafa;
        letter-spacing: -0.02em;
        margin: 0;
    }
    .app-subtitle {
        font-size: 0.9rem;
        color: #71717a;
        margin-top: 0.3rem;
    }

    /* Cards */
    .card {
        background: #18181b;
        border: 1px solid #27272a;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        transition: border-color 0.2s ease;
    }
    .card:hover {
        border-color: #3f3f46;
    }
    .card-title {
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #a1a1aa;
        margin-bottom: 1rem;
    }

    /* Stats cards */
    .stat-card {
        background: #18181b;
        border: 1px solid #27272a;
        border-radius: 10px;
        padding: 1.2rem;
        text-align: center;
    }
    .stat-value {
        font-size: 2rem;
        font-weight: 700;
        color: #fafafa;
    }
    .stat-label {
        font-size: 0.75rem;
        color: #71717a;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-top: 0.3rem;
    }

    /* Score badges */
    .score-a { color: #22c55e; }
    .score-b { color: #f59e0b; }
    .score-c { color: #ef4444; }
    .score-d { color: #6b7280; }

    /* Filters summary */
    .filters-summary {
        background: #18181b;
        border: 1px solid #27272a;
        border-radius: 10px;
        padding: 1rem 1.5rem;
        margin: 1rem 0;
    }
    .filter-tag {
        display: inline-block;
        background: #27272a;
        color: #a1a1aa;
        padding: 0.25rem 0.75rem;
        border-radius: 6px;
        font-size: 0.8rem;
        margin: 0.2rem;
    }

    /* History entry */
    .history-entry {
        background: #18181b;
        border: 1px solid #27272a;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        transition: border-color 0.2s ease;
    }
    .history-entry:hover {
        border-color: #3f3f46;
    }
    .history-date {
        font-size: 0.8rem;
        color: #71717a;
    }
    .history-count {
        font-size: 1.1rem;
        font-weight: 600;
        color: #fafafa;
    }

    /* Override Streamlit elements */
    .stSelectbox label, .stNumberInput label, .stCheckbox label {
        color: #a1a1aa !important;
        font-size: 0.85rem !important;
    }

    .stTabs [data-baseweb="tab-list"] {
        background: transparent;
        gap: 0;
        border-bottom: 1px solid #27272a;
    }
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        color: #71717a;
        border: none;
        border-bottom: 2px solid transparent;
        padding: 0.75rem 1.5rem;
        font-weight: 500;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        color: #fafafa;
        border-bottom: 2px solid #fafafa;
        background: transparent;
    }

    .stProgress > div > div {
        background-color: #27272a;
    }
    .stProgress > div > div > div {
        background-color: #3b82f6;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #111113;
        border-right: 1px solid #1e1e21;
    }
    section[data-testid="stSidebar"] .stMarkdown {
        color: #a1a1aa;
    }

    /* Tables */
    .stDataFrame {
        border: 1px solid #27272a;
        border-radius: 8px;
    }

    /* Buttons */
    .stButton > button[kind="primary"] {
        background: #fafafa;
        color: #09090b;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        padding: 0.6rem 1.5rem;
        transition: opacity 0.15s ease;
    }
    .stButton > button[kind="primary"]:hover {
        opacity: 0.9;
        background: #fafafa;
        color: #09090b;
    }
    .stDownloadButton > button {
        background: transparent;
        color: #fafafa;
        border: 1px solid #27272a;
        border-radius: 8px;
        font-weight: 500;
        transition: border-color 0.15s ease;
    }
    .stDownloadButton > button:hover {
        border-color: #3f3f46;
        color: #fafafa;
    }

    /* Expander */
    .streamlit-expanderHeader {
        background: #18181b;
        border: 1px solid #27272a;
        border-radius: 8px;
        color: #a1a1aa;
    }

    /* Metrics */
    [data-testid="stMetricValue"] {
        color: #fafafa;
    }
    [data-testid="stMetricLabel"] {
        color: #71717a;
    }

    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)


def save_to_history(timestamp, filters_text, df, excel_bytes, filename, qualified):
    """Sauvegarde une recherche dans l'historique en session"""
    st.session_state.search_history.insert(0, {
        'timestamp': timestamp,
        'date_str': datetime.now().strftime("%d/%m/%Y %H:%M"),
        'filters': filters_text,
        'count': len(df),
        'scores': df['score'].value_counts().to_dict() if 'score' in df.columns else {},
        'excel_bytes': excel_bytes,
        'filename': filename,
        'qualified': qualified,
    })


def main():
    """Interface principale"""

    # Header
    st.markdown("""
    <div class="app-header">
        <div class="app-title">Prospect Scraper B2B</div>
        <div class="app-subtitle">Data.gouv &middot; Societe.com &middot; Claude IA</div>
    </div>
    """, unsafe_allow_html=True)

    # Sidebar : Configuration
    with st.sidebar:
        st.markdown("### Configuration")

        api_key = st.text_input(
            "Cle API Anthropic",
            value=config.ANTHROPIC_API_KEY or "",
            type="password",
            help="Obtiens ta cle sur console.anthropic.com"
        )

        if not api_key:
            st.warning("Configure ta cle API pour la qualification IA")

        st.markdown("---")
        st.markdown("""
        <div style="color: #52525b; font-size: 0.75rem; line-height: 1.5;">
            <strong>Pipeline</strong><br>
            1. Scraping data.gouv.fr<br>
            2. Enrichissement Societe.com<br>
            3. Qualification IA (Claude)<br>
            4. Export Excel
        </div>
        """, unsafe_allow_html=True)

    # Onglets
    tab1, tab2 = st.tabs(["Nouvelle recherche", "Historique"])

    with tab1:
        run_search_interface(api_key)

    with tab2:
        show_history()


def run_search_interface(api_key: str):
    """Interface de recherche"""

    # Section filtres
    st.markdown('<div class="card-title">Filtres de recherche</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Chiffre d'affaires**")
        ca_min = st.number_input(
            "CA minimum (M)",
            min_value=0.0,
            max_value=1000.0,
            value=5.0,
            step=1.0
        )
        ca_max = st.number_input(
            "CA maximum (M)",
            min_value=0.0,
            max_value=1000.0,
            value=50.0,
            step=1.0
        )

        st.markdown("**Secteur d'activite**")
        secteur_options = ["Tous"] + [f"{code} - {lib}" for code, lib in config.SECTEURS_NAF.items()]
        secteur = st.selectbox("Code NAF", secteur_options)
        secteur_code = None if secteur == "Tous" else secteur.split(" - ")[0]

    with col2:
        st.markdown("**Localisation**")
        region_options = ["Toute la France"] + [f"{code} - {lib}" for code, lib in config.REGIONS.items()]
        region = st.selectbox("Region", region_options)
        region_code = None if region == "Toute la France" else region.split(" - ")[0]

        st.markdown("**Forme juridique**")
        forme_options = ["Toutes", "SAS", "SARL", "SA", "SCI"]
        forme = st.selectbox("Forme juridique", forme_options)
        forme_code = None if forme == "Toutes" else forme

    st.markdown("---")

    col3, col4 = st.columns(2)

    with col3:
        age_min = st.number_input(
            "Age minimum (annees)",
            min_value=0,
            max_value=100,
            value=3
        )

    with col4:
        limit = st.number_input(
            "Nombre max d'entreprises",
            min_value=1,
            max_value=1000,
            value=50,
            help="Pour tests, commence par 10-20"
        )

    # Options avancees
    with st.expander("Options avancees"):
        skip_enrichment = st.checkbox("Sauter l'enrichissement Societe.com", value=False)
        skip_qualification = st.checkbox("Sauter la qualification IA", value=False)

    # Resume filtres
    filters_text = f"CA {ca_min}-{ca_max}M | {region} | {secteur} | {forme} | Age>{age_min}ans | Limit={limit}"

    st.markdown(f"""
    <div class="filters-summary">
        <span class="filter-tag">CA {ca_min}-{ca_max}M</span>
        <span class="filter-tag">{region}</span>
        <span class="filter-tag">{secteur}</span>
        <span class="filter-tag">{forme}</span>
        <span class="filter-tag">Age &gt; {age_min}a</span>
        <span class="filter-tag">Limit {limit}</span>
    </div>
    """, unsafe_allow_html=True)

    # Bouton de lancement
    st.markdown("")
    col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])

    with col_btn2:
        if st.button("Lancer la recherche", type="primary", use_container_width=True):
            run_scraping_pipeline(
                ca_min=ca_min * 1_000_000,
                ca_max=ca_max * 1_000_000,
                region_code=region_code,
                secteur_code=secteur_code,
                forme_code=forme_code,
                age_min=age_min,
                limit=limit,
                api_key=api_key,
                skip_enrichment=skip_enrichment,
                skip_qualification=skip_qualification,
                filters_text=filters_text,
            )


def run_scraping_pipeline(ca_min, ca_max, region_code, secteur_code, forme_code,
                          age_min, limit, api_key, skip_enrichment, skip_qualification,
                          filters_text):
    """Execute le pipeline complet"""

    os.makedirs("outputs", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    config.FILTRES['ca_min'] = ca_min
    config.FILTRES['ca_max'] = ca_max

    filtres = {
        'tranches_effectif': TRANCHES_PME,
        'region': region_code,
        'secteur_naf': secteur_code,
        'forme_juridique': forme_code,
        'age_min': age_min,
        'limit': limit,
    }

    progress_bar = st.progress(0)
    status_text = st.empty()

    try:
        # ETAPE 1 : Scraping Data.gouv
        status_text.markdown("**Etape 1/4** — Recherche sur data.gouv.fr...")
        progress_bar.progress(10)

        scraper = DataGouvScraper()
        companies = scraper.search_companies(filtres)

        if not companies:
            st.error("Aucune entreprise trouvee avec ces criteres")
            return

        df = scraper.to_dataframe(companies)

        progress_bar.progress(25)
        st.success(f"{len(df)} entreprises trouvees sur data.gouv.fr")

        # ETAPE 2 : Enrichissement Societe.com
        if not skip_enrichment:
            status_text.markdown("**Etape 2/4** — Enrichissement Societe.com...")
            progress_bar.progress(30)

            enricher = SocieteEnricher()
            df = enricher.enrich_dataframe(df, filter_ca=True, target_limit=limit)

            progress_bar.progress(55)
            st.success(f"{len(df)} entreprises enrichies")
        else:
            progress_bar.progress(55)
            st.info("Enrichissement saute")

        # ETAPE 3 : Qualification IA
        if not skip_qualification:
            if not api_key:
                st.warning("Cle API manquante : qualification IA sautee")
                skip_qualification = True
            else:
                status_text.markdown("**Etape 3/4** — Qualification IA...")
                progress_bar.progress(60)

                qualifier = ProspectQualifier(api_key)
                df = qualifier.qualify_dataframe(df)

                progress_bar.progress(90)
                st.success("Prospects qualifies")

                # ETAPE 4 : Export final
                status_text.markdown("**Etape 4/4** — Generation du fichier Excel...")

                excel_bytes = qualifier.format_excel_output(df)
                filename = f"prospects_{timestamp}.xlsx"

                progress_bar.progress(100)
                status_text.markdown("**Termine**")

                # Sauvegarde dans l'historique
                save_to_history(timestamp, filters_text, df, excel_bytes, filename, qualified=True)

                # Affichage resultat
                st.markdown("---")

                # Stats
                score_counts = df['score'].value_counts()
                cols = st.columns(4)
                for i, (score, color) in enumerate([('A', '#22c55e'), ('B', '#f59e0b'), ('C', '#ef4444'), ('D', '#6b7280')]):
                    count = score_counts.get(score, 0)
                    cols[i].markdown(f"""
                    <div class="stat-card">
                        <div class="stat-value" style="color: {color};">{count}</div>
                        <div class="stat-label">Score {score}</div>
                    </div>
                    """, unsafe_allow_html=True)

                st.markdown("")

                # Bouton de telechargement
                st.download_button(
                    label="Telecharger le fichier Excel",
                    data=excel_bytes,
                    file_name=filename,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

                # Preview
                st.markdown("")
                st.markdown('<div class="card-title">Apercu des resultats</div>', unsafe_allow_html=True)
                preview_cols = ['score', 'score_label', 'nom_entreprise',
                                'ca_euros', 'evolution_ca', 'ville', 'justification']
                existing_preview = [c for c in preview_cols if c in df.columns]
                st.dataframe(
                    df[existing_preview].head(10),
                    use_container_width=True
                )
                return

        # Si pas de qualification : exporte le fichier enrichi
        progress_bar.progress(90)
        status_text.markdown("**Export du fichier enrichi...**")

        buffer = BytesIO()
        df.to_excel(buffer, index=False, engine='xlsxwriter')
        excel_bytes = buffer.getvalue()
        filename = f"prospects_enriched_{timestamp}.xlsx"

        progress_bar.progress(100)
        status_text.markdown("**Termine** (sans qualification IA)")

        save_to_history(timestamp, filters_text, df, excel_bytes, filename, qualified=False)

        st.markdown("---")
        st.success(f"{len(df)} entreprises trouvees")

        st.download_button(
            label="Telecharger le fichier Excel",
            data=excel_bytes,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"Erreur : {e}")
        import traceback
        st.code(traceback.format_exc())


def show_history():
    """Affiche l'historique des recherches de la session"""

    history = st.session_state.search_history

    if not history:
        st.markdown("""
        <div style="text-align: center; padding: 3rem; color: #52525b;">
            <div style="font-size: 1.2rem; margin-bottom: 0.5rem;">Aucune recherche</div>
            <div style="font-size: 0.85rem;">Lance une recherche pour voir les resultats ici.</div>
        </div>
        """, unsafe_allow_html=True)
        return

    for i, entry in enumerate(history):
        qualified_tag = "IA" if entry['qualified'] else "Enrichi"

        st.markdown(f"""
        <div class="history-entry">
            <div class="history-date">{entry['date_str']} &middot; {qualified_tag}</div>
            <div class="history-count">{entry['count']} entreprises</div>
            <div style="color: #52525b; font-size: 0.8rem; margin-top: 0.3rem;">{entry['filters']}</div>
        </div>
        """, unsafe_allow_html=True)

        # Scores
        if entry['scores']:
            score_cols = st.columns(4)
            scores = entry['scores']
            for j, (score, color) in enumerate([('A', '#22c55e'), ('B', '#f59e0b'), ('C', '#ef4444'), ('D', '#6b7280')]):
                count = scores.get(score, 0)
                score_cols[j].markdown(f'<span style="color:{color};font-weight:700;">{score}: {count}</span>', unsafe_allow_html=True)

        # Download
        st.download_button(
            label="Telecharger Excel",
            data=entry['excel_bytes'],
            file_name=entry['filename'],
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"download_{i}_{entry['timestamp']}",
        )

        st.markdown("---")


if __name__ == "__main__":
    main()
