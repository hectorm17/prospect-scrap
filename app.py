"""
Prospect Scraper B2B — Interface Streamlit
Design SaaS dark mode sobre — palette bleu marine + gris + accent rouge
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
import os

from streamlit_shadcn_ui import metric_card, badges

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
# CSS — Dark mode sobre (bleu marine + gris + rouge)
# ─────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    * { font-family: 'Inter', -apple-system, sans-serif !important; }

    /* ─── Background sobre ─── */
    .stApp {
        background: #0f172a;
    }

    /* ─── Hide branding ─── */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header { visibility: hidden; }

    /* ─── Container ─── */
    .block-container {
        padding-top: 2rem;
        max-width: 1200px;
    }

    /* ─── Typography ─── */
    h1, h2, h3, h4, h5, h6 { color: #e2e8f0 !important; }
    p { color: #94a3b8 !important; }
    label { color: #cbd5e1 !important; font-weight: 500 !important; }

    /* ─── Section titles ─── */
    .section-title {
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #64748b;
        margin: 1.5rem 0 0.75rem 0;
    }

    /* ─── Inputs sobre ─── */
    input, select, textarea {
        border-radius: 8px !important;
        border: 1px solid #334155 !important;
        background: #1e293b !important;
        color: #e2e8f0 !important;
    }

    input:focus, select:focus {
        border-color: #475569 !important;
        box-shadow: 0 0 0 3px rgba(71, 85, 105, 0.1) !important;
    }

    .stSelectbox label, .stNumberInput label, .stCheckbox label, .stTextInput label {
        font-size: 0.8rem !important;
        font-weight: 500 !important;
        color: #cbd5e1 !important;
    }

    .stSelectbox > div > div,
    .stNumberInput > div > div > input,
    .stTextInput > div > div > input {
        background: #1e293b !important;
        border: 1px solid #334155 !important;
        border-radius: 8px !important;
        color: #e2e8f0 !important;
    }

    [data-baseweb="select"] { background: #1e293b !important; }

    button[kind="increment"], button[kind="decrement"] {
        background: transparent !important;
        color: #94a3b8 !important;
    }

    /* ─── Filter pills sobre ─── */
    .filter-pills {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin: 1rem 0 1.5rem 0;
    }
    .pill {
        display: inline-flex;
        align-items: center;
        background: #1e293b;
        color: #94a3b8;
        padding: 8px 16px;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 500;
        border: 1px solid #334155;
    }

    /* ─── Tabs sobre ─── */
    .stTabs [data-baseweb="tab-list"] {
        background: transparent;
        border-bottom: 1px solid #334155;
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        color: #94a3b8;
        border: none;
        border-bottom: 2px solid transparent;
        border-radius: 8px 8px 0 0;
        padding: 12px 24px;
        font-size: 0.85rem;
        font-weight: 500;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background: #1e293b;
        color: #e2e8f0;
        border-bottom: 2px solid #dc2626;
    }

    /* ─── Progress sobre ─── */
    .stProgress > div > div { background-color: #334155; border-radius: 100px; }
    .stProgress > div > div > div {
        background: #dc2626;
        border-radius: 100px;
    }

    /* ─── Primary button — rouge sobre ─── */
    .stButton > button[kind="primary"] {
        background: #dc2626 !important;
        color: #fff !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
        padding: 12px 24px !important;
        transition: all 0.2s ease !important;
    }
    .stButton > button[kind="primary"]:hover {
        background: #b91c1c !important;
        transform: translateY(-1px);
        box-shadow: 0 8px 30px rgba(220, 38, 38, 0.3);
    }

    /* ─── Download button sobre ─── */
    .stDownloadButton > button {
        background: #1e293b !important;
        color: #e2e8f0 !important;
        border: 1px solid #334155 !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: 0.85rem !important;
        transition: all 0.2s ease !important;
    }
    .stDownloadButton > button:hover {
        background: #334155 !important;
        border-color: #475569 !important;
        color: #f1f5f9 !important;
    }

    /* ─── Expander sobre ─── */
    .streamlit-expanderHeader {
        font-size: 0.85rem;
        font-weight: 500;
        color: #e2e8f0 !important;
        background: #1e293b !important;
        border-radius: 8px;
    }

    details {
        border: 1px solid #334155 !important;
        border-radius: 8px !important;
        background: #1e293b !important;
    }

    /* ─── History cards ─── */
    .history-card {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1.25rem 1.5rem;
        margin-bottom: 0.75rem;
        transition: border-color 0.2s ease;
    }
    .history-card:hover {
        border-color: #475569;
    }
    .history-card .meta {
        font-size: 0.75rem;
        color: #64748b;
    }
    .history-card .title {
        font-size: 0.95rem;
        font-weight: 600;
        color: #e2e8f0;
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
        color: #64748b;
    }
    .empty-state .title {
        font-size: 1rem;
        font-weight: 600;
        color: #94a3b8;
    }
    .empty-state .desc {
        font-size: 0.85rem;
        margin-top: 0.25rem;
    }

    /* ─── Data table ─── */
    .stDataFrame { border-radius: 8px; overflow: hidden; }

    /* ─── Divider ─── */
    hr { border-color: #334155 !important; }

    /* ─── Toggle / Checkbox ─── */
    .stCheckbox span { color: #cbd5e1 !important; }

    /* ─── Alert ─── */
    .stAlert { border-radius: 8px; }

    /* ─── Slider ─── */
    .stSlider > div > div > div { color: #cbd5e1 !important; }
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
    # ─── Header sobre ───
    st.markdown("""
    <div style="text-align: center; padding: 3rem 0 2rem 0;">
        <h1 style="font-size: 3.5rem; font-weight: 800; margin: 0;
            background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
            MiraScrap
        </h1>
        <p style="font-size: 1.15rem; color: #94a3b8; margin-top: 0.5rem; font-weight: 500;">
            Trouvez et qualifiez des PME francaises en quelques clics
        </p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        badges(
            badge_list=[
                ("Powered by Claude AI", "outline"),
                ("100% Automatise", "default"),
            ],
            class_name="flex gap-2 justify-center",
            key="header_badges"
        )

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

    # ─── Options avancees ───
    with st.expander("Options avancees", expanded=False):
        st.markdown("<br>", unsafe_allow_html=True)

        age_min = st.slider("Age minimum entreprise (annees)", 0, 50, 3)

        st.markdown("<br>", unsafe_allow_html=True)

        col_dir1, col_dir2 = st.columns(2)
        with col_dir1:
            age_dir_min = st.number_input("Age min dirigeant", min_value=0, max_value=99, value=0, help="0 = pas de filtre")
        with col_dir2:
            age_dir_max = st.number_input("Age max dirigeant", min_value=0, max_value=99, value=0, help="0 = pas de filtre")

        st.markdown("<br>", unsafe_allow_html=True)

        enable_ia = st.toggle(
            "Qualification IA (Claude)",
            value=False,
            help="Scoring automatique par defaut. Active l'IA pour une analyse plus riche (~3s/entreprise)."
        )

        api_key = ""
        if enable_ia:
            st.markdown("---")
            api_key = st.text_input(
                "Cle API Anthropic",
                value=config.ANTHROPIC_API_KEY or "",
                type="password",
                placeholder="sk-ant-api03-...",
                help="Necessaire pour la qualification IA",
            )
            if not api_key:
                st.warning("Cle API requise pour activer la qualification IA")

        st.markdown("<br>", unsafe_allow_html=True)

        skip_enrichment = st.checkbox("Sauter l'enrichissement Societe.com")

    st.markdown("<br>", unsafe_allow_html=True)

    # ─── Resume des filtres ───
    pills = [f"CA {ca_min:.0f}-{ca_max:.0f}M", region, secteur, forme, f"Limit {limit}"]
    if age_dir_min > 0 or age_dir_max > 0:
        dir_range = f"Dirigeant {age_dir_min or '?'}-{age_dir_max or '?'} ans"
        pills.append(dir_range)
    pills_html = ''.join(f'<span class="pill">{p}</span>' for p in pills)
    st.markdown(f'<div class="filter-pills">{pills_html}</div>', unsafe_allow_html=True)

    filters_text = " | ".join(pills)

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

        # 2 - Enrichissement
        if not skip_enrichment:
            status.markdown("**Enrichissement Societe.com...**")
            progress.progress(30)
            enricher = SocieteEnricher()
            df = enricher.enrich_dataframe(df, filter_ca=True, target_limit=limit)
            progress.progress(55)
            st.success(f"{len(df)} entreprises enrichies")
        else:
            df = df[
                (df['ca_euros'].isna()) |
                ((df['ca_euros'] >= ca_min) & (df['ca_euros'] <= ca_max))
            ].copy()
            if len(df) > limit:
                df = df.head(limit)
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
            colors = {'A': '#4ade80', 'B': '#facc15', 'C': '#f87171', 'D': '#94a3b8'}
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
