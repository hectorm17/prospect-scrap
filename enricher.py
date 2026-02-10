"""
Enrichisseur de données via Societe.com (scraping)
Complète les données de l'API avec : téléphone, email, site web, évolution CA, dirigeant enrichi

Note: CA et age_dirigeant viennent de l'API data.gouv (finances + date_de_naissance)
Societe.com ajoute uniquement les données de contact et la tendance CA.
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
    """Enrichit les données entreprises via scraping Societe.com (complément API)"""

    BASE_URL = "https://www.societe.com/societe"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': config.SCRAPING_CONFIG['user_agent'],
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'fr-FR,fr;q=0.9',
        })

    def enrich_company(self, siren: str, nom: str = "") -> Dict:
        """Enrichit une entreprise avec les données manquantes depuis Societe.com"""
        slug = self._slugify(nom) if nom else "entreprise"
        url = f"{self.BASE_URL}/{slug}-{siren}.html"

        try:
            response = self.session.get(
                url,
                timeout=config.SCRAPING_CONFIG['request_timeout']
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'lxml')

            return {
                'ca_societe': self._extract_ca(soup),
                'telephone': self._extract_telephone(soup),
                'email': self._extract_email(soup),
                'site_web': self._extract_website(soup),
                'evolution_ca': self._extract_ca_evolution(soup),
                'dirigeant_enrichi': self._extract_dirigeant(soup),
            }

        except Exception as e:
            print(f"  ! Erreur {siren}: {str(e)[:50]}")
            return self._empty_data()

    def _slugify(self, text: str) -> str:
        """Convertit un nom en slug URL"""
        if not text:
            return "entreprise"
        slug = text.lower()
        slug = re.sub(r'[^a-z0-9\s-]', '', slug)
        slug = re.sub(r'[\s]+', '-', slug)
        slug = slug.strip('-')
        return slug[:50] if slug else "entreprise"

    def _extract_ca(self, soup: BeautifulSoup) -> Optional[float]:
        """Extrait le CA depuis Societe.com (fallback quand l'API n'a pas le CA)"""
        try:
            html_text = str(soup)
            match = re.search(r'ADSTACK\.data\.chiffre\s*=\s*(\d+)', html_text)
            if match:
                return float(match.group(1))

            patterns = [
                r'"ca"\s*:\s*(\d+)',
                r'"chiffre"\s*:\s*(\d+)',
            ]
            for pattern in patterns:
                match = re.search(pattern, html_text, re.IGNORECASE)
                if match:
                    num = float(match.group(1))
                    if num > 1000:
                        return num
            return None
        except Exception:
            return None

    def _extract_telephone(self, soup: BeautifulSoup) -> str:
        """Extrait le numéro de téléphone"""
        try:
            blocked_numbers = {'0260210000', '0899662006', '0891150515'}

            for link in soup.find_all('a', href=True):
                href = link['href']
                if href.startswith('tel:'):
                    tel = re.sub(r'\D', '', href.replace('tel:', ''))
                    if len(tel) == 10 and tel not in blocked_numbers:
                        return tel

            main_content = soup.find('main') or soup.find('div', {'id': 'main'}) or soup
            for section in main_content.find_all(['div', 'section', 'td']):
                text = section.get_text()
                if any(kw in text.lower() for kw in ['téléphone', 'tel', 'phone', 'contact']):
                    match = re.search(r'0[1-9](?:[\s.-]?\d{2}){4}', text)
                    if match:
                        tel_digits = re.sub(r'\D', '', match.group(0))
                        if len(tel_digits) == 10 and tel_digits not in blocked_numbers:
                            return match.group(0)

            return ""
        except Exception:
            return ""

    def _extract_email(self, soup: BeautifulSoup) -> str:
        """Extrait l'email"""
        try:
            email_link = soup.find('a', href=lambda x: x and 'mailto:' in str(x))
            if email_link:
                email = email_link['href'].replace('mailto:', '').split('?')[0]
                if '@' in email:
                    return email

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
        """Extrait le site web"""
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

            meta = soup.find('meta', {'property': 'og:see_also'})
            if meta and meta.get('content', '').startswith('http'):
                return meta['content']

            return ""
        except Exception:
            return ""

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
                    trend = "Decroissance"
                else:
                    trend = "Stable"

                return f"{trend} ({growth_pct:+.0f}% sur {years_span}a)"

            return ""
        except Exception:
            return ""

    def _extract_dirigeant(self, soup: BeautifulSoup) -> str:
        """Extrait le dirigeant avec sa fonction"""
        try:
            role_keywords = ['Gérant', 'Président', 'Directeur', 'PDG', 'DG', 'Administrateur']
            for p in soup.find_all('p'):
                text = p.get_text(strip=True)
                if any(text.startswith(kw) for kw in role_keywords) and 'Ancien' not in text and 'partant' not in text:
                    role = text.split('Depuis')[0].split('Du ')[0].strip()
                    parent = p.find_parent(['article', 'div', 'section'])
                    if parent:
                        name_elem = parent.find(['h2', 'h3', 'h4', 'a'])
                        if name_elem:
                            name = name_elem.get_text(strip=True)
                            if len(name) > 2 and len(name) < 60 and 'Annonce' not in name and 'BODACC' not in name:
                                return f"{name} ({role})"

            meta = soup.find('meta', {'name': 'description'})
            if meta and 'content' in meta.attrs:
                desc = meta['content']
                match = re.search(r'dirig[ée]+e?\s+par\s+([A-ZÉÈÊËÀÂÄÏÎÔÖÙÛÜ][a-zéèêëàâäïîôöùûü]+(?:\s+[A-ZÉÈÊËÀÂÄÏÎÔÖÙÛÜ][a-zéèêëàâäïîôöùûü]+)+)', desc)
                if match:
                    return match.group(1)

            return ""
        except Exception:
            return ""

    def _empty_data(self) -> Dict:
        """Retourne un dict vide en cas d'erreur"""
        return {
            'ca_societe': None,
            'telephone': '',
            'email': '',
            'site_web': '',
            'evolution_ca': '',
            'dirigeant_enrichi': '',
        }

    def enrich_dataframe(self, df: pd.DataFrame, filter_ca: bool = True,
                         target_limit: int = None) -> pd.DataFrame:
        """
        Enrichit un DataFrame avec les données Societe.com (contact + tendance CA).
        CA et age_dirigeant viennent deja de l'API.

        Args:
            df: DataFrame avec colonnes 'siren' et 'nom_entreprise'
            filter_ca: Si True, filtre par ca_min/ca_max (utilise ca_euros de l'API)
            target_limit: Nombre max d'entreprises a retourner
        """
        print("\n[Enrichissement] Complement Societe.com (tel, email, site web)...")

        # Filtre par CA AVANT enrichissement (economise des requetes)
        if filter_ca and 'ca_euros' in df.columns:
            ca_min = config.FILTRES.get('ca_min', 0)
            ca_max = config.FILTRES.get('ca_max', float('inf'))
            before = len(df)
            df = df[
                (df['ca_euros'].isna()) |
                ((df['ca_euros'] >= ca_min) & (df['ca_euros'] <= ca_max))
            ].copy()
            after = len(df)
            if before != after:
                print(f"  Filtrage CA ({ca_min/1e6:.0f}M-{ca_max/1e6:.0f}M): {before} -> {after}")

        # Tronque au nombre cible AVANT enrichissement
        if target_limit and len(df) > target_limit:
            df = df.head(target_limit).copy()
            print(f"  Limite: {target_limit} entreprises")

        enriched_data = []

        for _, row in tqdm(df.iterrows(), total=len(df), desc="Enrichissement"):
            siren = str(row['siren'])
            nom = row.get('nom_entreprise', '')

            societe_data = self.enrich_company(siren, nom)

            enriched_row = {**row.to_dict()}

            # CA fallback: si l'API n'a pas de CA, utilise Societe.com
            ca_societe = societe_data.pop('ca_societe', None)
            if ca_societe and (not enriched_row.get('ca_euros') or pd.isna(enriched_row.get('ca_euros'))):
                enriched_row['ca_euros'] = ca_societe

            # Merge: ne remplace que si la valeur Societe.com est non-vide
            for key, val in societe_data.items():
                if val:
                    enriched_row[key] = val

            enriched_data.append(enriched_row)

            time.sleep(config.SCRAPING_CONFIG['delay_between_requests'])

        enriched_df = pd.DataFrame(enriched_data)

        print(f"[OK] {len(enriched_df)} entreprises enrichies\n")

        return enriched_df


# Alias pour compatibilite
PappersEnricher = SocieteEnricher
