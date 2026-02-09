"""
Qualification des prospects avec Claude (Anthropic API)
Score A/B/C/D + recherche web + justification pour chaque entreprise
"""

import anthropic
import pandas as pd
from typing import Dict, List
from tqdm import tqdm
import time
import json
import re
import config


class ProspectQualifier:
    """Qualifie les prospects avec l'IA Claude + recherche web"""

    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-20250514"
        self.web_search_config = config.WEB_SEARCH_CONFIG

    def build_analysis_prompt(self, company_data: Dict) -> str:
        """Construit le prompt d'analyse avec instructions de recherche web"""

        nom = company_data.get('nom_entreprise', 'N/A')
        siren = company_data.get('siren', 'N/A')
        secteur = company_data.get('libelle_naf', company_data.get('activite_desc', 'N/A'))
        ca = company_data.get('ca_euros', 0)
        ca_formatted = f"{ca/1_000_000:.1f} M€" if ca else "N/A"
        evolution_ca = company_data.get('evolution_ca', 'N/A')
        resultat = company_data.get('resultat_euros', 'N/A')
        if isinstance(resultat, (int, float)):
            resultat = f"{resultat/1_000_000:.2f} M€"

        forme = company_data.get('forme_juridique', 'N/A')
        date_creation = company_data.get('date_creation', 'N/A')
        dirigeant = company_data.get('dirigeant_enrichi',
                    company_data.get('dirigeant_principal', 'N/A'))
        ville = company_data.get('ville', 'N/A')
        region = company_data.get('region', 'N/A')
        effectif = company_data.get('tranche_effectif',
                   company_data.get('effectif_societe', 'N/A'))
        site_web = company_data.get('site_web', '')
        telephone = company_data.get('telephone', '')
        email = company_data.get('email', '')
        adresse = company_data.get('adresse_complete', 'N/A')

        prompt = f"""Tu es un analyste corporate finance / M&A spécialisé dans les PME françaises.
Tu travailles pour un cabinet de conseil en corporate advisory qui cherche des PME indépendantes
à accompagner sur des opérations de croissance externe, cession, ou levée de fonds.

**ENTREPRISE À ANALYSER**

- Nom : {nom}
- SIREN : {siren}
- Secteur : {secteur}
- Chiffre d'affaires : {ca_formatted}
- Évolution CA : {evolution_ca}
- Résultat net : {resultat}
- Forme juridique : {forme}
- Date de création : {date_creation}
- Dirigeant : {dirigeant}
- Localisation : {adresse} - {ville}, {region}
- Effectif : {effectif}
- Téléphone : {telephone if telephone else 'Non disponible'}
- Email : {email if email else 'Non disponible'}
- Site web : {site_web if site_web else 'Non disponible'}

---

**MISSION**

Utilise la recherche web pour approfondir ton analyse de cette entreprise. Recherche :

1. **Levées de fonds** : "{nom}" + "levée de fonds" ou "financement"
2. **Activité LBO** : "{nom}" + "LBO" ou "rachat" ou "acquisition"
3. **Investisseurs financiers** : "{nom}" + "fonds d'investissement" ou "private equity" ou "capital"
4. **Informations dirigeant** : le dirigeant est-il le fondateur ? Son âge approximatif ?
5. **Articles de presse** : actualités récentes sur l'entreprise
6. **Site web** : si non disponible ci-dessus, trouve-le

---

**CRITÈRES DE SCORING**

- **A** = PME indépendante, rentable, dirigeant fondateur, CA entre 10-30M€, aucun accompagnement financier détecté
- **B** = PME correcte mais 1-2 critères manquants (CA un peu hors fourchette idéale, dirigeant non-fondateur, etc.)
- **C** = Trop petite (CA < 5M€), ou signes d'accompagnement financier existant
- **D** = Déjà en LBO, fonds au capital identifié, CA hors fourchette (< 3M€ ou > 60M€)

---

**FORMAT DE RÉPONSE (STRICT)**

Réponds UNIQUEMENT au format JSON suivant :

{{
  "resume_business": "Description de l'activité en 3-4 lignes : activité réelle, clients, positionnement, modèle économique",
  "signaux_ma": "Signaux M&A détectés (levées, LBO, acquisitions, fonds au capital) ou 'Aucun signal détecté'",
  "analyse_fit": "Analyse corporate advisory fit en 4-5 lignes : taille, complexité, structure, maturité, signaux",
  "score": "A, B, C ou D",
  "score_label": "Label descriptif du score",
  "justification": "Justification du score en 2-3 lignes",
  "dirigeant_info": "Nom + fonction + fondateur/non-fondateur + âge si trouvé, ou 'Non trouvé'",
  "email_found": "Email trouvé pendant la recherche web, ou chaîne vide",
  "site_web_found": "Site web trouvé pendant la recherche web, ou chaîne vide",
  "evolution_ca": "Tendance de croissance si trouvée, ou chaîne vide"
}}

Réponds UNIQUEMENT en JSON valide, sans aucun texte avant ou après le JSON."""

        return prompt

    def _api_call_with_retry(self, messages, tools, max_retries=3):
        """Appel API avec retry et backoff exponentiel pour les rate limits"""
        for attempt in range(max_retries + 1):
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=self.web_search_config['max_tokens'],
                    messages=messages,
                    tools=tools
                )
                return response
            except anthropic.RateLimitError as e:
                if attempt == max_retries:
                    raise
                wait_time = 30 * (2 ** attempt)  # 30s, 60s, 120s
                print(f"  Rate limit atteint, attente {wait_time}s...")
                time.sleep(wait_time)
        return None

    def analyze_company(self, company_data: Dict) -> Dict:
        """Analyse une entreprise avec Claude + recherche web"""
        try:
            prompt = self.build_analysis_prompt(company_data)

            tools = [{
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": self.web_search_config['max_uses_per_company'],
                "user_location": {
                    "type": "approximate",
                    "country": "FR",
                    "timezone": "Europe/Paris"
                }
            }]

            messages = [{"role": "user", "content": prompt}]

            response = self._api_call_with_retry(messages, tools)

            # Gère pause_turn : continue la conversation si Claude a besoin de plus de tours
            max_continuations = 10
            continuation = 0
            while response.stop_reason == "pause_turn" and continuation < max_continuations:
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": "Continue."})
                response = self._api_call_with_retry(messages, tools)
                continuation += 1

            # Extrait le texte de la réponse (ignore les blocs tool_use/tool_result)
            text_content = ""
            for block in response.content:
                if hasattr(block, 'text'):
                    text_content += block.text

            # Nettoie et parse le JSON
            content = text_content.strip()
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]

            # Cherche un objet JSON dans le texte
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content)
            if json_match:
                content = json_match.group(0)

            content = content.strip()
            result = json.loads(content)

            # Validation des clés requises
            required_keys = ['resume_business', 'signaux_ma', 'analyse_fit',
                             'score', 'justification']
            if not all(k in result for k in required_keys):
                raise ValueError("Réponse IA incomplète")

            # Normalise le score
            score = result['score'].upper().strip()
            if score not in ['A', 'B', 'C', 'D']:
                score = 'C'
            result['score'] = score
            result['score_label'] = config.SCORING_CATEGORIES.get(score, '')

            # Assure que toutes les clés attendues existent
            for key in ['dirigeant_info', 'email_found', 'site_web_found',
                        'evolution_ca', 'signaux_ma', 'score_label']:
                if key not in result:
                    result[key] = ''

            return result

        except json.JSONDecodeError:
            print(f"  Warning: JSON parse error for {company_data.get('nom_entreprise', 'N/A')}")
            return self._default_analysis()
        except Exception as e:
            print(f"  Warning: AI analysis error: {e}")
            return self._default_analysis()

    def _default_analysis(self) -> Dict:
        """Analyse par défaut en cas d'erreur"""
        return {
            'resume_business': 'Analyse non disponible',
            'signaux_ma': 'Non analysé',
            'analyse_fit': 'Analyse non disponible',
            'score': 'C',
            'score_label': config.SCORING_CATEGORIES['C'],
            'justification': "Erreur lors de l'analyse automatique",
            'dirigeant_info': '',
            'email_found': '',
            'site_web_found': '',
            'evolution_ca': '',
        }

    def qualify_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Qualifie toutes les entreprises avec recherche web + scoring IA"""
        print("\n Qualification IA + Recherche web des prospects...\n")

        qualified_data = []
        batch_size = self.web_search_config['batch_size']
        delay = self.web_search_config['delay_between_qualifications']
        batch_pause = self.web_search_config['batch_pause']

        for idx, row in tqdm(df.iterrows(), total=len(df), desc="Qualification"):
            company_data = row.to_dict()

            # Analyse IA avec recherche web
            analysis = self.analyze_company(company_data)

            # Fusionne les données
            qualified_row = {**company_data, **analysis}

            # Merge web search : email
            if not qualified_row.get('email') and qualified_row.get('email_found'):
                qualified_row['email'] = qualified_row['email_found']

            # Merge web search : site web
            if not qualified_row.get('site_web') and qualified_row.get('site_web_found'):
                qualified_row['site_web'] = qualified_row['site_web_found']

            # Merge web search : évolution CA
            if not qualified_row.get('evolution_ca') and analysis.get('evolution_ca'):
                qualified_row['evolution_ca'] = analysis['evolution_ca']

            # Merge web search : dirigeant enrichi
            if qualified_row.get('dirigeant_info') and qualified_row['dirigeant_info'] != 'Non trouvé':
                qualified_row['dirigeant_enrichi'] = qualified_row['dirigeant_info']

            qualified_data.append(qualified_row)

            # Rate limiting
            time.sleep(delay)
            if (idx + 1) % batch_size == 0:
                time.sleep(batch_pause)

        qualified_df = pd.DataFrame(qualified_data)

        # Trie par score
        score_order = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
        qualified_df['score_order'] = qualified_df['score'].map(score_order)
        qualified_df = qualified_df.sort_values('score_order').drop('score_order', axis=1)

        print(f"\n {len(qualified_df)} prospects qualifiés")
        print("\n Répartition des scores:")
        print(qualified_df['score'].value_counts().sort_index())

        return qualified_df

    def format_excel_output(self, df: pd.DataFrame, output_file: str):
        """Formate et exporte le fichier Excel final avec 18 colonnes"""

        df_export = df.copy()

        # Prépare CA en M€
        if 'ca_euros' in df_export.columns:
            df_export['ca_m_euros'] = df_export['ca_euros'].apply(
                lambda x: round(x / 1_000_000, 2) if pd.notna(x) and isinstance(x, (int, float)) else None
            )

        # Formate résultat net
        if 'resultat_euros' in df_export.columns:
            df_export['resultat_m_euros'] = df_export['resultat_euros'].apply(
                lambda x: f"{x/1_000_000:.2f}" if pd.notna(x) and isinstance(x, (int, float)) else 'N/A'
            )

        # Construit la colonne secteur (meilleure source disponible)
        if 'secteur' not in df_export.columns:
            if 'libelle_naf' in df_export.columns:
                df_export['secteur'] = df_export['libelle_naf']
            elif 'activite_desc' in df_export.columns:
                df_export['secteur'] = df_export['activite_desc']
            else:
                df_export['secteur'] = ''

        # Construit la colonne dirigeant (meilleure source disponible)
        if 'dirigeant' not in df_export.columns:
            if 'dirigeant_enrichi' in df_export.columns:
                df_export['dirigeant'] = df_export['dirigeant_enrichi']
            elif 'dirigeant_principal' in df_export.columns:
                df_export['dirigeant'] = df_export['dirigeant_principal']
            else:
                df_export['dirigeant'] = ''

        # Construit adresse_complete si absente
        if 'adresse_complete' not in df_export.columns:
            df_export['adresse_complete'] = df_export.apply(
                lambda r: f"{r.get('adresse', '')}, {r.get('code_postal', '')} {r.get('ville', '')}".strip(', '),
                axis=1
            )

        # 18 colonnes dans l'ordre exact demandé
        column_mapping = {
            'score': 'Score',
            'score_label': 'Score Label',
            'nom_entreprise': 'Nom entreprise',
            'ca_m_euros': 'CA (M€)',
            'evolution_ca': 'Évolution CA',
            'resultat_m_euros': 'Résultat net',
            'secteur': 'Secteur',
            'dirigeant': 'Dirigeant',
            'telephone': 'Téléphone',
            'email': 'Email',
            'site_web': 'Site web',
            'adresse_complete': 'Adresse complète',
            'ville': 'Ville',
            'region': 'Région',
            'resume_business': 'Résumé business',
            'signaux_ma': 'Signaux M&A',
            'analyse_fit': 'Analyse corporate fit',
            'justification': 'Justification du score',
        }

        # Sélectionne et renomme les colonnes
        final_columns = []
        rename_map = {}
        for col_key, col_label in column_mapping.items():
            if col_key not in df_export.columns:
                df_export[col_key] = ''
            final_columns.append(col_key)
            rename_map[col_key] = col_label

        df_final = df_export[final_columns].rename(columns=rename_map)

        # Export Excel avec formatage
        with pd.ExcelWriter(output_file, engine='xlsxwriter') as writer:
            df_final.to_excel(writer, sheet_name='Prospects', index=False)

            workbook = writer.book
            worksheet = writer.sheets['Prospects']

            # Format header
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#4472C4',
                'font_color': 'white',
                'border': 1,
                'text_wrap': True,
                'valign': 'vcenter',
            })

            # Formats par score
            score_formats = {
                'A': workbook.add_format({'bg_color': '#C6EFCE', 'bold': True, 'border': 1}),
                'B': workbook.add_format({'bg_color': '#FFEB9C', 'border': 1}),
                'C': workbook.add_format({'bg_color': '#FFC7CE', 'border': 1}),
                'D': workbook.add_format({'bg_color': '#CCCCCC', 'border': 1}),
            }

            # Écrit les headers
            for col_num, value in enumerate(df_final.columns.values):
                worksheet.write(0, col_num, value, header_format)

            # Applique les couleurs selon le score
            for row_num in range(1, len(df_final) + 1):
                score = df_final.iloc[row_num - 1].iloc[0]
                fmt = score_formats.get(score, score_formats['D'])
                worksheet.write(row_num, 0, score, fmt)

            # Largeurs de colonnes (18 colonnes)
            widths = [8, 35, 30, 10, 20, 12, 25, 25, 15, 25, 30, 35, 15, 20, 40, 30, 40, 40]
            for i, w in enumerate(widths):
                worksheet.set_column(i, i, w)

            # Fige la ligne d'en-tête
            worksheet.freeze_panes(1, 0)

            # Auto-filtre
            worksheet.autofilter(0, 0, len(df_final), len(df_final.columns) - 1)

        print(f"\n Fichier Excel final créé: {output_file}")


def main():
    """Test du qualifier"""
    import glob
    import os
    from datetime import datetime

    if not config.ANTHROPIC_API_KEY or config.ANTHROPIC_API_KEY == "sk-ant-xxxxx":
        print("ERREUR: Configure ta clé API Anthropic dans config.py")
        print("   Obtiens-la sur: https://console.anthropic.com/")
        return

    files = glob.glob("outputs/enriched_*.xlsx")
    if not files:
        print("Aucun fichier enrichi trouvé. Lance enricher.py d'abord")
        return

    latest = max(files, key=os.path.getctime)
    print(f"Chargement: {latest}")

    df = pd.read_excel(latest)

    qualifier = ProspectQualifier(config.ANTHROPIC_API_KEY)
    qualified_df = qualifier.qualify_dataframe(df)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"outputs/prospects_qualified_{timestamp}.xlsx"
    qualifier.format_excel_output(qualified_df, output_file)


if __name__ == "__main__":
    main()
