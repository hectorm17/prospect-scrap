"""
Prospect Scraper B2B — Interface Streamlit
Design SaaS moderne, clean et minimaliste
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
import os

from scraper import DataGouvScraper, TRANCHES_PME
from enricher import SocieteEnricher
from qualifier import ProspectQualifier
import config

st.set_page_config(
    page_title="Prospect Scraper",
    page_icon="",
    layout="wide",
    initial_sidebar_state="collapsed"
)

if 'search_history' not in st.session_state:
    st.session_state.search_history = []

# ─────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    /* Reset */
    .stApp {
        background: #fafafa;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* ─── Header ─── */
    .header {
        padding: 2rem 0 1.5rem;
        margin-bottom: 2rem;
    }
    .header h1 {
        font-size: 1.75rem;
        font-weight: 700;
        color: #111;
        letter-spacing: -0.03em;
        margin: 0;
    }
    .header p {
        font-size: 0.875rem;
        color: #6b7280;
        margin: 0.25rem 0 0 0;
    }

    /* ─── Section titles ─── */
    .section-title {
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #9ca3af;
        margin: 1.5rem 0 0.75rem 0;
    }

    /* ─── Cards ─── */
    .card {
        background: #fff;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
    }

    /* ─── Filter pills ─── */
    .filter-pills {
        display: flex;
        flex-wrap: wrap;
        gap: 0.4rem;
        margin: 0.75rem 0 1.25rem 0;
    }
    .pill {
        display: inline-flex;
        align-items: center;
        background: #f3f4f6;
        color: #374151;
        padding: 0.3rem 0.75rem;
        border-radius: 100px;
        font-size: 0.75rem;
        font-weight: 500;
    }

    /* ─── Score badges ─── */
    .score-badge {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 28px;
        height: 28px;
        border-radius: 8px;
        font-size: 0.8rem;
        font-weight: 700;
        color: #fff;
    }
    .score-badge.a { background: #16a34a; }
    .score-badge.b { background: #d97706; }
    .score-badge.c { background: #dc2626; }
    .score-badge.d { background: #9ca3af; }

    /* ─── Stat cards ─── */
    .stats-row {
        display: flex;
        gap: 0.75rem;
        margin: 1rem 0;
    }
    .stat-card {
        flex: 1;
        background: #fff;
        border: 1px solid #e5e7eb;
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
    }
    .stat-card .value {
        font-size: 1.75rem;
        font-weight: 700;
        line-height: 1;
    }
    .stat-card .label {
        font-size: 0.7rem;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #9ca3af;
        margin-top: 0.35rem;
    }
    .stat-card.green .value { color: #16a34a; }
    .stat-card.amber .value { color: #d97706; }
    .stat-card.red .value { color: #dc2626; }
    .stat-card.gray .value { color: #9ca3af; }

    /* ─── History cards ─── */
    .history-card {
        background: #fff;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 1.25rem 1.5rem;
        margin-bottom: 0.75rem;
        transition: box-shadow 0.15s ease;
    }
    .history-card:hover {
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    .history-card .meta {
        font-size: 0.75rem;
        color: #9ca3af;
    }
    .history-card .title {
        font-size: 0.95rem;
        font-weight: 600;
        color: #111;
        margin: 0.15rem 0;
    }
    .history-card .filters {
        font-size: 0.75rem;
        color: #6b7280;
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
        color: #9ca3af;
    }
    .empty-state .icon {
        font-size: 2.5rem;
        margin-bottom: 0.75rem;
        opacity: 0.4;
    }
    .empty-state .title {
        font-size: 1rem;
        font-weight: 600;
        color: #6b7280;
    }
    .empty-state .desc {
        font-size: 0.85rem;
        margin-top: 0.25rem;
    }

    /* ─── Streamlit overrides ─── */
    .stSelectbox label, .stNumberInput label, .stCheckbox label, .stTextInput label {
        font-size: 0.8rem !important;
        font-weight: 500 !important;
        color: #374151 !important;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        background: transparent;
        border-bottom: 1px solid #e5e7eb;
        gap: 0;
    }
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        color: #9ca3af;
        border: none;
        border-bottom: 2px solid transparent;
        padding: 0.6rem 1.25rem;
        font-size: 0.85rem;
        font-weight: 500;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        color: #111;
        border-bottom: 2px solid #111;
        background: transparent;
    }

    /* Progress */
    .stProgress > div > div { background-color: #e5e7eb; border-radius: 100px; }
    .stProgress > div > div > div { background-color: #111; border-radius: 100px; }

    /* Primary button */
    .stButton > button[kind="primary"] {
        background: #111;
        color: #fff;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        font-size: 0.85rem;
        padding: 0.6rem 1.5rem;
        transition: background 0.15s ease;
    }
    .stButton > button[kind="primary"]:hover {
        background: #333;
        color: #fff;
    }

    /* Download button */
    .stDownloadButton > button {
        background: #fff;
        color: #111;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        font-weight: 500;
        font-size: 0.85rem;
        transition: border-color 0.15s ease, box-shadow 0.15s ease;
    }
    .stDownloadButton > button:hover {
        border-color: #d1d5db;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        color: #111;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: #fff;
        border-right: 1px solid #e5e7eb;
    }

    /* Expander */
    .streamlit-expanderHeader {
        font-size: 0.85rem;
        font-weight: 500;
        color: #6b7280;
    }

    /* Data table */
    .stDataFrame { border-radius: 8px; overflow: hidden; }

    /* Hide branding */
    #MainMenu, footer, header { visibility: hidden; }

    /* Divider override */
    hr { border-color: #f3f4f6 !important; }
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
    # Header
    st.markdown("""
    <div class="header">
        <h1>Prospect Scraper</h1>
        <p>Trouvez et qualifiez des PME francaises en quelques clics</p>
    </div>
    """, unsafe_allow_html=True)

    # Sidebar — API key
    with st.sidebar:
        st.markdown("#### Parametres")
        api_key = st.text_input(
            "Cle API Anthropic",
            value=config.ANTHROPIC_API_KEY or "",
            type="password",
            help="console.anthropic.com"
        )
        if not api_key:
            st.info("Ajoute ta cle API pour activer la qualification IA")

    # Tabs
    tab1, tab2 = st.tabs(["Recherche", "Historique"])

    with tab1:
        search_tab(api_key)
    with tab2:
        history_tab()


def search_tab(api_key: str):
    # ─── Filters ───
    st.markdown('<div class="section-title">Filtres</div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)

    with col1:
        ca_min = st.number_input("CA min (M)", min_value=0.0, max_value=1000.0, value=5.0, step=1.0)
        ca_max = st.number_input("CA max (M)", min_value=0.0, max_value=1000.0, value=50.0, step=1.0)

    with col2:
        region_options = ["Toute la France"] + [f"{lib}" for _, lib in config.REGIONS.items()]
        region_labels = {lib: code for code, lib in config.REGIONS.items()}
        region = st.selectbox("Region", region_options)
        region_code = region_labels.get(region) if region != "Toute la France" else None

        secteur_options = ["Tous les secteurs"] + [f"{lib}" for _, lib in config.SECTEURS_NAF.items()]
        secteur_labels = {lib: code for code, lib in config.SECTEURS_NAF.items()}
        secteur = st.selectbox("Secteur", secteur_options)
        secteur_code = secteur_labels.get(secteur) if secteur != "Tous les secteurs" else None

    with col3:
        forme_options = ["Toutes", "SAS", "SARL", "SA"]
        forme = st.selectbox("Forme juridique", forme_options)
        forme_code = None if forme == "Toutes" else forme

        limit = st.number_input("Nombre d'entreprises", min_value=1, max_value=500, value=20)

    with st.expander("Plus de filtres"):
        age_min = st.number_input("Age minimum (annees)", min_value=0, max_value=100, value=3)
        skip_enrichment = st.checkbox("Sauter l'enrichissement Societe.com")
        skip_qualification = st.checkbox("Sauter la qualification IA")

    # ─── Summary pills ───
    pills = [f"CA {ca_min:.0f}-{ca_max:.0f}M", region, secteur, forme, f"Limit {limit}"]
    pills_html = ''.join(f'<span class="pill">{p}</span>' for p in pills)
    st.markdown(f'<div class="filter-pills">{pills_html}</div>', unsafe_allow_html=True)

    filters_text = " | ".join(pills)

    # ─── Launch ───
    _, btn_col, _ = st.columns([1, 2, 1])
    with btn_col:
        if st.button("Lancer la recherche", type="primary", use_container_width=True):
            run_pipeline(
                ca_min=ca_min * 1e6, ca_max=ca_max * 1e6,
                region_code=region_code, secteur_code=secteur_code,
                forme_code=forme_code, age_min=age_min, limit=limit,
                api_key=api_key, skip_enrichment=skip_enrichment,
                skip_qualification=skip_qualification, filters_text=filters_text,
            )


def run_pipeline(ca_min, ca_max, region_code, secteur_code, forme_code,
                 age_min, limit, api_key, skip_enrichment, skip_qualification,
                 filters_text):

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

    progress = st.progress(0)
    status = st.empty()

    try:
        # 1 — Scraping
        status.markdown("**Recherche sur data.gouv.fr...**")
        progress.progress(10)
        scraper = DataGouvScraper()
        companies = scraper.search_companies(filtres)

        if not companies:
            st.error("Aucune entreprise trouvee avec ces criteres.")
            return

        df = scraper.to_dataframe(companies)
        progress.progress(25)
        st.success(f"{len(df)} entreprises trouvees")

        # 2 — Enrichissement
        if not skip_enrichment:
            status.markdown("**Enrichissement Societe.com...**")
            progress.progress(30)
            enricher = SocieteEnricher()
            df = enricher.enrich_dataframe(df, filter_ca=True, target_limit=limit)
            progress.progress(55)
            st.success(f"{len(df)} entreprises enrichies")
        else:
            progress.progress(55)

        # 3 — Qualification IA
        if not skip_qualification:
            if not api_key:
                st.warning("Cle API manquante — qualification sautee")
                skip_qualification = True
            else:
                status.markdown("**Qualification IA...**")
                progress.progress(60)
                qualifier = ProspectQualifier(api_key)
                df = qualifier.qualify_dataframe(df)
                progress.progress(90)
                st.success("Prospects qualifies")

                # 4 — Export
                status.markdown("**Generation Excel...**")
                excel_bytes = qualifier.format_excel_output(df)
                filename = f"prospects_{timestamp}.xlsx"
                progress.progress(100)
                status.empty()

                save_to_history(timestamp, filters_text, df, excel_bytes, filename, qualified=True)
                show_results(df, excel_bytes, filename)
                return

        # Without qualification
        progress.progress(90)
        buf = BytesIO()
        df.to_excel(buf, index=False, engine='xlsxwriter')
        excel_bytes = buf.getvalue()
        filename = f"prospects_{timestamp}.xlsx"
        progress.progress(100)
        status.empty()

        save_to_history(timestamp, filters_text, df, excel_bytes, filename, qualified=False)
        show_results(df, excel_bytes, filename)

    except Exception as e:
        st.error(f"Erreur : {e}")
        import traceback
        st.code(traceback.format_exc())


def show_results(df, excel_bytes, filename):
    """Affiche les resultats apres pipeline"""
    st.markdown("---")

    # Score cards
    if 'score' in df.columns:
        counts = df['score'].value_counts()
        st.markdown(f"""
        <div class="stats-row">
            <div class="stat-card green">
                <div class="value">{counts.get('A', 0)}</div>
                <div class="label">Score A</div>
            </div>
            <div class="stat-card amber">
                <div class="value">{counts.get('B', 0)}</div>
                <div class="label">Score B</div>
            </div>
            <div class="stat-card red">
                <div class="value">{counts.get('C', 0)}</div>
                <div class="label">Score C</div>
            </div>
            <div class="stat-card gray">
                <div class="value">{counts.get('D', 0)}</div>
                <div class="label">Score D</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("")
    st.download_button(
        label="Telecharger Excel",
        data=excel_bytes,
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # Preview table
    st.markdown('<div class="section-title">Apercu</div>', unsafe_allow_html=True)

    preview_df = df.copy()

    # Format CA in M for display
    if 'ca_euros' in preview_df.columns:
        preview_df['CA'] = preview_df['ca_euros'].apply(
            lambda x: f"{x/1e6:.1f}M" if pd.notna(x) and isinstance(x, (int, float)) and x > 0 else ""
        )

    # Build preview columns
    cols_map = {
        'score': 'Score',
        'nom_entreprise': 'Entreprise',
        'CA': 'CA',
        'evolution_ca': 'Tendance',
        'ville': 'Ville',
        'url_pappers': 'Pappers',
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
            <div class="icon"></div>
            <div class="title">Aucune recherche</div>
            <div class="desc">Tes resultats apparaitront ici apres une recherche.</div>
        </div>
        """, unsafe_allow_html=True)
        return

    for i, entry in enumerate(history):
        tag = "Qualifie" if entry['qualified'] else "Enrichi"
        scores = entry.get('scores', {})

        scores_html = ""
        if scores:
            colors = {'A': '#16a34a', 'B': '#d97706', 'C': '#dc2626', 'D': '#9ca3af'}
            scores_html = '<div class="scores">' + ''.join(
                f'<span style="color:{colors.get(s, "#9ca3af")}">{s}: {c}</span>'
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
