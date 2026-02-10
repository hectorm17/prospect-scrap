"""
Scraper pour récupérer les entreprises depuis data.gouv.fr
API: Recherche d'entreprises (Annuaire des Entreprises)

IMPORTANT:
- L'API region/departement filtre par TOUT établissement, pas le siège
- On post-filtre par siege.region / siege.departement pour avoir le bon résultat
- activite_principale nécessite le code NAF complet (ex: "62.01Z")
- Pour filtrer par secteur large (2 chiffres), on utilise section_activite_principale
"""

import requests
import pandas as pd
import time
from datetime import datetime
from typing import List, Dict, Optional
import config

# Mapping tranches effectif INSEE -> description
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
    '42': '1000-1999 salariés',
    '51': '2000-4999 salariés',
    '52': '5000-9999 salariés',
    '53': '10000+ salariés',
}

# Tranches recommandées pour PME (CA 5-50M€ typiquement)
TRANCHES_PME = ['12', '21', '22', '31']  # 20-249 salariés

# Mapping code NAF 2 chiffres → section lettre (pour l'API)
# L'API n'accepte pas les codes 2 chiffres, il faut la lettre de section
NAF_TO_SECTION = {
    "41": "F", "42": "F", "43": "F",  # Construction
    "46": "G", "47": "G",  # Commerce
    "58": "J", "62": "J", "63": "J",  # Information/Communication
    "64": "K", "66": "K",  # Finance
    "68": "L",  # Immobilier
    "69": "M", "70": "M", "71": "M", "72": "M", "73": "M", "74": "M",  # Activités spécialisées
    "77": "N", "78": "N",  # Activités de services admin
    "85": "P",  # Enseignement
    "86": "Q",  # Santé
}

# Mapping région INSEE → départements du siège
REGION_DEPARTEMENTS = {
    "11": ["75", "77", "78", "91", "92", "93", "94", "95"],  # Île-de-France
    "24": ["18", "28", "36", "37", "41", "45"],  # Centre-Val de Loire
    "27": ["21", "25", "39", "58", "70", "71", "89", "90"],  # Bourgogne-Franche-Comté
    "28": ["14", "27", "50", "61", "76"],  # Normandie
    "32": ["02", "59", "60", "62", "80"],  # Hauts-de-France
    "44": ["08", "10", "51", "52", "54", "55", "57", "67", "68", "88"],  # Grand Est
    "52": ["44", "49", "53", "72", "85"],  # Pays de la Loire
    "53": ["22", "29", "35", "56"],  # Bretagne
    "75": ["16", "17", "19", "23", "24", "33", "40", "47", "64", "79", "86", "87"],  # Nouvelle-Aquitaine
    "76": ["09", "11", "12", "30", "31", "32", "34", "46", "48", "65", "66", "81", "82"],  # Occitanie
    "84": ["01", "03", "07", "15", "26", "38", "42", "43", "63", "69", "73", "74"],  # Auvergne-Rhône-Alpes
    "93": ["04", "05", "06", "13", "83", "84"],  # PACA
    "94": ["2A", "2B"],  # Corse
}

# Mapping forme juridique texte → codes nature_juridique
FORME_TO_NATURE = {
    "SAS": ["5710"],
    "SARL": ["5499"],
    "SA": ["5505", "5510", "5515", "5520", "5522", "5525", "5530", "5599"],
    "SCI": ["6540"],
}


