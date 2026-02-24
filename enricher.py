"""
Enrichisseur via API JSON recherche-entreprises.api.gouv.fr
+ Recherche site web multi-methodes (DDG, domain guessing)
"""

import requests
import pandas as pd
import time
import re
from typing import Dict
from urllib.parse import urlparse, unquote, quote, parse_qs
from datetime import datetime
from tqdm import tqdm
import config


class CompanyEnricher:
    """Enrichit les entreprises via API JSON officielle + recherche site web"""

    API_URL = "https://recherche-entreprises.api.gouv.fr/search"

    SKIP_DOMAINS = [
        'societe.com', 'pappers.fr', 'infogreffe.fr', 'data.gouv.fr',
        'facebook.com', 'twitter.com', 'linkedin.com', 'instagram.com',
        'youtube.com', 'google.com', 'wikipedia.org', 'verif.com',
        'manageo.fr', 'pagesjaunes.fr', 'annuaire.com', 'duckduckgo.com',
        'entreprises.lefigaro.fr', 'bing.com', 'bodacc.fr', 'xerfi.com',
        'kompass.com', 'ellisphere.com', 'amazon.', 'tiktok.com',
        'indeed.com', 'glassdoor', 'welcometothejungle', 'inpi.fr',
    ]

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': config.SCRAPING_CONFIG['user_agent'],
        })
        self._web_session = requests.Session()
        self._web_session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'fr-FR,fr;q=0.9',
        })

    def enrich(self, siren: str, nom: str = "", ville: str = "") -> Dict:
        """Enrichit une entreprise via API JSON + recherche site web."""

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

        # --- Recherche site web (multi-methodes) ---
        if nom:
            result['site_web'] = self.find_website(nom, ville)

        # --- Logo (CompanyEnrich > Clearbit > Google Favicon) ---
        if result['site_web']:
            try:
                domain = urlparse(result['site_web']).netloc.replace('www.', '')
                if domain:
                    result['logo_url'] = f"https://img.companyenrich.com/logo?domain={domain}&format=png"
            except Exception:
                pass

        return result

    # ================================================================
    # RECHERCHE SITE WEB — 3 methodes en cascade
    # ================================================================

    def find_website(self, nom_entreprise: str, ville: str = "") -> str:
        """Cherche le site web avec plusieurs methodes en cascade."""

        nom_court = nom_entreprise.split('(')[0].strip()
        sigles = self._extract_sigles(nom_entreprise)
        print(f"[SITE] Recherche pour: {nom_court} (sigles={sigles}, ville={ville})")

        # Methode 1 : DDG avec nom exact + "site officiel"
        site = self._search_ddg(f'"{nom_court}" site officiel')
        if site:
            print(f"[SITE] TROUVE via DDG nom: {site}")
            return site

        time.sleep(1)

        # Methode 2 : DDG avec sigle si present (ex: SNSM, CCF)
        for sigle in sigles:
            if sigle != nom_court:
                site = self._search_ddg(f'{sigle} site officiel')
                if site:
                    print(f"[SITE] TROUVE via DDG sigle '{sigle}': {site}")
                    return site
                time.sleep(1)

        # Methode 3 : DDG avec nom + ville
        if ville:
            site = self._search_ddg(f'{nom_court} {ville}')
            if site:
                print(f"[SITE] TROUVE via DDG nom+ville: {site}")
                return site
            time.sleep(1)

        # Methode 4 : Deviner le domaine
        for sigle in sigles:
            site = self._guess_domain(sigle)
            if site:
                print(f"[SITE] TROUVE via guess sigle '{sigle}': {site}")
                return site

        site = self._guess_domain(nom_court)
        if site:
            print(f"[SITE] TROUVE via guess nom: {site}")
            return site

        print(f"[SITE] ECHEC: aucun site pour {nom_court}")
        return ""

    def _extract_sigles(self, nom: str) -> list:
        """Extrait les sigles depuis 'NOM COMPLET (SIGLE)' ou 'NOM (A-B)'.
        Retourne une liste ordonnee par priorite."""
        NOISE = {'de', 'des', 'du', 'la', 'le', 'les', 'en', 'et', 'au',
                 'aux', 'sur', 'par', 'pour', 'banque', 'societe', 'groupe',
                 'nationale', 'pays', 'france'}
        match = re.search(r'\(([^)]+)\)', nom)
        if not match:
            return []
        inner = match.group(1).strip()
        sigles = []
        # Separer par tirets (pas espaces) — "VYV3-PDL" → ["VYV3", "PDL"]
        parts = re.split(r'\s*-\s*', inner)
        for p in parts:
            p = p.strip()
            # Garder les sigles courts (2-12 chars), ignorer les mots courants
            if 2 <= len(p) <= 12 and p.lower() not in NOISE:
                if p not in sigles:
                    sigles.append(p)
        return sigles

    def _extract_sigle(self, nom: str) -> str:
        """Retourne le premier sigle (compat)."""
        sigles = self._extract_sigles(nom)
        return sigles[0] if sigles else ""

    def _search_ddg(self, query: str) -> str:
        """Recherche DuckDuckGo HTML, retourne le premier resultat pertinent."""
        try:
            url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
            print(f"  [DDG] query='{query}'")

            for attempt in range(2):
                resp = self._web_session.get(url, timeout=8)
                print(f"  [DDG] status={resp.status_code} len={len(resp.text)} attempt={attempt}")
                if resp.status_code == 200:
                    break
                if resp.status_code == 202 and attempt == 0:
                    time.sleep(5)
                    continue
                return ""

            if resp.status_code != 200:
                return ""

            matches = list(re.finditer(r'uddg=([^&"]+)', resp.text))
            print(f"  [DDG] {len(matches)} liens uddg trouves")

            for match in matches:
                href = unquote(match.group(1))
                if not href.startswith('http'):
                    continue
                if self._is_company_website(href):
                    return href
                else:
                    print(f"  [DDG] skip (exclu): {href[:60]}")

            return ""
        except Exception as e:
            print(f"  [DDG] EXCEPTION: {e}")
            return ""

    def _guess_domain(self, nom: str) -> str:
        """Essaie de deviner le domaine depuis le nom de l'entreprise."""
        clean = nom.upper()
        for suffix in ['SAS', 'SARL', 'SA', 'EURL', 'SCI', 'SASU', 'SNC', 'SOC', 'SOCIETE', 'NATIONALE']:
            clean = re.sub(rf'\b{suffix}\b', '', clean)
        import unicodedata
        clean = unicodedata.normalize('NFD', clean)
        clean = clean.encode('ascii', 'ignore').decode('ascii')
        words = re.findall(r'[a-zA-Z0-9]+', clean.lower())
        if not words:
            return ""

        candidates = []
        joined = ''.join(words)
        hyphenated = '-'.join(words)
        candidates.append(joined)
        if hyphenated != joined:
            candidates.append(hyphenated)

        seen = set()
        unique = []
        for c in candidates:
            if c not in seen and 2 <= len(c) <= 30:
                seen.add(c)
                unique.append(c)

        for name in unique:
            for ext in ['.fr', '.com', '.org']:
                domain = f"https://www.{name}{ext}"
                try:
                    r = self._web_session.head(
                        domain, timeout=3, allow_redirects=True,
                    )
                    print(f"  [GUESS] {domain} → {r.status_code} → {r.url[:60]}")
                    if r.status_code < 400:
                        final_url = r.url
                        if self._is_company_website(final_url):
                            return final_url
                except Exception as e:
                    print(f"  [GUESS] {domain} → ERREUR: {type(e).__name__}")

        return ""

    def _is_company_website(self, url: str) -> bool:
        """Retourne True si l'URL est probablement le site de l'entreprise."""
        url_lower = url.lower()
        return not any(d in url_lower for d in self.SKIP_DOMAINS)

    # ================================================================
    # ENRICHISSEMENT DATAFRAME
    # ================================================================

    def enrich_dataframe(self, df: pd.DataFrame, filter_ca: bool = True,
                         target_limit: int = None) -> pd.DataFrame:
        """Enrichit un DataFrame via API JSON + recherche site web."""
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
            ville = row.get('ville', '')
            api_data = self.enrich(siren, nom, ville)
            enriched_row = {**row.to_dict()}

            # Merge : ne remplace que si la valeur API est non-vide/non-None
            for key, val in api_data.items():
                if val is None:
                    if key in enriched_row and pd.notna(enriched_row.get(key)):
                        continue
                    enriched_row[key] = val
                elif val:
                    enriched_row[key] = val

            enriched_data.append(enriched_row)
            time.sleep(0.2)

        enriched_df = pd.DataFrame(enriched_data)

        sites = enriched_df['site_web'].apply(
            lambda x: bool(x) if isinstance(x, str) else False
        ).sum() if 'site_web' in enriched_df.columns else 0
        print(f"[OK] {len(enriched_df)} entreprises enrichies ({sites} sites web)\n")

        return enriched_df


# Aliases pour compatibilite
SocieteEnricher = CompanyEnricher
PappersEnricher = CompanyEnricher
Enricher = CompanyEnricher
