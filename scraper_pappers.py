"""
Scraper utilisant l'API Pappers v2 (fonctionne depuis Streamlit Cloud).
Drop-in replacement pour DataGouvScraper.

API: https://api.pappers.fr/v2/recherche
Auth: api_token query param
Limites: dépend du plan (gratuit = limité)
"""

import re
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import pandas as pd
import time
from datetime import datetime
from typing import List, Dict, Optional
import config

# Réutilise les constantes du scraper data.gouv
from scraper import (
    TRANCHES_PME,
    REGION_DEPARTEMENTS,
    FORME_TO_NATURE,
    NAF_LABELS,
    TRANCHES_EFFECTIF,
)


class PappersScraper:
    """Scraper utilisant l'API Pappers v2 — drop-in replacement pour DataGouvScraper."""

    BASE_URL = "https://api.pappers.fr/v2/recherche"
    REQUEST_TIMEOUT = 30
    MAX_PER_PAGE = 20  # Pappers limite à 20 résultats par page

    # Qualités à EXCLURE
    _QUALITE_EXCLUSIONS = [
        'commissaire aux comptes',
        'commissaire aux comptes suppléant',
        'commissaire aux comptes titulaire',
        'membre du conseil de surveillance',
        'censeur',
        'représentant permanent',
    ]

    # Qualités PRIORITAIRES
    # Gérant/DG d'abord : ce sont les vrais décideurs opérationnels
    _QUALITE_PRIORITE = [
        'gérant',
        'co-gérant',
        'directeur général',
        'directeur général délégué',
        'président-directeur général',
        'pdg',
        'président',
        "président du conseil d'administration",
        'président de sas',
        'administrateur',
    ]

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.diagnostics: List[str] = []

    def _log(self, msg: str):
        print(msg)
        self.diagnostics.append(msg)

    # ──────────────────────────────────────────
    # search_companies — même interface que DataGouvScraper
    # ──────────────────────────────────────────

    def search_companies(self, filtres: Dict) -> List[Dict]:
        limit = filtres.get('limit', 100) or 100
        self.diagnostics = []
        self._log("\n[Pappers] Recherche API Pappers v2...")
        self._log(f"  Limite cible: {limit}")

        params = {
            'api_token': self.api_key,
            'par_page': min(self.MAX_PER_PAGE, limit),
            'entreprise_cessee': 'false',
        }

        # --- CA (en euros, directement) ---
        ca_min = float(filtres.get('ca_min', 0) or 0)
        ca_max = float(filtres.get('ca_max', 0) or 0)
        if ca_min > 0:
            params['chiffre_affaires_min'] = int(ca_min)
            self._log(f"  CA min: {ca_min/1e6:.0f}M")
        if ca_max > 0:
            params['chiffre_affaires_max'] = int(ca_max)
            self._log(f"  CA max: {ca_max/1e6:.0f}M")

        # --- Région → départements ---
        region_code = filtres.get('region')
        if region_code:
            depts = REGION_DEPARTEMENTS.get(region_code, [])
            if depts:
                params['departement'] = ','.join(depts)
                self._log(f"  Region: {config.REGIONS.get(region_code, region_code)} → depts: {depts}")

        # --- Secteur NAF ---
        secteur = filtres.get('secteur_naf')
        if secteur:
            params['code_naf'] = secteur
            self._log(f"  NAF: {secteur}")

        # --- Forme juridique ---
        forme = filtres.get('forme_juridique')
        if forme and forme in FORME_TO_NATURE:
            params['categorie_juridique'] = ','.join(FORME_TO_NATURE[forme])
            self._log(f"  Forme: {forme} → {FORME_TO_NATURE[forme]}")

        # --- Age dirigeant (server-side!) ---
        age_dir_min = filtres.get('age_dirigeant_min', 0) or 0
        age_dir_max = filtres.get('age_dirigeant_max', 0) or 0
        if age_dir_min > 0:
            params['age_dirigeant_min'] = int(age_dir_min)
            self._log(f"  Age dirigeant min: {age_dir_min}")
        if age_dir_max > 0:
            params['age_dirigeant_max'] = int(age_dir_max)
            self._log(f"  Age dirigeant max: {age_dir_max}")

        # --- Age entreprise (date_creation_max) ---
        age_min = filtres.get('age_min', 0) or 0
        if age_min > 0:
            max_year = datetime.now().year - age_min
            params['date_creation_max'] = f"{max_year}-12-31"
            self._log(f"  Age entreprise min: {age_min} ans (créée avant {max_year})")

        # --- Pagination ---
        all_companies = []
        seen_sirens = set()
        page = 1

        while len(all_companies) < limit:
            params['page'] = page

            try:
                response = self.session.get(
                    self.BASE_URL,
                    params=params,
                    timeout=self.REQUEST_TIMEOUT,
                )

                self._log(f"  Page {page}: HTTP {response.status_code}, "
                          f"Content-Type: {response.headers.get('content-type', '?')}")

                # Gestion erreurs HTTP
                if response.status_code in (401, 402, 403):
                    try:
                        err = response.json()
                        err_msg = err.get('error', '') or err.get('message', '')
                    except Exception:
                        err_msg = response.text[:200]
                    raise RuntimeError(f"API Pappers ({response.status_code}): {err_msg}")
                if response.status_code == 429:
                    self._log("  Rate limit atteint, arrêt.")
                    break

                ct = response.headers.get('content-type', '')
                if 'application/json' not in ct:
                    body = response.text[:300].replace('\n', ' ')
                    msg = f"Pappers ne retourne pas du JSON (CT: {ct}). Body: {body}"
                    self._log(f"  {msg}")
                    if page == 1:
                        raise RuntimeError(msg)
                    break

                try:
                    data = response.json()
                except ValueError:
                    body = response.text[:300].replace('\n', ' ')
                    msg = f"JSON invalide. Body: {body}"
                    self._log(f"  {msg}")
                    if page == 1:
                        raise RuntimeError(msg)
                    break

                response.raise_for_status()

                # Debug: log les clés du premier résultat
                results = data.get('resultats', data.get('results', []))
                total = data.get('total', data.get('total_results', '?'))

                if page == 1:
                    self._log(f"  API: {total} résultats totaux")
                    if results:
                        self._log(f"  Clés résultat: {list(results[0].keys())[:15]}")

                if not results:
                    self._log(f"  Page {page}: aucun résultat, arrêt")
                    break

                added = 0
                for company in results:
                    siren = company.get('siren', '')
                    if not siren or siren in seen_sirens:
                        continue
                    seen_sirens.add(siren)
                    all_companies.append(company)
                    added += 1

                self._log(f"  Page {page}: {len(results)} reçus → +{added} retenus "
                          f"(total: {len(all_companies)})")

                if len(all_companies) >= limit:
                    break
                if len(results) < params['par_page']:
                    break

                page += 1
                time.sleep(0.5)  # Respecter les limites

            except (requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout) as e:
                msg = f"Erreur réseau: {type(e).__name__}: {e}"
                self._log(f"  {msg}")
                if page == 1:
                    raise RuntimeError(f"Impossible de joindre l'API Pappers: {msg}") from e
                break
            except RuntimeError:
                raise
            except Exception as e:
                msg = f"Erreur page {page}: {type(e).__name__}: {e}"
                self._log(f"  {msg}")
                if page == 1:
                    raise
                break

        all_companies = all_companies[:limit]
        self._log(f"  Params API: { {k: v for k, v in params.items() if k != 'api_token'} }")
        self._log(f"  Total retenu: {len(all_companies)} entreprises uniques")
        return all_companies

    # ──────────────────────────────────────────
    # to_dataframe — même schéma que DataGouvScraper
    # ──────────────────────────────────────────

    def to_dataframe(self, companies: List[Dict]) -> pd.DataFrame:
        data = []
        for company in companies:
            try:
                siege = company.get('siege', {})
                siren = company.get('siren', '')

                # Finances
                ca_euros, resultat_euros = self._extract_finances(company)

                # Dirigeant
                pp = self._pick_best_dirigeant_pp(company)
                dirigeant_principal = self._format_dirigeant(pp)
                dirigeant_nom = self._extract_nom(pp)
                dirigeant_prenom = self._extract_prenom(pp)
                age_dirigeant = self._extract_age(pp)

                # NAF
                code_naf = (company.get('code_naf')
                            or company.get('activite_principale', ''))
                libelle_naf = (company.get('libelle_code_naf')
                               or NAF_LABELS.get(code_naf, ''))

                # Tranche effectif
                tranche_code = (company.get('tranche_effectif_salarie')
                                or company.get('effectif', ''))
                tranche_text = TRANCHES_EFFECTIF.get(str(tranche_code), str(tranche_code))

                # Adresse
                adresse = siege.get('adresse_ligne_1') or siege.get('adresse', '')
                code_postal = siege.get('code_postal', '')
                ville = (siege.get('ville')
                         or siege.get('libelle_commune', ''))
                dept = siege.get('departement', '')
                region_code = siege.get('region', '')
                region_name = config.REGIONS.get(region_code, region_code)

                adresse_complete = ', '.join(
                    p for p in [adresse, f"{code_postal} {ville}".strip()] if p
                )

                row = {
                    'nom_entreprise': (company.get('nom_entreprise')
                                       or company.get('denomination')
                                       or company.get('nom_complet', '')),
                    'siren': siren,
                    'siret_siege': (siege.get('siret')
                                    or company.get('siret_siege', '')),
                    'forme_juridique': (company.get('categorie_juridique')
                                        or company.get('forme_juridique')
                                        or company.get('nature_juridique', '')),
                    'code_naf': code_naf,
                    'libelle_naf': libelle_naf,
                    'date_creation': company.get('date_creation', ''),
                    'tranche_effectif': tranche_text,
                    'categorie': company.get('categorie_entreprise', ''),

                    'ca_euros': ca_euros,
                    'resultat_euros': resultat_euros,

                    'adresse': adresse,
                    'code_postal': code_postal,
                    'ville': ville,
                    'departement': dept,
                    'region': region_name,
                    'adresse_complete': adresse_complete,

                    'dirigeant_principal': dirigeant_principal,
                    'dirigeant_nom': dirigeant_nom,
                    'dirigeant_prenom': dirigeant_prenom,
                    'age_dirigeant': age_dirigeant,

                    'url_pappers': f"https://www.pappers.fr/entreprise/{siren}",
                    'url_datagouv': f"https://annuaire-entreprises.data.gouv.fr/entreprise/{siren}",

                    # Bonus Pappers (pré-remplis, enricher peut compléter)
                    'site_web': company.get('site_internet')
                               or company.get('site_web', ''),
                    'telephone': company.get('telephone', ''),
                    'email': company.get('email', ''),
                }
                data.append(row)
            except Exception as e:
                print(f"  Erreur parsing {company.get('siren', '?')}: {e}")
                continue

        return pd.DataFrame(data)

    # ──────────────────────────────────────────
    # Helpers privés
    # ──────────────────────────────────────────

    def _extract_finances(self, company: Dict) -> tuple:
        """Extrait CA et résultat net (année la plus récente)."""
        # Pappers peut avoir "finances" (list de dicts) ou "chiffre_affaires" direct
        ca = company.get('chiffre_affaires')
        resultat = company.get('resultat')

        # Essayer finances si c'est un dict {année: {ca, resultat_net}} (format data.gouv)
        finances = company.get('finances')
        if isinstance(finances, dict) and finances:
            try:
                latest = max(finances.keys())
                year_data = finances[latest]
                ca = ca or year_data.get('ca')
                resultat = resultat or year_data.get('resultat_net')
            except Exception:
                pass
        # Pappers finances = liste de dicts [{annee, chiffre_affaires, resultat}]
        elif isinstance(finances, list) and finances:
            try:
                latest = finances[0]  # Déjà triée par année desc
                ca = ca or latest.get('chiffre_affaires') or latest.get('ca')
                resultat = resultat or latest.get('resultat') or latest.get('resultat_net')
            except Exception:
                pass

        # Convertir en float
        try:
            ca = float(ca) if ca is not None else None
        except (ValueError, TypeError):
            ca = None
        try:
            resultat = float(resultat) if resultat is not None else None
        except (ValueError, TypeError):
            resultat = None

        return ca, resultat

    def _pick_best_dirigeant_pp(self, company: Dict) -> Optional[Dict]:
        """Sélectionne le meilleur dirigeant personne physique."""
        # Pappers: "representants" ou "dirigeants"
        dirigeants = (company.get('representants')
                      or company.get('dirigeants', []))
        if not dirigeants:
            return None

        # Séparer PP des PM
        pp_list = []
        for d in dirigeants:
            type_dir = (d.get('type_dirigeant') or d.get('type') or '').lower()
            prenom = d.get('prenom') or d.get('prenoms') or ''
            if 'morale' in type_dir or not prenom:
                continue
            pp_list.append(d)

        if not pp_list:
            return None

        # Priorité par qualité
        for keyword in self._QUALITE_PRIORITE:
            for d in pp_list:
                qualite = (d.get('qualite') or '').lower()
                if keyword in qualite:
                    return d

        # Premier non-exclu
        for d in pp_list:
            qualite = (d.get('qualite') or '').lower()
            if not any(excl in qualite for excl in self._QUALITE_EXCLUSIONS):
                return d

        # Fallback: premier PP
        return pp_list[0] if pp_list else None

    def _format_dirigeant(self, pp: Optional[Dict]) -> str:
        if not pp:
            return ""
        prenom = pp.get('prenom') or pp.get('prenoms', '')
        nom = pp.get('nom', '')
        qualite = pp.get('qualite', '')
        return f"{prenom} {nom} ({qualite})".strip()

    def _extract_nom(self, pp: Optional[Dict]) -> str:
        if not pp:
            return ''
        nom = pp.get('nom', '')
        return re.sub(r'\s*\([^)]*\)', '', nom).strip()

    def _extract_prenom(self, pp: Optional[Dict]) -> str:
        if not pp:
            return ''
        return pp.get('prenom') or pp.get('prenoms', '')

    def _extract_age(self, pp: Optional[Dict]) -> Optional[int]:
        if not pp:
            return None
        # Pappers: "date_de_naissance" ou "date_naissance" ou "age"
        age = pp.get('age')
        if age:
            try:
                return int(age)
            except (ValueError, TypeError):
                pass
        date_str = (pp.get('date_de_naissance')
                    or pp.get('date_naissance')
                    or pp.get('date_de_naissance_formate', ''))
        if not date_str or len(date_str) < 4:
            return None
        try:
            birth_year = int(date_str[:4])
            if birth_year > 1900:
                return datetime.now().year - birth_year
        except (ValueError, TypeError):
            pass
        return None
