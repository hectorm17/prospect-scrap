"""
Enrichisseur via API JSON recherche-entreprises.api.gouv.fr
Zéro scraping HTML. Uniquement des appels API → response.json()
"""

import requests
import pandas as pd
import time
import re
from typing import Dict
from urllib.parse import urlparse, unquote, quote
from datetime import datetime
from tqdm import tqdm
import config


class CompanyEnricher:
    """Enrichit les entreprises via API JSON officielle + DuckDuckGo pour site web"""

    API_URL = "https://recherche-entreprises.api.gouv.fr/search"

    DDG_SKIP = [
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
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'fr-FR,fr;q=0.9',
        })

    def enrich(self, siren: str, nom: str = "") -> Dict:
        """Enrichit une entreprise. Zéro scraping HTML."""

        result = {
            'ca_euros': None,
            'resultat_euros': None,
            'evolution_ca': '',
            'dirigeant_enrichi': '',
            'age_dirigeant': None,
            'site_web': '',
            'logo_url': '',
        }

        # --- Appel API JSON ---
        try:
            r = self.session.get(
                self.API_URL,
                params={'q': siren, 'per_page': 1},
                timeout=10,
            )
            r.raise_for_status()
            results = r.json().get('results', [])

            if results and results[0].get('siren') == siren:
                company = results[0]

                # Finances
                finances = company.get('finances', {})
                if finances:
                    years = sorted(finances.keys(), reverse=True)
                    latest = finances[years[0]]
                    ca = latest.get('ca')
                    rn = latest.get('resultat_net')
                    if ca is not None:
                        result['ca_euros'] = ca
                    if rn is not None:
                        result['resultat_euros'] = rn

                    # Evolution CA
                    if len(years) >= 2:
                        ca_prev = finances[years[1]].get('ca')
                        if ca and ca_prev and ca_prev > 0:
                            evo = ((ca - ca_prev) / ca_prev) * 100
                            if evo > 10:
                                trend = "Croissance"
                            elif evo < -10:
                                trend = "Decroissance"
                            else:
                                trend = "Stable"
                            result['evolution_ca'] = f"{trend} ({evo:+.0f}%)"

                # Dirigeant (premiere personne physique)
                for d in company.get('dirigeants', []):
                    if d.get('type_dirigeant') != 'personne physique':
                        continue
                    nom_d = d.get('nom', '')
                    prenoms = d.get('prenoms', '')
                    qualite = d.get('qualite', '')
                    if nom_d:
                        result['dirigeant_enrichi'] = f"{prenoms} {nom_d} ({qualite})".strip()
                    ddn = d.get('date_de_naissance', '')
                    if ddn and len(ddn) >= 4:
                        try:
                            age = datetime.now().year - int(ddn[:4])
                            if 20 <= age <= 95:
                                result['age_dirigeant'] = age
                        except ValueError:
                            pass
                    break

        except Exception as e:
            print(f"  ! API {siren}: {str(e)[:60]}")

        # --- Site web via DuckDuckGo ---
        if nom:
            time.sleep(3)
            result['site_web'] = self._search_website_ddg(nom)

        # --- Logo Clearbit ---
        if result['site_web']:
            try:
                domain = urlparse(result['site_web']).netloc.replace('www.', '')
                if domain:
                    result['logo_url'] = f"https://logo.clearbit.com/{domain}"
            except Exception:
                pass

        return result

    def _search_website_ddg(self, nom_entreprise: str) -> str:
        """Recherche le site web via DuckDuckGo HTML"""
        if not nom_entreprise:
            return ""
        try:
            url = f"https://html.duckduckgo.com/html/?q={quote(nom_entreprise + ' site officiel')}"

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

            # Parse minimal (regex, pas de BeautifulSoup)
            for match in re.finditer(r'uddg=([^&"]+)', resp.text):
                href = unquote(match.group(1))
                if not href.startswith('http'):
                    continue
                if any(d in href.lower() for d in self.DDG_SKIP):
                    continue
                return href

            return ""
        except Exception:
            return ""

    def enrich_dataframe(self, df: pd.DataFrame, filter_ca: bool = True,
                         target_limit: int = None) -> pd.DataFrame:
        """Enrichit un DataFrame via API JSON + DDG."""
        print("\n[Enrichissement] API JSON + recherche site web...")

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
            api_data = self.enrich(siren, nom)
            enriched_row = {**row.to_dict()}

            # Merge : ne remplace que si la valeur API est non-vide/non-None
            for key, val in api_data.items():
                if val is None:
                    # CA/resultat/age : remplace seulement si le champ existant est vide
                    if key in enriched_row and pd.notna(enriched_row.get(key)):
                        continue
                    enriched_row[key] = val
                elif val:
                    enriched_row[key] = val

            enriched_data.append(enriched_row)
            time.sleep(0.2)

        enriched_df = pd.DataFrame(enriched_data)

        sites = enriched_df['site_web'].apply(lambda x: bool(x) if isinstance(x, str) else False).sum() if 'site_web' in enriched_df.columns else 0
        print(f"[OK] {len(enriched_df)} entreprises enrichies ({sites} sites web)\n")

        return enriched_df


# Aliases pour compatibilite
SocieteEnricher = CompanyEnricher
PappersEnricher = CompanyEnricher
Enricher = CompanyEnricher
