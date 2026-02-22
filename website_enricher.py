"""
Enrichisseur de donnees via les sites web des entreprises.
Visite le site_web de chaque entreprise pour extraire :
- Description / activite (meta tags, JSON-LD, OG)
- Contacts (email, telephone)
- Services / offres
- Dates importantes (fondation)
- Capital social, SIRET (footer / mentions legales)

Mode par defaut : extraction HTML pure (BeautifulSoup) — rapide et gratuit.
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
import json
from typing import Dict, Optional
from urllib.parse import urlparse, urljoin
from tqdm import tqdm
import config


class WebsiteEnricher:
    """Enrichit les donnees entreprises en visitant leurs sites web"""

    TIMEOUT = 5
    MAX_CONTENT = 500_000
    DELAY = 1

    SKIP_DOMAINS = [
        'facebook.com', 'twitter.com', 'linkedin.com', 'instagram.com',
        'youtube.com', 'google.com', 'societe.com', 'pappers.fr',
        'infogreffe.fr', 'data.gouv.fr', 'tiktok.com',
    ]

    BLOCKED_NUMBERS = {'0260210000', '0899662006', '0891150515'}

    BLOCKED_EMAIL_DOMAINS = [
        'example.com', 'sentry.io', 'wixpress.com', 'wordpress.org',
        'schema.org', 'gravatar.com', 'w3.org',
    ]

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': config.SCRAPING_CONFIG['user_agent'],
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.5',
        })
        self.session.max_redirects = 3

    def enrich_company(self, site_web: str) -> Dict:
        """Fetch et extrait les donnees du site web d'une entreprise"""
        if not site_web or not isinstance(site_web, str):
            return self._empty_data()

        url = self._normalize_url(site_web)
        if not url:
            return self._empty_data()

        try:
            response = self.session.get(
                url, timeout=self.TIMEOUT, allow_redirects=True, verify=True,
            )

            content_type = response.headers.get('content-type', '')
            if 'text/html' not in content_type and 'application/xhtml' not in content_type:
                return self._empty_data()

            response.raise_for_status()
            # Force UTF-8 pour eviter les problemes d'encodage
            response.encoding = response.apparent_encoding or 'utf-8'
            html = response.text[:self.MAX_CONTENT]

            return self._extract_all(html, url)

        except requests.exceptions.SSLError:
            try:
                response = self.session.get(url, timeout=self.TIMEOUT, verify=False)
                response.raise_for_status()
                response.encoding = response.apparent_encoding or 'utf-8'
                html = response.text[:self.MAX_CONTENT]
                return self._extract_all(html, url)
            except Exception:
                return self._empty_data()
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.TooManyRedirects):
            return self._empty_data()
        except Exception:
            return self._empty_data()

    def _extract_all(self, html: str, url: str) -> Dict:
        """Extraction complete depuis le HTML"""
        soup = BeautifulSoup(html, 'lxml')
        result = {}
        result.update(self._extract_meta_tags(soup))
        result.update(self._extract_jsonld(soup))
        result.update(self._extract_contact_info(soup, url))
        result.update(self._extract_footer_info(soup))
        result.update(self._extract_services(soup))
        return result

    # ── Meta tags ──────────────────────────────────────────

    def _extract_meta_tags(self, soup: BeautifulSoup) -> Dict:
        """Extrait meta description, og:description, title"""
        result = {}

        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            result['ws_description'] = meta_desc['content'].strip()[:500]

        og_desc = soup.find('meta', attrs={'property': 'og:description'})
        if og_desc and og_desc.get('content'):
            og_text = og_desc['content'].strip()[:500]
            if len(og_text) > len(result.get('ws_description', '')):
                result['ws_description'] = og_text

        title = soup.find('title')
        if title:
            result['ws_title'] = title.get_text(strip=True)[:200]

        return result

    # ── JSON-LD (Schema.org) ───────────────────────────────

    def _extract_jsonld(self, soup: BeautifulSoup) -> Dict:
        """Extrait les donnees structurees JSON-LD (Schema.org)"""
        result = {}

        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string)
                items = data if isinstance(data, list) else [data]
                if isinstance(data, dict) and '@graph' in data:
                    items = data['@graph']

                for item in items:
                    if not isinstance(item, dict):
                        continue
                    schema_type = item.get('@type', '')

                    if schema_type in ('Organization', 'LocalBusiness',
                                       'Corporation', 'ProfessionalService'):
                        if item.get('description'):
                            result['ws_description'] = str(item['description'])[:500]
                        if item.get('telephone'):
                            result['ws_telephone'] = str(item['telephone'])
                        if item.get('email'):
                            result['ws_email'] = str(item['email'])
                        if item.get('foundingDate'):
                            result['ws_date_fondation'] = str(item['foundingDate'])[:10]
                        if item.get('numberOfEmployees'):
                            emp = item['numberOfEmployees']
                            if isinstance(emp, dict):
                                result['ws_effectif'] = str(emp.get('value', ''))
                            else:
                                result['ws_effectif'] = str(emp)

            except (json.JSONDecodeError, TypeError, AttributeError):
                continue

        return result

    # ── Contact (email, telephone) ─────────────────────────

    def _extract_contact_info(self, soup: BeautifulSoup, base_url: str) -> Dict:
        """Extrait email et telephone depuis le contenu de la page"""
        result = {}
        domain = urlparse(base_url).netloc.replace('www.', '')

        # Email: liens mailto:
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.startswith('mailto:'):
                email = href.replace('mailto:', '').split('?')[0].strip()
                if '@' in email and not any(d in email for d in self.BLOCKED_EMAIL_DOMAINS):
                    result['ws_email'] = email
                    break

        # Email: regex fallback (prefere emails du domaine)
        if 'ws_email' not in result:
            text = soup.get_text()
            matches = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
            for m in matches:
                if not any(d in m for d in self.BLOCKED_EMAIL_DOMAINS):
                    if domain and domain in m:
                        result['ws_email'] = m
                        break
            if 'ws_email' not in result:
                for m in matches:
                    if not any(d in m for d in self.BLOCKED_EMAIL_DOMAINS):
                        result['ws_email'] = m
                        break

        # Telephone: liens tel:
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.startswith('tel:'):
                tel = re.sub(r'\D', '', href.replace('tel:', ''))
                if tel.startswith('33') and len(tel) == 11:
                    tel = '0' + tel[2:]
                if len(tel) == 10 and tel.startswith('0') and tel not in self.BLOCKED_NUMBERS:
                    result['ws_telephone'] = tel
                    break

        # Telephone: regex fallback
        if 'ws_telephone' not in result:
            text = soup.get_text()
            for pattern in [r'(?:\+33|0033)\s*[1-9](?:[\s.-]?\d{2}){4}',
                            r'0[1-9](?:[\s.-]?\d{2}){4}']:
                match = re.search(pattern, text)
                if match:
                    tel = re.sub(r'\D', '', match.group(0))
                    if tel.startswith('33'):
                        tel = '0' + tel[2:]
                    if len(tel) == 10 and tel not in self.BLOCKED_NUMBERS:
                        result['ws_telephone'] = tel
                        break

        return result

    # ── Footer / mentions legales ──────────────────────────

    def _extract_footer_info(self, soup: BeautifulSoup) -> Dict:
        """Extrait SIRET, capital, dates depuis le footer"""
        result = {}

        footer = soup.find('footer') or soup.find('div', id=re.compile(r'footer', re.I))
        search_areas = [footer] if footer else []
        for el in soup.find_all(['div', 'section', 'p']):
            text = el.get_text(strip=True).lower()
            if any(kw in text for kw in ['mention', 'siret', 'capital', 'rcs']):
                search_areas.append(el)
                if len(search_areas) > 10:
                    break

        combined = ' '.join(el.get_text() for el in search_areas if el)
        if not combined:
            return result

        # Capital social
        capital_match = re.search(
            r'(?:capital|Capital)\s*(?:social)?\s*(?:de)?\s*:?\s*([\d\s.,]+)\s*(?:euros|EUR|€)',
            combined,
        )
        if capital_match:
            result['ws_capital'] = capital_match.group(1).strip()

        # Date fondation
        year_match = re.search(
            r'(?:depuis|cree|fondee?|etabli|founded|since|creation)\s*(?:en\s*)?(\d{4})',
            combined, re.IGNORECASE,
        )
        if year_match:
            year = int(year_match.group(1))
            if 1900 <= year <= 2026:
                result['ws_date_fondation'] = str(year)

        return result

    # ── Services / activite ────────────────────────────────

    def _extract_services(self, soup: BeautifulSoup) -> Dict:
        """Extrait les services/offres depuis les headings et listes"""
        result = {}

        service_keywords = [
            'nos services', 'notre offre', 'nos solutions', 'nos metiers',
            'our services', 'nos activites', 'nos prestations',
            'savoir-faire', 'expertise', 'competences',
        ]

        services = []
        for heading in soup.find_all(['h1', 'h2', 'h3']):
            text = heading.get_text(strip=True).lower()
            if not any(kw in text for kw in service_keywords):
                continue
            parent = heading.find_parent(['section', 'div', 'article'])
            if not parent:
                continue
            for li in parent.find_all('li'):
                svc = li.get_text(strip=True)
                if 5 < len(svc) < 150:
                    services.append(svc)
            if not services:
                for p in parent.find_all('p'):
                    txt = p.get_text(strip=True)
                    if 20 < len(txt) < 300:
                        services.append(txt)
            if services:
                break

        if services:
            result['ws_services'] = ' | '.join(services[:8])

        return result

    # ── Helpers ────────────────────────────────────────────

    def _normalize_url(self, url: str) -> Optional[str]:
        """Normalise l'URL: ajoute https://, filtre social media"""
        url = url.strip().rstrip('/')
        if not url:
            return None

        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        parsed = urlparse(url)
        if not parsed.netloc or '.' not in parsed.netloc:
            return None

        if any(d in parsed.netloc for d in self.SKIP_DOMAINS):
            return None

        return url

    def _merge_website_data(self, row: dict, ws_data: dict) -> dict:
        """Merge les donnees du site web, complement sans ecraser"""
        merged = {**row}

        if ws_data.get('ws_description'):
            merged['ws_description'] = ws_data['ws_description']

        if ws_data.get('ws_services'):
            merged['ws_services'] = ws_data['ws_services']

        if ws_data.get('ws_capital'):
            merged['ws_capital'] = ws_data['ws_capital']

        if ws_data.get('ws_date_fondation'):
            merged['ws_date_fondation'] = ws_data['ws_date_fondation']

        # Email: seulement si vide
        if ws_data.get('ws_email') and not row.get('email'):
            merged['email'] = ws_data['ws_email']

        # Telephone: seulement si vide
        if ws_data.get('ws_telephone') and not row.get('telephone'):
            merged['telephone'] = ws_data['ws_telephone']

        return merged

    def _empty_data(self) -> Dict:
        return {}

    # ── DataFrame ──────────────────────────────────────────

    def enrich_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Enrichit le DataFrame en visitant les sites web des entreprises"""
        print("\n[Website] Visite des sites web entreprises...")

        has_site = df['site_web'].notna() & (df['site_web'] != '')
        to_process = has_site.sum()
        print(f"  {to_process}/{len(df)} entreprises avec site web")

        if to_process == 0:
            return df

        enriched_data = []
        success_count = 0

        for _, row in tqdm(df.iterrows(), total=len(df), desc="Sites web"):
            row_dict = row.to_dict()
            site_web = row_dict.get('site_web', '')

            if site_web and isinstance(site_web, str) and site_web.strip():
                ws_data = self.enrich_company(site_web)
                row_dict = self._merge_website_data(row_dict, ws_data)
                if ws_data.get('ws_description') or ws_data.get('ws_services'):
                    success_count += 1

            enriched_data.append(row_dict)
            time.sleep(self.DELAY)

        enriched_df = pd.DataFrame(enriched_data)
        print(f"[OK] {success_count}/{to_process} sites enrichis avec succes\n")

        return enriched_df
