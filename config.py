"""
Configuration du scraper de prospects B2B
"""
import os

# ============================================
# FILTRES DE RECHERCHE
# ============================================

# Tranches d'effectif INSEE (proxy pour taille entreprise)
# L'API data.gouv ne fournit PAS le CA, on filtre par effectif
TRANCHES_EFFECTIF = {
    '00': '0 salarié',
    '01': '1-2 salariés',
    '02': '3-5 salariés',
    '03': '6-9 salariés',
    '11': '10-19 salariés',
    '12': '20-49 salariés',      # Petite PME
    '21': '50-99 salariés',      # Moyenne PME
    '22': '100-199 salariés',    # Grande PME
    '31': '200-249 salariés',    # ETI
    '32': '250-499 salariés',
    '41': '500-999 salariés',
    '42': '1000+ salariés',
}

FILTRES = {
    # Tranches d'effectif à cibler (codes INSEE)
    # PME typiques avec CA 5-50M€: ['12', '21', '22', '31']
    "tranches_effectif": ['12', '21', '22', '31'],

    # Chiffre d'affaires (filtrage POST-enrichissement Pappers)
    "ca_min": 5_000_000,      # 5 M€
    "ca_max": 50_000_000,     # 50 M€

    # Région (code INSEE)
    # Exemples: "11" (Île-de-France), "84" (Auvergne-Rhône-Alpes)
    # None = toute la France
    "region": None,

    # Secteur d'activité (code NAF)
    # Exemples: "62.01Z" (Informatique), "41" (Construction)
    # None = tous secteurs
    "secteur_naf": None,

    # Forme juridique (dans la query)
    # Exemples: "5710" (SAS), "5720" (SARL)
    # None = toutes formes
    "forme_juridique": None,

    # Limite de résultats
    "limit": 10,

    # Âge minimum de l'entreprise (années)
    "age_min": 0,
}

# ============================================
# CODES RÉGIONS (INSEE)
# ============================================

REGIONS = {
    "11": "Île-de-France",
    "24": "Centre-Val de Loire",
    "27": "Bourgogne-Franche-Comté",
    "28": "Normandie",
    "32": "Hauts-de-France",
    "44": "Grand Est",
    "52": "Pays de la Loire",
    "53": "Bretagne",
    "75": "Nouvelle-Aquitaine",
    "76": "Occitanie",
    "84": "Auvergne-Rhône-Alpes",
    "93": "Provence-Alpes-Côte d'Azur",
    "94": "Corse",
}

# ============================================
# CODES NAF PRINCIPAUX
# ============================================

SECTEURS_NAF = {
    "41": "Construction de bâtiments",
    "42": "Génie civil",
    "43": "Travaux de construction spécialisés",
    "46": "Commerce de gros",
    "47": "Commerce de détail",
    "58": "Édition",
    "62": "Programmation informatique",
    "63": "Services d'information",
    "64": "Activités financières",
    "66": "Activités auxiliaires de services financiers",
    "68": "Activités immobilières",
    "69": "Activités juridiques et comptables",
    "70": "Activités des sièges sociaux ; conseil de gestion",
    "71": "Activités d'architecture et d'ingénierie",
    "72": "Recherche-développement scientifique",
    "73": "Publicité et études de marché",
    "74": "Autres activités spécialisées, scientifiques et techniques",
    "77": "Activités de location et location-bail",
    "78": "Activités liées à l'emploi",
    "85": "Enseignement",
    "86": "Activités pour la santé humaine",
}

# ============================================
# API KEYS
# ============================================

# Clé API Anthropic - Pour développement local, mettez votre clé ici
# Pour Streamlit Cloud, utilisez les secrets (voir .streamlit/secrets.toml)
_LOCAL_API_KEY = ""  # Pour dev local: export ANTHROPIC_API_KEY="ta-cle"

def get_anthropic_key():
    """Récupère la clé API dans l'ordre: env var > streamlit secrets > local"""
    # 1. Variable d'environnement (priorité)
    key = os.environ.get('ANTHROPIC_API_KEY')
    if key:
        return key

    # 2. Streamlit secrets (pour Streamlit Cloud)
    try:
        import streamlit as st
        if hasattr(st, 'secrets') and 'ANTHROPIC_API_KEY' in st.secrets:
            return st.secrets['ANTHROPIC_API_KEY']
    except:
        pass

    # 3. Clé locale (développement uniquement)
    if _LOCAL_API_KEY:
        return _LOCAL_API_KEY

    return ''

ANTHROPIC_API_KEY = get_anthropic_key()

# ============================================
# PARAMÈTRES DE SCRAPING
# ============================================

SCRAPING_CONFIG = {
    # Délai entre requêtes (secondes)
    "delay_between_requests": 2,

    # Timeout des requêtes (secondes)
    "request_timeout": 10,

    # Nombre de tentatives en cas d'échec
    "max_retries": 3,

    # User agent
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

# Sur-fetching : on récupère N fois plus d'entreprises que demandé
# pour compenser les pertes lors du filtrage CA
OVERFETCH_MULTIPLIER = 3

# ============================================
# SCORING IA
# ============================================

SCORING_CATEGORIES = {
    "A": "PME indépendante, rentable, dirigeant fondateur",
    "B": "PME intéressante, 1-2 critères manquants",
    "C": "Trop petite ou signes d'accompagnement existant",
    "D": "Déjà en LBO / fonds au capital / hors cible CA",
}

# ============================================
# WEB SEARCH (QUALIFIER IA)
# ============================================

WEB_SEARCH_CONFIG = {
    # Max recherches web par entreprise
    "max_uses_per_company": 5,

    # Max tokens pour l'appel API qualifier (augmenté pour web search)
    "max_tokens": 4096,

    # Délai entre appels API qualifier (secondes)
    "delay_between_qualifications": 3,

    # Taille du batch avant pause longue
    "batch_size": 3,

    # Durée de la pause après chaque batch (secondes)
    "batch_pause": 5,
}

# ============================================
# FICHIERS DE SORTIE
# ============================================

OUTPUT_CONFIG = {
    "dir": "outputs",
    "filename_raw": "prospects_raw_{timestamp}.xlsx",
    "filename_qualified": "prospects_qualified_{timestamp}.xlsx",
}