class DataGouvScraper:
    """Scraper pour l'API de l'annuaire des entreprises"""

    BASE_URL = "https://recherche-entreprises.api.gouv.fr/search"
    MAX_PAGES = 20  # Max pages à parcourir (post-filtering discards many)

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': config.SCRAPING_CONFIG['user_agent']
        })

    def search_companies(self, filtres: Dict) -> List[Dict]:
        """
        Recherche les entreprises selon les filtres.

        Stratégie:
        1. Appel API avec filtres supportés (effectif, NAF, nature juridique)
        2. Post-filtrage par siège.region (l'API filtre par tout établissement)
        3. Post-filtrage par âge
        4. Déduplication par SIREN
        5. Retourne limit * OVERFETCH_MULTIPLIER résultats
        """
        limit = filtres.get('limit', 100) or 100
        overfetch_limit = int(limit * config.OVERFETCH_MULTIPLIER)
        region_code = filtres.get('region')
        target_depts = REGION_DEPARTEMENTS.get(region_code, []) if region_code else []

        print(f"\n[Scraper] Recherche data.gouv.fr...")
        print(f"  Limite cible: {limit} (overfetch: {overfetch_limit})")
        if region_code:
            print(f"  Region: {config.REGIONS.get(region_code, region_code)} → departements siege: {target_depts}")

        # Construction des paramètres API
        params = {
            'per_page': 25,
            'etat_administratif': 'A',
        }

        # Tranches d'effectif
        tranches = filtres.get('tranches_effectif', TRANCHES_PME)
        if tranches:
            params['tranche_effectif_salarie'] = ','.join(tranches)
            print(f"  Effectif: {tranches}")

        # Secteur NAF - l'API veut le code complet ou la section lettre
        secteur = filtres.get('secteur_naf')
        if secteur:
            if '.' in secteur:
                # Code complet (ex: "62.01Z")
                params['activite_principale'] = secteur
                print(f"  NAF: {secteur}")
            elif secteur in NAF_TO_SECTION:
                # Code 2 chiffres → section lettre
                section = NAF_TO_SECTION[secteur]
                params['section_activite_principale'] = section
                print(f"  Section NAF: {secteur} → section {section}")
            else:
                print(f"  NAF {secteur}: non mappable, ignoré")

        # Forme juridique
        forme = filtres.get('forme_juridique')
        if forme and forme in FORME_TO_NATURE:
            params['nature_juridique'] = ','.join(FORME_TO_NATURE[forme])
            print(f"  Forme: {forme} → {FORME_TO_NATURE[forme]}")

        # Pagination et collecte
        all_companies = []
        seen_sirens = set()
        page = 1

        while page <= self.MAX_PAGES:
            params['page'] = page

            try:
                response = self.session.get(
                    self.BASE_URL,
                    params=params,
                    timeout=config.SCRAPING_CONFIG['request_timeout']
                )
                response.raise_for_status()
                data = response.json()

                if 'erreur' in data:
                    print(f"  Erreur API: {data['erreur'][:100]}")
                    break

                results = data.get('results', [])
                total = data.get('total_results', 0)

                if page == 1:
                    print(f"  API: {total} résultats totaux")

                if not results:
                    print(f"  Page {page}: aucun résultat, arrêt")
                    break

                # Post-filtrage par siège
                added = 0
                for company in results:
                    siren = company.get('siren')
                    if not siren or siren in seen_sirens:
                        continue

                    siege = company.get('siege', {})

                    # Filtre région: vérifier le département du SIÈGE
                    if target_depts:
                        siege_dept = siege.get('departement', '')
                        if siege_dept not in target_depts:
                            continue

                    # Filtre NAF 2 chiffres: section est trop large, post-filtre
                    if secteur and not '.' in secteur:
                        company_naf = company.get('activite_principale', '')
                        if not company_naf.startswith(secteur + '.'):
                            continue

                    # Filtre âge
                    age_min = filtres.get('age_min', 0)
                    if age_min > 0:
                        age = self._calculate_age(company)
                        if age < age_min:
                            continue

                    seen_sirens.add(siren)
                    all_companies.append(company)
                    added += 1

                print(f"  Page {page}: {len(results)} résultats API → +{added} retenus (total: {len(all_companies)})")

                # Assez de résultats ?
                if len(all_companies) >= overfetch_limit:
                    break

                # Plus de pages ?
                if len(results) < 25:
                    break

                page += 1
                time.sleep(0.5)

            except Exception as e:
                print(f"  Erreur page {page}: {e}")
                break

        all_companies = all_companies[:overfetch_limit]
        print(f"  Total retenu: {len(all_companies)} entreprises uniques")

        return all_companies

    def _calculate_age(self, company: Dict) -> int:
        """Calcule l'âge de l'entreprise en années"""
        try:
            date_creation = company.get('date_creation')
            if not date_creation:
                return 0
            creation_year = int(date_creation[:4])
            return datetime.now().year - creation_year
        except Exception:
            return 0

    def to_dataframe(self, companies: List[Dict]) -> pd.DataFrame:
        """Convertit les résultats en DataFrame"""
        data = []

        for company in companies:
            try:
                siege = company.get('siege', {})
                tranche_code = company.get('tranche_effectif_salarie', '')

                # Finances (API fournit ca + resultat_net par année)
                ca_euros, resultat_euros = self._extract_finances(company)

                row = {
                    'nom_entreprise': company.get('nom_complet', ''),
                    'siren': company.get('siren', ''),
                    'siret_siege': siege.get('siret', ''),
                    'forme_juridique': company.get('nature_juridique', ''),
                    'code_naf': company.get('activite_principale', ''),
                    'libelle_naf': company.get('libelle_activite_principale', ''),
                    'date_creation': company.get('date_creation', ''),
                    'tranche_effectif': TRANCHES_EFFECTIF.get(tranche_code, tranche_code),
                    'categorie': company.get('categorie_entreprise', ''),

                    # Finances (directement depuis l'API)
                    'ca_euros': ca_euros,
                    'resultat_euros': resultat_euros,

                    # Adresse siège
                    'adresse': siege.get('adresse', ''),
                    'code_postal': siege.get('code_postal', ''),
                    'ville': siege.get('libelle_commune', ''),
                    'departement': siege.get('departement', ''),
                    'region': siege.get('region', ''),
                    'adresse_complete': self._build_complete_address(siege),

                    # Dirigeant + âge (directement depuis l'API)
                    'dirigeant_principal': self._extract_dirigeant(company),
                    'age_dirigeant': self._extract_age_dirigeant(company),

                    # Liens
                    'url_pappers': f"https://www.pappers.fr/entreprise/{company.get('siren', '')}",
                }

                data.append(row)
            except Exception as e:
                print(f"  Erreur parsing: {e}")
                continue

        return pd.DataFrame(data)

    def _build_complete_address(self, siege: Dict) -> str:
        """Construit l'adresse complète depuis les composants du siège"""
        parts = []
        if siege.get('adresse'):
            parts.append(siege['adresse'])
        cp_ville = []
        if siege.get('code_postal'):
            cp_ville.append(siege['code_postal'])
        if siege.get('libelle_commune'):
            cp_ville.append(siege['libelle_commune'])
        if cp_ville:
            parts.append(' '.join(cp_ville))
        return ', '.join(parts) if parts else ''

    def _extract_dirigeant(self, company: Dict) -> str:
        """Extrait le nom du dirigeant principal"""
        try:
            dirigeants = company.get('dirigeants', [])
            if dirigeants:
                premier = dirigeants[0]
                nom = premier.get('nom', '')
                prenom = premier.get('prenoms', '')
                qualite = premier.get('qualite', '')
                return f"{prenom} {nom} ({qualite})".strip()
            return ""
        except Exception:
            return ""

    def _extract_finances(self, company: Dict) -> tuple:
        """Extrait CA et résultat net depuis finances de l'API (année la plus récente)"""
        try:
            finances = company.get('finances', {})
            if not finances:
                return None, None
            latest_year = max(finances.keys())
            year_data = finances[latest_year]
            ca = year_data.get('ca')
            resultat = year_data.get('resultat_net')
            return ca, resultat
        except Exception:
            return None, None

    def _extract_age_dirigeant(self, company: Dict) -> Optional[int]:
        """Extrait l'âge du dirigeant depuis date_de_naissance de l'API (format: '1972-12')"""
        try:
            dirigeants = company.get('dirigeants', [])
            if not dirigeants:
                return None
            date_naissance = dirigeants[0].get('date_de_naissance', '')
            if not date_naissance or len(date_naissance) < 4:
                return None
            birth_year = int(date_naissance[:4])
            age = datetime.now().year - birth_year
            if 20 <= age <= 95:
                return age
            return None
        except Exception:
            return None


def main():
    """Test du scraper"""
    scraper = DataGouvScraper()
    companies = scraper.search_companies(config.FILTRES)

    if companies:
        df = scraper.to_dataframe(companies)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        import os
        os.makedirs("outputs", exist_ok=True)
        output_file = f"outputs/data_gouv_raw_{timestamp}.xlsx"
        df.to_excel(output_file, index=False)

        print(f"\nFichier: {output_file}")
        print(f"{len(df)} entreprises exportées")
    else:
        print("Aucune entreprise trouvée")


if __name__ == "__main__":
    main()
