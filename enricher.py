"""
Enrichisseur de donnees via l'API JSON annuaire-entreprises.
Utilise recherche-entreprises.api.gouv.fr/search?q={siren} pour recuperer
les donnees detaillees d'une entreprise (finances, dirigeants, siege).

Recherche du site web via DuckDuckGo HTML en complement.
Logo via Clearbit si site web trouve.
"""

import requests
import pandas as pd
import time
import re
from typing import Dict, Optional
from urllib.parse import urlparse, unquote, quote
from datetime import datetime
from tqdm import tqdm
import config


class Enricher:
    """Enrichit les donnees entreprises via API JSON + recherche site web DDG"""

    API_URL = "https://recherche-entreprises.api.gouv.fr/search"

    DDG_SKIP_DOMAINS = [
        'societe.com', 'pappers.fr', 'infogreffe.fr', 'data.gouv.fr',
        'facebook.com', 'twitter.com', 'linkedin.com', 'instagram.com',
        'youtube.com', 'google.com', 'wikipedia.org', 'verif.com',
        'manageo.fr', 'pagesjaunes.fr', 'annuaire.com', 'duckduckgo.com',
        'entreprises.lefigaro.fr', 'bing.com', 'bodacc.fr', 'xerfi.com',
        'kompass.com', 'ellisphere.com', 'amazon.', 'tiktok.com',
    ]

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': config.SCRAPING_CONFIG['user_agent'],
        })
        self._ddg_session = requests.Session()
        self._ddg_session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
        })

    def enrich_company(self, siren: str, nom: str = "") -> Dict:
        """Enrichit une entreprise via API JSON + DDG pour le site web"""

        data = self._empty_data()

        # Etape 1 : API JSON pour finances + dirigeants
        try:
            resp = self.session.get(
                self.API_URL,
                params={'q': siren, 'per_page': 1},
                timeout=config.SCRAPING_CONFIG['request_timeout'],
            )
            resp.raise_for_status()
            results = resp.json().get('results', [])

            if results:
                company = results[0]
                if company.get('siren') == siren:
                    data.update(self._parse_api_data(company))

        except Exception as e:
            print(f"  ! API {siren}: {str(e)[:50]}")

        # Etape 2 : Site web via DuckDuckGo
        if not data.get('site_web') and nom:
            time.sleep(3)
            data['site_web'] = self._search_website_ddg(nom)

        # Etape 3 : Logo via Clearbit
        site_web = data.get('site_web', '')
        if site_web:
            try:
                domain = urlparse(site_web).netloc.replace('www.', '')
                if domain:
                    data['logo_url'] = f"https://logo.clearbit.com/{domain}"
            except Exception:
                pass

        return data

    def _parse_api_data(self, company: Dict) -> Dict:
        """Parse les donnees de l'API JSON en champs enrichis"""
        result = {}

        # Finances : CA + resultat net (annee la plus recente)
        finances = company.get('finances', {})
        if finances:
            latest_year = max(finances.keys())
            year_data = finances[latest_year]
            ca = year_data.get('ca')
            resultat = year_data.get('resultat_net')
            if ca is not None:
                result['ca_api'] = ca
            if resultat is not None:
                result['resultat_api'] = resultat

            # Evolution CA sur les annees disponibles
            result['evolution_ca'] = self._calc_evolution(finances)

        # Dirigeant principal (personne physique uniquement)
        dirigeants = company.get('dirigeants', [])
        for d in dirigeants:
            if d.get('type_dirigeant') != 'personne physique':
                continue
            nom_d = d.get('nom', '')
            prenoms = d.get('prenoms', '')
            qualite = d.get('qualite', '')
            if nom_d:
                result['dirigeant_enrichi'] = f"{prenoms} {nom_d} ({qualite})".strip()

            # Age dirigeant
            date_naissance = d.get('date_de_naissance', '')
            if date_naissance and len(date_naissance) >= 4:
                try:
                    birth_year = int(date_naissance[:4])
                    age = datetime.now().year - birth_year
                    if 20 <= age <= 95:
                        result['age_dirigeant_api'] = age
                except ValueError:
                    pass
            break  # Premier dirigeant physique uniquement

        return result

    def _calc_evolution(self, finances: Dict) -> str:
        """Calcule l'evolution du CA sur les annees disponibles"""
        try:
            ca_by_year = {}
            for year, data in finances.items():
                ca = data.get('ca')
                if ca is not None and ca > 0:
                    ca_by_year[year] = ca

            if len(ca_by_year) < 2:
                return ""

            sorted_years = sorted(ca_by_year.keys())
            latest = ca_by_year[sorted_years[-1]]
            earliest = ca_by_year[sorted_years[0]]

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

    def _search_website_ddg(self, nom_entreprise: str) -> str:
        """Recherche le site web via DuckDuckGo HTML"""
        if not nom_entreprise:
            return ""

        try:
            query = f"{nom_entreprise} site officiel"
            url = f"https://html.duckduckgo.com/html/?q={quote(query)}"

            for attempt in range(2):
                resp = self._ddg_session.get(url, timeout=8)
                if resp.status_code == 200:
                    break
                if resp.status_code == 202 and attempt == 0:
                    time.sleep(5)
                    continue
                return ""

            if resp.status_code != 200:
                return ""

            # Parse DDG results (HTML minimal, pas besoin de lxml)
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, 'html.parser')

            for a in soup.find_all('a', href=True):
                href = a['href']
                if 'uddg=' in href:
                    match = re.search(r'uddg=([^&]+)', href)
                    if match:
                        href = unquote(match.group(1))

                if not href.startswith('http'):
                    continue
                if any(d in href.lower() for d in self.DDG_SKIP_DOMAINS):
                    continue

                return href

            return ""
        except Exception:
            return ""

    def _empty_data(self) -> Dict:
        return {
            'site_web': '',
            'logo_url': '',
            'evolution_ca': '',
            'dirigeant_enrichi': '',
        }

    def enrich_dataframe(self, df: pd.DataFrame, filter_ca: bool = True,
                         target_limit: int = None) -> pd.DataFrame:
        """
        Enrichit un DataFrame via API JSON + DDG.
        Complete les champs manquants (CA, dirigeant, site web, logo).
        """
        print("\n[Enrichissement] API JSON + recherche site web...")

        # Filtre par CA AVANT enrichissement
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

        if target_limit and len(df) > target_limit:
            df = df.head(target_limit).copy()
            print(f"  Limite: {target_limit} entreprises")

        enriched_data = []

        for _, row in tqdm(df.iterrows(), total=len(df), desc="Enrichissement"):
            siren = str(row['siren'])
            nom = row.get('nom_entreprise', '')

            api_data = self.enrich_company(siren, nom)

            enriched_row = {**row.to_dict()}

            # CA fallback : si le scraper n'a pas de CA, utiliser l'API enrichissement
            ca_api = api_data.pop('ca_api', None)
            if ca_api and (not enriched_row.get('ca_euros') or pd.isna(enriched_row.get('ca_euros'))):
                enriched_row['ca_euros'] = ca_api

            # Resultat fallback
            resultat_api = api_data.pop('resultat_api', None)
            if resultat_api and (not enriched_row.get('resultat_euros') or pd.isna(enriched_row.get('resultat_euros'))):
                enriched_row['resultat_euros'] = resultat_api

            # Age dirigeant fallback
            age_api = api_data.pop('age_dirigeant_api', None)
            if age_api and (not enriched_row.get('age_dirigeant') or pd.isna(enriched_row.get('age_dirigeant'))):
                enriched_row['age_dirigeant'] = age_api

            # Merge autres champs (site_web, logo_url, evolution_ca, dirigeant)
            for key, val in api_data.items():
                if val:
                    enriched_row[key] = val

            enriched_data.append(enriched_row)

            time.sleep(0.3)  # API JSON = rapide, pas besoin de gros delay

        enriched_df = pd.DataFrame(enriched_data)

        sites_found = enriched_df['site_web'].apply(lambda x: bool(x) if isinstance(x, str) else False).sum() if 'site_web' in enriched_df.columns else 0
        print(f"[OK] {len(enriched_df)} entreprises enrichies ({sites_found} sites web trouves)\n")

        return enriched_df


# Aliases pour compatibilite avec le reste du code
SocieteEnricher = Enricher
PappersEnricher = Enricher
