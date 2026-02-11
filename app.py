"""
Prospect Scraper B2B — Interface Streamlit
Design Mirabaud Banking : bleu marine fonce + or/gold
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
import os

from streamlit_shadcn_ui import metric_card

from scraper import DataGouvScraper, TRANCHES_PME
from enricher import SocieteEnricher
from qualifier import AutoScorer, ProspectQualifier, format_excel_output
import config

st.set_page_config(
    page_title="MiraScrap",
    page_icon="",
    layout="wide",
    initial_sidebar_state="collapsed"
)

if 'search_history' not in st.session_state:
    st.session_state.search_history = []

# ─────────────────────────────────────────────
# CSS — Mirabaud Banking (bleu marine + gold)
# ─────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Crimson+Text:wght@400;600;700&display=swap');

    * { font-family: 'Inter', -apple-system, sans-serif !important; }
    h1, h2, h3 { font-family: 'Crimson Text', serif !important; font-weight: 600 !important; }

    /* ─── Background Mirabaud dark blue ─── */
    .stApp {
        background: linear-gradient(180deg, #0a2540 0%, #1e3a5f 100%);
    }

    /* ─── Hide branding ─── */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header { visibility: hidden; }

    /* ─── Container ─── */
    .block-container {
        padding-top: 2rem;
        max-width: 1400px;
    }

    /* ─── Typography ─── */
    h1 { color: #e8e6e3 !important; font-size: 3.5rem !important; }
    h2, h3 { color: #e8e6e3 !important; }
    h4, h5, h6 { color: #c9a961 !important; }
    p { color: #94a3b8 !important; }
    label {
        color: #e8e6e3 !important;
        font-weight: 500 !important;
        font-size: 14px !important;
        text-transform: uppercase !important;
        letter-spacing: 0.5px !important;
    }

    /* ─── Section titles ─── */
    .section-title {
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: #c9a961;
        margin: 1.5rem 0 0.75rem 0;
    }

    /* ─── Inputs Mirabaud ─── */
    input, select, textarea {
        border-radius: 4px !important;
        border: 1px solid #2d5a8c !important;
        background: #1e3a5f !important;
        color: #e8e6e3 !important;
        padding: 14px !important;
        font-size: 15px !important;
    }

    input:focus, select:focus {
        border-color: #c9a961 !important;
        box-shadow: 0 0 0 2px rgba(201, 169, 97, 0.2) !important;
        outline: none !important;
    }

    .stSelectbox label, .stNumberInput label, .stCheckbox label, .stTextInput label {
        font-size: 13px !important;
        font-weight: 500 !important;
        color: #e8e6e3 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.5px !important;
    }

    .stSelectbox > div > div,
    .stNumberInput > div > div > input,
    .stTextInput > div > div > input {
        background: #1e3a5f !important;
        border: 1px solid #2d5a8c !important;
        border-radius: 4px !important;
        color: #e8e6e3 !important;
    }

    [data-baseweb="select"] { background: #1e3a5f !important; }
    [data-baseweb="select"] * { color: #e8e6e3 !important; }

    button[kind="increment"], button[kind="decrement"] {
        background: #2d5a8c !important;
        color: #e8e6e3 !important;
        border: none !important;
    }
    button[kind="increment"]:hover, button[kind="decrement"]:hover {
        background: #3d6a9c !important;
    }

    /* ─── Filter pills Mirabaud ─── */
    .filter-pills {
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
        margin: 24px 0;
    }
    .pill {
        display: inline-flex;
        align-items: center;
        background: #1e3a5f;
        color: #e8e6e3;
        padding: 10px 20px;
        border-radius: 4px;
        font-size: 13px;
        font-weight: 500;
        border: 1px solid #2d5a8c;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .pill-accent {
        background: #c9a961;
        color: #0a2540;
        border: none;
        font-weight: 600;
    }

    /* ─── Tabs Mirabaud corporate ─── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        background: transparent;
        border-bottom: 2px solid #2d5a8c;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 0;
        padding: 16px 28px;
        background: transparent;
        color: #94a3b8;
        border: none;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 1px;
        font-size: 13px;
    }
    .stTabs [data-baseweb="tab"]:hover {
        color: #c9a961;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background: transparent;
        color: #e8e6e3;
        border-bottom: 3px solid #c9a961;
    }

    /* ─── Progress bar gold ─── */
    .stProgress > div > div { background-color: #2d5a8c; border-radius: 100px; }
    .stProgress > div > div > div {
        background: #c9a961 !important;
        border-radius: 100px;
    }

    /* ─── Primary button — gold CTA ─── */
    .stButton > button[kind="primary"] {
        background: #c9a961 !important;
        color: #0a2540 !important;
        border: none !important;
        border-radius: 4px !important;
        font-weight: 600 !important;
        font-size: 16px !important;
        padding: 16px 32px !important;
        letter-spacing: 0.5px !important;
        text-transform: uppercase !important;
        transition: all 0.3s ease !important;
    }
    .stButton > button[kind="primary"]:hover {
        background: #d4b76d !important;
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(201, 169, 97, 0.3);
    }

    /* ─── Download button ─── */
    .stDownloadButton > button {
        background: #1e3a5f !important;
        color: #e8e6e3 !important;
        border: 1px solid #2d5a8c !important;
        border-radius: 4px !important;
        font-weight: 600 !important;
        font-size: 0.85rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.5px !important;
        transition: all 0.3s ease !important;
    }
    .stDownloadButton > button:hover {
        background: #2d5a8c !important;
        border-color: #c9a961 !important;
        color: #e8e6e3 !important;
    }

    /* ─── Checkbox / Toggle ─── */
    .stCheckbox span { color: #e8e6e3 !important; }
    input[type="checkbox"] {
        width: 20px !important;
        height: 20px !important;
    }

    /* ─── Advanced options container ─── */
    .advanced-container {
        background: #1e3a5f;
        padding: 24px;
        border-radius: 8px;
        border: 1px solid #2d5a8c;
        margin-top: 8px;
    }

    /* ─── History cards ─── */
    .history-card {
        background: #1e3a5f;
        border: 1px solid #2d5a8c;
        border-radius: 8px;
        padding: 1.25rem 1.5rem;
        margin-bottom: 0.75rem;
        transition: border-color 0.3s ease;
    }
    .history-card:hover {
        border-color: #c9a961;
    }
    .history-card .meta {
        font-size: 0.75rem;
        color: #94a3b8;
    }
    .history-card .title {
        font-size: 0.95rem;
        font-weight: 600;
        color: #e8e6e3;
        margin: 0.15rem 0;
    }
    .history-card .filters {
        font-size: 0.75rem;
        color: #94a3b8;
    }
    .history-card .scores {
        display: flex;
        gap: 0.75rem;
        margin-top: 0.5rem;
    }
    .history-card .scores span {
        font-size: 0.75rem;
        font-weight: 600;
    }

    /* ─── Empty state ─── */
    .empty-state {
        text-align: center;
        padding: 4rem 2rem;
        color: #94a3b8;
    }
    .empty-state .title {
        font-size: 1rem;
        font-weight: 600;
        color: #e8e6e3;
    }
    .empty-state .desc {
        font-size: 0.85rem;
        margin-top: 0.25rem;
    }

    /* ─── Data table ─── */
    .stDataFrame { border-radius: 8px; overflow: hidden; }

    /* ─── Divider ─── */
    hr { border-color: #2d5a8c !important; }

    /* ─── Alert ─── */
    .stAlert {
        background: #1e3a5f !important;
        border-left: 4px solid #c9a961 !important;
        color: #e8e6e3 !important;
        border-radius: 4px;
    }

    /* ─── Slider ─── */
    .stSlider > div > div > div { color: #e8e6e3 !important; }
    .stSlider [data-baseweb="slider"] div[role="slider"] {
        background: #c9a961 !important;
    }

    /* ─── Metric cards override ─── */
    [data-testid="stMetricValue"] { color: #e8e6e3 !important; }
</style>
""", unsafe_allow_html=True)


