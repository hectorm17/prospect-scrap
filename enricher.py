"""
Enrichisseur de données via Societe.com (scraping)
Complète : CA, résultat, dirigeants, téléphone, site web

Note: Pappers est bloqué par Cloudflare, on utilise Societe.com
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
from typing import Dict, Optional
from tqdm import tqdm
import config


class SocieteEnricher:
    """Enrichit les données entreprises via scraping Societe.com"""

    BASE_URL = "https://www.societe.com/societe"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': config.SCRAPING_CONFIG['user_agent'],
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'fr-FR,fr;q=0.9',
        })

    def enrich_company(self, siren: str, nom: str = "") -> Dict:
        """
        Enrichit les données d'une entreprise depuis Societe.com

        Args:
            siren: Numéro SIREN de l'entreprise
            nom: Nom de l'entreprise (pour construire l'URL)

        Returns:
            Dictionnaire avec les données enrichies
        """
        # Construit l'URL (format: nom-siren.html)
        slug = self._slugify(nom) if nom else "entreprise"
        url = f"{self.BASE_URL}/{slug}-{siren}.html"

        try:
            response = self.session.get(
                url,
                timeout=config.SCRAPING_CONFIG['request_timeout']
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'lxml')

            data = {
                'ca_euros': self._extract_ca(soup),
                'evolution_ca': self._extract_ca_evolution(soup),
                'resultat_euros': self._extract_resultat(soup),
                'effectif_societe': self._extract_effectif(soup),
                'telephone': self._extract_telephone(soup),
                'email': self._extract_email(soup),
                'site_web': self._extract_website(soup),
                'dirigeant_enrichi': self._extract_dirigeant(soup),
                'activite_desc': self._extract_activite(soup),
            }

            return data

        except Exception as e:
            print(f"  ! Erreur {siren}: {str(e)[:50]}")
            return self._empty_data()

    def _slugify(self, text: str) -> str:
        """Convertit un nom en slug URL"""
        if not text:
            return "entreprise"
        # Supprime les caractères spéciaux, garde lettres/chiffres/tirets
        slug = text.lower()
        slug = re.sub(r'[^a-z0-9\s-]', '', slug)
        slug = re.sub(r'[\s]+', '-', slug)
        slug = slug.strip('-')
        return slug[:50] if slug else "entreprise"

    def _extract_ca(self, soup: BeautifulSoup) -> Optional[float]:
        """Extrait le chiffre d'affaires"""
        try:
            html_text = str(soup)

            # Méthode 1: Variable JavaScript ADSTACK.data.chiffre (le plus fiable)
            match = re.search(r'ADSTACK\.data\.chiffre\s*=\s*(\d+)', html_text)
            if match:
                return float(match.group(1))

            # Méthode 2: Cherche dans les divs avec data-year et data-a (année courante)
            # Pattern: <div>Chiffre d'affaires</div> suivi de <div data-year="2024" data-a>
            ca_label = soup.find('div', string="Chiffre d'affaires")
            if ca_label:
                parent = ca_label.find_parent()
                if parent:
                    ca_div = parent.find('div', attrs={'data-a': True})
                    if ca_div:
                        span = ca_div.find('span', class_='xDpNbr')
                        if span:
                            val = span.get_text(strip=True)
                            val = re.sub(r'[^\d,.]', '', val).replace(',', '.')
                            if val:
                                return float(val)

            return None
        except:
            return None

    def _extract_ca_evolution(self, soup: BeautifulSoup) -> str:
        """Extrait l'évolution du CA sur plusieurs années"""
        try:
            ca_values = {}
            ca_label = soup.find('div', string="Chiffre d'affaires")
            if ca_label:
                parent = ca_label.find_parent()
                if parent:
                    for div in parent.find_all('div', attrs={'data-year': True}):
                        year = div.get('data-year', '')
                        span = div.find('span', class_='xDpNbr')
                        if span:
                            val = span.get_text(strip=True)
                            val = re.sub(r'[^\d,.]', '', val).replace(',', '.')
                            if val:
                                try:
                                    ca_values[year] = float(val)
                                except ValueError:
                                    pass

            if len(ca_values) < 2:
                return ""

            sorted_years = sorted(ca_values.keys())
            latest = ca_values[sorted_years[-1]]
            earliest = ca_values[sorted_years[0]]

            if earliest > 0:
                growth_pct = ((latest - earliest) / earliest) * 100
                years_span = len(sorted_years) - 1
                if growth_pct > 10:
                    trend = "Croissance"
                elif growth_pct < -10:
                    trend = "Décroissance"
                else:
                    trend = "Stable"

                values_str = ', '.join(
                    f"{y}: {ca_values[y]/1e6:.1f}M€" for y in sorted_years[-3:]
                )
                return f"{trend} ({growth_pct:+.0f}% sur {years_span}a) - {values_str}"

            return ""
        except Exception:
            return ""

    def _extract_resultat(self, soup: BeautifulSoup) -> Optional[float]:
        """Extrait le résultat net"""
        try:
            # Cherche "Résultat" ou "Bénéfice"
            for elem in soup.find_all('div'):
                text = elem.get_text()
                if 'sultat' in text or 'Bénéfice' in text:
                    next_elem = elem.find_next('span', class_='xDpNbr')
                    if next_elem:
                        val = next_elem.get_text(strip=True)
                        val = val.replace('\xa0', '').replace(' ', '')
                        val = val.replace('€', '').replace(',', '.')
                        if val and val != 'NC':
                            return float(val)
            return None
        except:
            return None

    def _extract_effectif(self, soup: BeautifulSoup) -> str:
        """Extrait l'effectif"""
        try:
            for elem in soup.find_all(['div', 'span', 'td']):
                text = elem.get_text()
                if 'Effectif' in text and 'salarié' in text.lower():
                    # Extrait le nombre
                    match = re.search(r'(\d+)', text)
                    if match:
                        return f"{match.group(1)} salariés"
            return ""
        except:
            return ""

    def _extract_telephone(self, soup: BeautifulSoup) -> str:
        """Extrait le numéro de téléphone"""
        try:
            html_text = str(soup)
            # Cherche un pattern téléphone français
            match = re.search(r'0[1-9](?:[\s.-]?\d{2}){4}', html_text)
            if match:
                tel = match.group(0)
                # Vérifie que ce n'est pas un SIREN/SIRET
                if len(re.sub(r'\D', '', tel)) == 10:
                    return tel
            return ""
        except:
            return ""

    def _extract_email(self, soup: BeautifulSoup) -> str:
        """Extrait l'email - essaie mailto puis regex dans le HTML"""
        try:
            # Méthode 1: liens mailto
            email_link = soup.find('a', href=lambda x: x and 'mailto:' in str(x))
            if email_link:
                email = email_link['href'].replace('mailto:', '').split('?')[0]
                if '@' in email:
                    return email

            # Méthode 2: regex email dans le HTML
            html_text = str(soup)
            email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
            matches = re.findall(email_pattern, html_text)
            blocked = ['example.com', 'societe.com', 'placeholder', 'schema.org']
            for match in matches:
                if not any(d in match for d in blocked):
                    return match

            return ""
        except Exception:
            return ""

    def _extract_website(self, soup: BeautifulSoup) -> str:
        """Extrait le site web depuis les liens externes de la page"""
        try:
            skip_domains = [
                'societe.com', 'facebook.com', 'twitter.com', 'linkedin.com',
                'instagram.com', 'youtube.com', 'google.com', 'pappers.fr',
                'infogreffe.fr', 'bodacc.fr', 'data.gouv.fr',
            ]
            for link in soup.find_all('a', href=True):
                href = link['href']
                if not href.startswith('http'):
                    continue
                if any(d in href for d in skip_domains):
                    continue
                if 'mailto:' in href or '#' == href:
                    continue
                rel = link.get('rel', [])
                if 'nofollow' in rel or 'external' in rel:
                    return href

            # Méthode 2: og:see_also meta
            meta = soup.find('meta', {'property': 'og:see_also'})
            if meta and meta.get('content', '').startswith('http'):
                return meta['content']

            return ""
        except Exception:
            return ""

    def _extract_dirigeant(self, soup: BeautifulSoup) -> str:
        """Extrait le dirigeant avec sa fonction"""
        try:
            for elem in soup.find_all(['div', 'section']):
                text = elem.get_text()
                if 'Dirigeant' in text:
                    name_elem = elem.find_next('a')
                    if name_elem and '/dirigeant/' in str(name_elem.get('href', '')):
                        name = name_elem.get_text(strip=True)
                        # Cherche la fonction dans un élément voisin
                        function_elem = name_elem.find_next(['span', 'div'])
                        if function_elem:
                            func_text = function_elem.get_text(strip=True)
                            keywords = ['Président', 'Directeur', 'Gérant',
                                        'PDG', 'CEO', 'DG', 'Administrateur',
                                        'Fondateur']
                            for kw in keywords:
                                if kw.lower() in func_text.lower():
                                    return f"{name} ({func_text})"
                        return name
            return ""
        except Exception:
            return ""

    def _extract_activite(self, soup: BeautifulSoup) -> str:
        """Extrait la description de l'activité"""
        try:
            meta = soup.find('meta', {'name': 'description'})
            if meta and 'content' in meta.attrs:
                return meta['content'][:100]
            return ""
        except:
            return ""

    def _empty_data(self) -> Dict:
        """Retourne un dict vide en cas d'erreur"""
        return {
            'ca_euros': None,
            'evolution_ca': '',
            'resultat_euros': None,
            'effectif_societe': '',
            'telephone': '',
            'email': '',
            'site_web': '',
            'dirigeant_enrichi': '',
            'activite_desc': '',
        }

    def enrich_dataframe(self, df: pd.DataFrame, filter_ca: bool = True,
                         target_limit: int = None) -> pd.DataFrame:
        """
        Enrichit un DataFrame complet

        Args:
            df: DataFrame avec colonnes 'siren' et 'nom_entreprise'
            filter_ca: Si True, filtre par ca_min/ca_max après enrichissement

        Returns:
            DataFrame enrichi (et filtré si filter_ca=True)
        """
        print("\n[Enrichissement] Récupération des données depuis Societe.com...")

        enriched_data = []
        ca_min = config.FILTRES.get('ca_min', 0)
        ca_max = config.FILTRES.get('ca_max', float('inf'))

        for idx, row in tqdm(df.iterrows(), total=len(df), desc="Enrichissement"):
            siren = str(row['siren'])
            nom = row.get('nom_entreprise', '')

            # Enrichit via Societe.com
            societe_data = self.enrich_company(siren, nom)

            # Fusionne les données
            enriched_row = {**row.to_dict(), **societe_data}
            enriched_data.append(enriched_row)

            # Délai entre requêtes (respecte le serveur)
            time.sleep(config.SCRAPING_CONFIG['delay_between_requests'])

        enriched_df = pd.DataFrame(enriched_data)

        # Filtre par CA si demandé
        if filter_ca:
            before = len(enriched_df)
            # Garde les entreprises avec CA dans la fourchette OU CA non disponible
            enriched_df = enriched_df[
                (enriched_df['ca_euros'].isna()) |
                ((enriched_df['ca_euros'] >= ca_min) & (enriched_df['ca_euros'] <= ca_max))
            ]
            after = len(enriched_df)
            if before != after:
                print(f"  Filtrage CA ({ca_min/1e6:.0f}M-{ca_max/1e6:.0f}M): {before} -> {after} entreprises")

        # Tronque au nombre cible si spécifié
        if target_limit and len(enriched_df) > target_limit:
            enriched_df = enriched_df.head(target_limit)
            print(f"  Limite appliquée: {target_limit} entreprises retenues")

        print(f"[OK] {len(enriched_df)} entreprises enrichies\n")

        return enriched_df


# Alias pour compatibilité avec le code existant
PappersEnricher = SocieteEnricher


def main():
    """Test de l'enrichisseur"""
    import glob
    import os

    files = glob.glob("outputs/data_gouv_raw_*.xlsx")
    if not files:
        print("Aucun fichier data_gouv trouve. Lance d'abord scraper.py")
        return

    latest = max(files, key=os.path.getctime)
    print(f"Chargement: {latest}")

    df = pd.read_excel(latest)
    df_test = df.head(3)  # Limite pour test

    enricher = SocieteEnricher()
    enriched_df = enricher.enrich_dataframe(df_test, filter_ca=False)

    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"outputs/enriched_{timestamp}.xlsx"
    enriched_df.to_excel(output_file, index=False)

    print(f"Fichier sauvegarde: {output_file}")
    print(enriched_df[['nom_entreprise', 'ca_euros', 'telephone', 'site_web']].to_string())


if __name__ == "__main__":
    main()
