"""
Configuration du scraper de prospects B2B
"""
import os

# ============================================
# FILTRES DE RECHERCHE
# ============================================

TRANCHES_EFFECTIF = {
    '00': '0 salarié',
    '01': '1-2 salariés',
    '02': '3-5 salariés',
    '03': '6-9 salariés',
    '11': '10-19 salariés',
    '12': '20-49 salariés',
    '21': '50-99 salariés',
    '22': '100-199 salariés',
    '31': '200-249 salariés',
    '32': '250-499 salariés',
    '41': '500-999 salariés',
    '42': '1000+ salariés',
}

FILTRES = {
    "tranches_effectif": ['12', '21', '22', '31'],
    "ca_min": 5_000_000,
    "ca_max": 50_000_000,
    "region": None,
    "secteur_naf": None,
    "forme_juridique": None,
    "limit": 10,
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

_LOCAL_API_KEY = ""

def get_anthropic_key():
    """Récupère la clé API dans l'ordre: env var > streamlit secrets > local"""
    key = os.environ.get('ANTHROPIC_API_KEY')
    if key:
        return key
    try:
        import streamlit as st
        if hasattr(st, 'secrets') and 'ANTHROPIC_API_KEY' in st.secrets:
            return st.secrets['ANTHROPIC_API_KEY']
    except:
        pass
    if _LOCAL_API_KEY:
        return _LOCAL_API_KEY
    return ''

ANTHROPIC_API_KEY = get_anthropic_key()

# ============================================
# PARAMÈTRES DE SCRAPING
# ============================================

SCRAPING_CONFIG = {
    "delay_between_requests": 2,
    "request_timeout": 10,
    "max_retries": 3,
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

OVERFETCH_MULTIPLIER = 3

# ============================================
# SCORING IA (sans recherche web - rapide)
# ============================================

SCORING_CATEGORIES = {
    "A": "Prospect prioritaire - PME indépendante rentable",
    "B": "Intéressant - 1-2 critères manquants",
    "C": "Secondaire - Trop petit ou accompagné",
    "D": "Hors cible",
}

QUALIFIER_CONFIG = {
    "max_tokens": 1000,
    "delay_between_calls": 1,
}

# ============================================
# FICHIERS DE SORTIE
# ============================================

OUTPUT_CONFIG = {
    "dir": "outputs",
}