def save_to_history(timestamp, filters_text, df, excel_bytes, filename, qualified):
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
    # ─── Header Mirabaud Banking ───
    st.markdown("""
    <div style="text-align: center; padding: 4rem 0 3rem 0; background: linear-gradient(180deg, rgba(10, 37, 64, 0) 0%, rgba(30, 58, 95, 0.3) 100%);">
        <h1 style="font-size: 4.5rem; font-weight: 700; margin: 0; color: #e8e6e3 !important;
            font-family: 'Crimson Text', serif !important; letter-spacing: 2px;
            -webkit-text-fill-color: #e8e6e3;">
            MiraScrap
        </h1>
        <div style="width: 80px; height: 3px; background: #c9a961; margin: 1.5rem auto;"></div>
        <p style="font-size: 1.2rem; color: #94a3b8 !important; margin-top: 1rem; font-weight: 400; letter-spacing: 0.5px;">
            Trouvez et qualifiez des PME francaises en quelques clics
        </p>
        <p style="font-size: 0.95rem; color: #c9a961 !important; margin-top: 0.5rem; font-weight: 500;
            text-transform: uppercase; letter-spacing: 1px;">
            Powered by Claude AI
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ─── Tabs ───
    tab1, tab2 = st.tabs(["Recherche", "Historique"])

    with tab1:
        search_tab()
    with tab2:
        history_tab()


def search_tab():
    # ─── Filtres ───
    st.markdown("### Criteres de recherche")
    st.markdown("<br>", unsafe_allow_html=True)

    # Ligne 1 : CA
    col1, col2, col_spacer = st.columns([1, 1, 1])
    with col1:
        ca_min = st.number_input("CA min (M)", min_value=0.0, max_value=1000.0, value=5.0, step=0.5)
    with col2:
        ca_max = st.number_input("CA max (M)", min_value=0.0, max_value=1000.0, value=50.0, step=1.0)

    st.markdown("<br>", unsafe_allow_html=True)

    # Ligne 2 : Region et Secteur
    col1, col2, col_spacer = st.columns([1, 1, 1])
    with col1:
        region_options = ["Toute la France"] + [f"{lib}" for _, lib in config.REGIONS.items()]
        region_labels = {lib: code for code, lib in config.REGIONS.items()}
        region = st.selectbox("Region", region_options)
        region_code = region_labels.get(region) if region != "Toute la France" else None
    with col2:
        secteur_options = ["Tous les secteurs"] + [f"{lib}" for _, lib in config.SECTEURS_NAF.items()]
        secteur_labels = {lib: code for code, lib in config.SECTEURS_NAF.items()}
        secteur = st.selectbox("Secteur", secteur_options)
        secteur_code = secteur_labels.get(secteur) if secteur != "Tous les secteurs" else None

    st.markdown("<br>", unsafe_allow_html=True)

    # Ligne 3 : Forme juridique et Nombre
    col1, col2, col_spacer = st.columns([1, 1, 1])
    with col1:
        forme_options = ["Toutes", "SAS", "SARL", "SA"]
        forme = st.selectbox("Forme juridique", forme_options)
        forme_code = None if forme == "Toutes" else forme
    with col2:
        limit = st.number_input("Nombre d'entreprises", min_value=1, max_value=500, value=20)

    st.markdown("<br><br>", unsafe_allow_html=True)

    # ─── Options avancees (checkbox toggle, pas d'expander) ───
    show_advanced = st.checkbox("Afficher les options avancees", value=False, key="show_advanced")

    age_min = 3
    age_dir_min = 0
    age_dir_max = 0
    enable_ia = False
    api_key = ""
    skip_enrichment = False

    if show_advanced:
        st.markdown("<br>", unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            age_min = st.slider("Age minimum entreprise (annees)", 0, 50, 3, key="age_min_entreprise")
        with col2:
            age_dir_min = st.number_input("Age min dirigeant", min_value=0, max_value=90, value=0,
                                          help="0 = pas de filtre", key="age_min_dirigeant")

        st.markdown("<br>", unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            age_dir_max = st.number_input("Age max dirigeant", min_value=0, max_value=90, value=0,
                                          help="0 = pas de filtre", key="age_max_dirigeant")
        with col2:
            pass

        st.markdown("<br>", unsafe_allow_html=True)

        enable_ia = st.checkbox("Qualification IA (Claude)", value=False, key="qualification_ia",
                                help="Analyse intelligente avec scoring A/B/C/D")

        if enable_ia:
            st.markdown("<br>", unsafe_allow_html=True)
            api_key = st.text_input(
                "Cle API Anthropic",
                value=config.ANTHROPIC_API_KEY or "",
                type="password",
                placeholder="sk-ant-api03-...",
                key="api_key",
                help="Obtenez votre cle sur console.anthropic.com",
            )
            if not api_key:
                st.warning("Cle API requise pour activer la qualification IA")

        st.markdown("<br>", unsafe_allow_html=True)

        skip_enrichment = st.checkbox("Sauter l'enrichissement Societe.com", value=False, key="skip_enrichment")

    st.markdown("<br>", unsafe_allow_html=True)

    # ─── Resume des filtres — Mirabaud style badges ───
    pills = [f"CA {ca_min:.0f}-{ca_max:.0f}M", region, secteur, forme]
    if age_dir_min > 0 or age_dir_max > 0:
        dir_range = f"Dirigeant {age_dir_min or '?'}-{age_dir_max or '?'} ans"
        pills.append(dir_range)
    pills_html = ''.join(f'<span class="pill">{p}</span>' for p in pills)
    pills_html += f'<span class="pill pill-accent">{limit} entreprises</span>'
    st.markdown(f'<div class="filter-pills">{pills_html}</div>', unsafe_allow_html=True)

    filters_text = " | ".join(pills + [f"Limit {limit}"])

    # ─── Bouton recherche ───
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Lancer la recherche", type="primary", use_container_width=True):
        run_pipeline(
            ca_min=ca_min * 1e6, ca_max=ca_max * 1e6,
            region_code=region_code, secteur_code=secteur_code,
            forme_code=forme_code, age_min=age_min, limit=limit,
            age_dir_min=age_dir_min, age_dir_max=age_dir_max,
            api_key=api_key, skip_enrichment=skip_enrichment,
            enable_ia=enable_ia, filters_text=filters_text,
        )


def run_pipeline(ca_min, ca_max, region_code, secteur_code, forme_code,
                 age_min, limit, age_dir_min, age_dir_max,
                 api_key, skip_enrichment, enable_ia, filters_text):

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
        'age_dirigeant_min': age_dir_min,
        'age_dirigeant_max': age_dir_max,
        'ca_min': ca_min,
        'ca_max': ca_max,
        'limit': limit,
    }

    progress = st.progress(0)
    status = st.empty()

    try:
        # 1 - Scraping
        status.markdown("**Recherche sur data.gouv.fr...**")
        progress.progress(10)
        scraper = DataGouvScraper()
        companies = scraper.search_companies(filtres)

        if not companies:
            st.error("Aucune entreprise trouvee avec ces criteres.")
            return

        df = scraper.to_dataframe(companies)
        progress.progress(25)

        ca_filled = df['ca_euros'].notna().sum()
        age_filled = df['age_dirigeant'].notna().sum()
        st.success(f"{len(df)} entreprises trouvees (CA: {ca_filled}/{len(df)}, Age dirigeant: {age_filled}/{len(df)})")

        # 2 - Enrichissement (CA deja filtre par le scraper)
        if not skip_enrichment:
            status.markdown("**Enrichissement Societe.com...**")
            progress.progress(30)
            enricher = SocieteEnricher()
            df = enricher.enrich_dataframe(df, filter_ca=False)
            progress.progress(55)
            st.success(f"{len(df)} entreprises enrichies")
        else:
            progress.progress(55)

        # 3 - Scoring
        if enable_ia and api_key:
            status.markdown("**Qualification IA (Claude)...**")
            progress.progress(60)
            qualifier = ProspectQualifier(api_key)
            df = qualifier.qualify_dataframe(df)
            progress.progress(90)
            st.success("Prospects qualifies par IA")
        else:
            status.markdown("**Scoring automatique...**")
            progress.progress(60)
            scorer = AutoScorer()
            df = scorer.score_dataframe(df)
            progress.progress(90)
            st.success("Prospects scores automatiquement")

        # 4 - Export
        status.markdown("**Generation Excel...**")
        excel_bytes = format_excel_output(df)
        filename = f"prospects_{timestamp}.xlsx"
        progress.progress(100)
        status.empty()

        save_to_history(timestamp, filters_text, df, excel_bytes, filename, qualified=enable_ia)
        show_results(df, excel_bytes, filename)

    except Exception as e:
        st.error(f"Erreur : {e}")
        import traceback
        st.code(traceback.format_exc())


def show_results(df, excel_bytes, filename):
    """Affiche les resultats apres pipeline"""
    st.markdown("---")
    st.markdown("### Resultats")

    # ─── Metric cards ───
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        metric_card(
            title="Entreprises",
            content=str(len(df)),
            description="Trouvees et enrichies",
            key="m_total"
        )
    with col2:
        score_a = len(df[df['score'] == 'A']) if 'score' in df.columns else 0
        metric_card(
            title="Score A",
            content=str(score_a),
            description="Prospects prioritaires",
            key="m_score_a"
        )
    with col3:
        ca_moyen = df['ca_euros'].dropna().mean() / 1_000_000 if df['ca_euros'].notna().any() else 0
        metric_card(
            title="CA moyen",
            content=f"{ca_moyen:.1f} M",
            description="Moyenne des prospects",
            key="m_ca"
        )
    with col4:
        age_moyen = df['age_dirigeant'].dropna().mean() if df['age_dirigeant'].notna().any() else 0
        metric_card(
            title="Age dirigeant",
            content=f"{age_moyen:.0f} ans" if age_moyen > 0 else "N/A",
            description="Moyenne",
            key="m_age"
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ─── Download ───
    st.download_button(
        label="Telecharger Excel",
        data=excel_bytes,
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # ─── Preview table ───
    st.markdown('<div class="section-title">Apercu</div>', unsafe_allow_html=True)

    preview_df = df.copy()

    if 'ca_euros' in preview_df.columns:
        preview_df['CA'] = preview_df['ca_euros'].apply(
            lambda x: f"{x/1e6:.1f}M" if pd.notna(x) and isinstance(x, (int, float)) and x > 0 else ""
        )

    preview_df['dirigeant'] = preview_df.apply(
        lambda r: r.get('dirigeant_enrichi') or r.get('dirigeant_principal') or '', axis=1
    )

    preview_df['activite'] = preview_df.apply(
        lambda r: r.get('activite_declaree') or r.get('libelle_naf') or '', axis=1
    )

    cols_map = {
        'score': 'Score',
        'nom_entreprise': 'Entreprise',
        'activite': 'Activite',
        'CA': 'CA',
        'evolution_ca': 'Tendance',
        'dirigeant': 'Dirigeant',
        'age_dirigeant': 'Age',
        'ville': 'Ville',
        'telephone': 'Tel',
        'justification': 'Justification',
    }
    available = {k: v for k, v in cols_map.items() if k in preview_df.columns}
    if available:
        display_df = preview_df[list(available.keys())].rename(columns=available)
        st.dataframe(display_df, use_container_width=True, hide_index=True)


def history_tab():
    history = st.session_state.search_history

    if not history:
        st.markdown("""
        <div class="empty-state">
            <div class="title">Aucune recherche</div>
            <div class="desc">Tes resultats apparaitront ici apres une recherche.</div>
        </div>
        """, unsafe_allow_html=True)
        return

    for i, entry in enumerate(history):
        tag = "Qualifie IA" if entry['qualified'] else "Auto-score"
        scores = entry.get('scores', {})

        scores_html = ""
        if scores:
            colors = {'A': '#4ade80', 'B': '#c9a961', 'C': '#f87171', 'D': '#94a3b8'}
            scores_html = '<div class="scores">' + ''.join(
                f'<span style="color:{colors.get(s, "#94a3b8")}">{s}: {c}</span>'
                for s, c in sorted(scores.items())
            ) + '</div>'

        st.markdown(f"""
        <div class="history-card">
            <div class="meta">{entry['date_str']} &middot; {tag}</div>
            <div class="title">{entry['count']} entreprises</div>
            <div class="filters">{entry['filters']}</div>
            {scores_html}
        </div>
        """, unsafe_allow_html=True)

        st.download_button(
            label="Telecharger",
            data=entry['excel_bytes'],
            file_name=entry['filename'],
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"dl_{i}_{entry['timestamp']}",
        )


if __name__ == "__main__":
    main()
