"""
Scraper pour récupérer les entreprises depuis data.gouv.fr
API: Recherche d'entreprises (Annuaire des Entreprises)

Note: L'API ne fournit PAS les données financières (CA).
On utilise les tranches d'effectif comme proxy pour la taille.
Le CA sera récupéré via Pappers dans l'étape d'enrichissement.
"""

import requests
import pandas as pd
import time
from datetime import datetime
from typing import List, Dict, Optional
from tqdm import tqdm
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


class DataGouvScraper:
    """Scraper pour l'API de l'annuaire des entreprises"""

    BASE_URL = "https://recherche-entreprises.api.gouv.fr/search"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': config.SCRAPING_CONFIG['user_agent']
        })

    def search_companies(self, filtres: Dict) -> List[Dict]:
        """
        Recherche les entreprises selon les filtres

        Paramètres supportés par l'API:
        - activite_principale: Code NAF (ex: "62.01Z")
        - region: Code région INSEE (ex: "11" pour IDF)
        - tranche_effectif_salarie: Codes séparés par virgule
        - etat_administratif: "A" pour actif

        Returns:
            Liste de dictionnaires contenant les infos des entreprises
        """
        print("\n🔍 Recherche d'entreprises sur data.gouv.fr...")

        all_companies = []
        page = 1
        per_page = 25
        limit = filtres.get('limit', 100)
        # Sur-fetcher pour compenser les pertes lors du filtrage CA
        overfetch_limit = int(limit * config.OVERFETCH_MULTIPLIER)

        # Construction des paramètres
        params = {
            'per_page': per_page,
            'etat_administratif': 'A',  # Entreprises actives uniquement
        }

        # Secteur NAF
        if filtres.get('secteur_naf'):
            params['activite_principale'] = filtres['secteur_naf']

        # Région
        if filtres.get('region'):
            params['region'] = filtres['region']

        # Tranches d'effectif (proxy pour taille/CA)
        tranches = filtres.get('tranches_effectif', TRANCHES_PME)
        if tranches:
            params['tranche_effectif_salarie'] = ','.join(tranches)

        # Forme juridique (dans la query)
        query_parts = []
        if filtres.get('forme_juridique'):
            query_parts.append(f"nature_juridique:{filtres['forme_juridique']}")

        params['q'] = ' '.join(query_parts) if query_parts else ''

        print(f"  Filtres: secteur={filtres.get('secteur_naf', 'tous')}, "
              f"région={filtres.get('region', 'toutes')}, "
              f"effectif={tranches}")

        while len(all_companies) < overfetch_limit:
            params['page'] = page

            try:
                response = self.session.get(
                    self.BASE_URL,
                    params=params,
                    timeout=config.SCRAPING_CONFIG['request_timeout']
                )
                response.raise_for_status()
                data = response.json()

                results = data.get('results', [])
                total = data.get('total_results', 0)

                if page == 1:
                    print(f"  📊 {total} entreprises trouvées au total")

                if not results:
                    break

                # Filtre par âge si défini
                filtered = self._filter_by_age(results, filtres)
                all_companies.extend(filtered)

                print(f"  Page {page}: +{len(filtered)} entreprises")

                # Pas de page suivante
                if len(results) < per_page:
                    break

                page += 1
                time.sleep(0.5)  # Respecte l'API

            except Exception as e:
                print(f"❌ Erreur page {page}: {e}")
                break

        # Applique la limite de sur-fetching
        all_companies = all_companies[:overfetch_limit]
        print(f"✅ Total retenu: {len(all_companies)} entreprises\n")
        return all_companies

    def _filter_by_age(self, companies: List[Dict], filtres: Dict) -> List[Dict]:
        """Filtre les entreprises par âge minimum"""
        age_min = filtres.get('age_min', 0)
        if age_min <= 0:
            return companies

        filtered = []
        for company in companies:
            age = self._calculate_age(company)
            if age >= age_min:
                filtered.append(company)
        return filtered
    
    def _calculate_age(self, company: Dict) -> int:
        """Calcule l'âge de l'entreprise en années"""
        try:
            date_creation = company.get('date_creation')
            if not date_creation:
                return 0
            
            creation_year = int(date_creation[:4])
            current_year = datetime.now().year
            return current_year - creation_year
        except:
            return 0
    
    def to_dataframe(self, companies: List[Dict]) -> pd.DataFrame:
        """Convertit les résultats en DataFrame"""
        data = []

        for company in companies:
            try:
                siege = company.get('siege', {})
                tranche_code = company.get('tranche_effectif_salarie', '')

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

                    # Adresse siège
                    'adresse': siege.get('adresse', ''),
                    'code_postal': siege.get('code_postal', ''),
                    'ville': siege.get('libelle_commune', ''),
                    'region': siege.get('region', ''),
                    'adresse_complete': self._build_complete_address(siege),

                    # Dirigeant (si dispo dans l'API)
                    'dirigeant_principal': self._extract_dirigeant(company),

                    # Lien Pappers pour enrichissement
                    'url_pappers': f"https://www.pappers.fr/entreprise/{company.get('siren', '')}",
                }

                data.append(row)
            except Exception as e:
                print(f"⚠️ Erreur parsing entreprise: {e}")
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
        except:
            return ""


def main():
    """Test du scraper"""
    scraper = DataGouvScraper()
    
    # Utilise les filtres du config
    companies = scraper.search_companies(config.FILTRES)
    
    if companies:
        df = scraper.to_dataframe(companies)
        
        # Sauvegarde
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"outputs/data_gouv_raw_{timestamp}.xlsx"
        df.to_excel(output_file, index=False)
        
        print(f"✅ Fichier sauvegardé: {output_file}")
        print(f"📊 {len(df)} entreprises exportées")
    else:
        print("❌ Aucune entreprise trouvée")


if __name__ == "__main__":
    import os
    os.makedirs("outputs", exist_ok=True)
    main()
