"""
Qualification des prospects avec Claude (Anthropic API)
Score A/B/C/D basé sur les données scrapées - PAS de recherche web (rapide)
"""

import anthropic
import pandas as pd
from io import BytesIO
from typing import Dict
from tqdm import tqdm
import time
import json
import re
import config


class ProspectQualifier:
    """Qualifie les prospects avec l'IA Claude (sans web search = rapide)"""

    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-20250514"

    def build_analysis_prompt(self, company_data: Dict) -> str:
        """Construit le prompt d'analyse basé uniquement sur les données scrapées"""

        nom = company_data.get('nom_entreprise', 'N/A')
        siren = company_data.get('siren', 'N/A')
        secteur = company_data.get('libelle_naf', company_data.get('activite_desc', 'N/A'))
        ca = company_data.get('ca_euros', 0)
        ca_fmt = f"{ca/1_000_000:.1f} M€" if ca else "Non disponible"
        evolution_ca = company_data.get('evolution_ca', '') or 'Non disponible'
        resultat = company_data.get('resultat_euros', None)
        resultat_fmt = f"{resultat/1_000_000:.2f} M€" if isinstance(resultat, (int, float)) else "Non disponible"
        forme = company_data.get('forme_juridique', 'N/A')
        date_creation = company_data.get('date_creation', 'N/A')
        dirigeant = company_data.get('dirigeant_enrichi', company_data.get('dirigeant_principal', 'N/A'))
        ville = company_data.get('ville', 'N/A')
        effectif = company_data.get('tranche_effectif', company_data.get('effectif_societe', 'N/A'))

        return f"""Tu es un analyste M&A spécialisé PME françaises. Analyse cette entreprise et score-la.

ENTREPRISE :
- Nom : {nom} (SIREN: {siren})
- Secteur : {secteur}
- CA : {ca_fmt}
- Évolution CA : {evolution_ca}
- Résultat net : {resultat_fmt}
- Forme juridique : {forme}
- Création : {date_creation}
- Dirigeant : {dirigeant}
- Ville : {ville}
- Effectif : {effectif}

SCORING :
- A = PME indépendante, rentable, CA 10-30M€, fondateur dirigeant probable
- B = PME correcte, CA 5-50M€, 1-2 critères manquants
- C = Trop petite (CA<5M€), ou association, ou secteur inadapté
- D = Hors cible (pas une entreprise commerciale, CA inconnu et petite structure)

Réponds UNIQUEMENT en JSON :
{{"score":"A/B/C/D","score_label":"label court","resume":"activité en 2 lignes","analyse":"fit M&A en 2 lignes","justification":"pourquoi ce score en 1 ligne"}}"""

    def analyze_company(self, company_data: Dict) -> Dict:
        """Analyse une entreprise avec Claude (appel simple, pas de web search)"""
        try:
            prompt = self.build_analysis_prompt(company_data)

            response = self.client.messages.create(
                model=self.model,
                max_tokens=config.QUALIFIER_CONFIG['max_tokens'],
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text.strip()

            # Nettoie le markdown
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]

            # Trouve le JSON
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content)
            if json_match:
                content = json_match.group(0)

            result = json.loads(content.strip())

            # Normalise le score
            score = result.get('score', 'C').upper().strip()
            if score not in ['A', 'B', 'C', 'D']:
                score = 'C'
            result['score'] = score
            result['score_label'] = result.get('score_label', config.SCORING_CATEGORIES.get(score, ''))

            # Assure les clés
            for key in ['resume', 'analyse', 'justification', 'score_label']:
                if key not in result:
                    result[key] = ''

            return result

        except anthropic.RateLimitError:
            print(f"  Rate limit, attente 10s...")
            time.sleep(10)
            try:
                return self.analyze_company(company_data)
            except Exception:
                return self._default_analysis()
        except Exception as e:
            print(f"  Erreur IA: {str(e)[:60]}")
            return self._default_analysis()

    def _default_analysis(self) -> Dict:
        return {
            'score': 'C',
            'score_label': config.SCORING_CATEGORIES['C'],
            'resume': 'Analyse non disponible',
            'analyse': 'Analyse non disponible',
            'justification': "Erreur lors de l'analyse",
        }

    def qualify_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Qualifie toutes les entreprises (rapide, ~3s par entreprise)"""
        print("\n Qualification IA des prospects...\n")

        qualified_data = []
        delay = config.QUALIFIER_CONFIG['delay_between_calls']

        for idx, row in tqdm(df.iterrows(), total=len(df), desc="Qualification IA"):
            analysis = self.analyze_company(row.to_dict())
            qualified_row = {**row.to_dict(), **analysis}
            qualified_data.append(qualified_row)
            time.sleep(delay)

        qualified_df = pd.DataFrame(qualified_data)

        # Trie par score
        score_order = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
        qualified_df['score_order'] = qualified_df['score'].map(score_order)
        qualified_df = qualified_df.sort_values('score_order').drop('score_order', axis=1)

        print(f"\n {len(qualified_df)} prospects qualifiés")
        print(qualified_df['score'].value_counts().sort_index())

        return qualified_df

    def format_excel_output(self, df: pd.DataFrame, output_file: str = None) -> bytes:
        """Formate le fichier Excel professionnel. Retourne les bytes du fichier."""

        df_export = df.copy()

        # CA en M€
        if 'ca_euros' in df_export.columns:
            df_export['ca_m'] = df_export['ca_euros'].apply(
                lambda x: round(x / 1_000_000, 2) if pd.notna(x) and isinstance(x, (int, float)) else None
            )

        # Résultat net en M€
        if 'resultat_euros' in df_export.columns:
            df_export['resultat_m'] = df_export['resultat_euros'].apply(
                lambda x: round(x / 1_000_000, 2) if pd.notna(x) and isinstance(x, (int, float)) else None
            )

        # Dirigeant : meilleure source
        df_export['dirigeant_final'] = df_export.apply(
            lambda r: r.get('dirigeant_enrichi') or r.get('dirigeant_principal') or '', axis=1
        )

        # Secteur : meilleure source
        df_export['secteur_final'] = df_export.apply(
            lambda r: r.get('libelle_naf') or r.get('activite_desc') or '', axis=1
        )

        # Adresse complète
        if 'adresse_complete' not in df_export.columns:
            df_export['adresse_complete'] = df_export.apply(
                lambda r: f"{r.get('adresse', '')}, {r.get('code_postal', '')} {r.get('ville', '')}".strip(', '),
                axis=1
            )

        # Colonnes dans l'ordre avec noms français professionnels
        column_map = [
            ('score', 'Score'),
            ('score_label', 'Qualification'),
            ('nom_entreprise', 'Entreprise'),
            ('ca_m', "Chiffre d'Affaires (M€)"),
            ('evolution_ca', 'Évolution CA'),
            ('resultat_m', 'Résultat Net (M€)'),
            ('secteur_final', "Secteur d'Activité"),
            ('dirigeant_final', 'Dirigeant Principal'),
            ('telephone', 'Téléphone'),
            ('email', 'Email'),
            ('site_web', 'Site Web'),
            ('adresse_complete', 'Adresse du Siège'),
            ('ville', 'Ville'),
            ('region', 'Région'),
            ('tranche_effectif', 'Effectif'),
            ('date_creation', 'Date de Création'),
            ('forme_juridique', 'Forme Juridique'),
            ('siren', 'SIREN'),
            ('url_pappers', 'Fiche Pappers'),
            ('resume', 'Résumé Activité'),
            ('analyse', 'Analyse M&A'),
            ('justification', 'Justification Score'),
        ]

        # Construit le DataFrame final
        final_cols = []
        rename = {}
        for col_key, col_label in column_map:
            if col_key not in df_export.columns:
                df_export[col_key] = ''
            final_cols.append(col_key)
            rename[col_key] = col_label

        df_final = df_export[final_cols].rename(columns=rename)

        # Écrit dans un buffer (ou fichier)
        buffer = BytesIO()
        target = output_file if output_file else buffer

        with pd.ExcelWriter(target, engine='xlsxwriter') as writer:
            df_final.to_excel(writer, sheet_name='Prospects', index=False)

            wb = writer.book
            ws = writer.sheets['Prospects']

            # --- FORMATS ---
            header_fmt = wb.add_format({
                'bold': True, 'bg_color': '#1a1a2e', 'font_color': '#e0e0e0',
                'border': 1, 'text_wrap': True, 'valign': 'vcenter',
                'font_name': 'Calibri', 'font_size': 10,
            })
            money_fmt = wb.add_format({
                'num_format': '#,##0.00', 'border': 1,
                'font_name': 'Calibri', 'font_size': 10,
            })
            cell_fmt = wb.add_format({
                'border': 1, 'text_wrap': True, 'valign': 'vcenter',
                'font_name': 'Calibri', 'font_size': 10,
            })
            score_fmts = {
                'A': wb.add_format({
                    'bold': True, 'bg_color': '#27ae60', 'font_color': 'white',
                    'border': 1, 'align': 'center', 'font_name': 'Calibri', 'font_size': 11,
                }),
                'B': wb.add_format({
                    'bold': True, 'bg_color': '#f39c12', 'font_color': 'white',
                    'border': 1, 'align': 'center', 'font_name': 'Calibri', 'font_size': 11,
                }),
                'C': wb.add_format({
                    'bold': True, 'bg_color': '#e74c3c', 'font_color': 'white',
                    'border': 1, 'align': 'center', 'font_name': 'Calibri', 'font_size': 11,
                }),
                'D': wb.add_format({
                    'bold': True, 'bg_color': '#7f8c8d', 'font_color': 'white',
                    'border': 1, 'align': 'center', 'font_name': 'Calibri', 'font_size': 11,
                }),
            }

            # --- HEADERS ---
            for col_num, value in enumerate(df_final.columns.values):
                ws.write(0, col_num, value, header_fmt)

            # --- DATA avec formatage ---
            for row_num in range(len(df_final)):
                row_data = df_final.iloc[row_num]

                for col_num, col_name in enumerate(df_final.columns):
                    val = row_data.iloc[col_num]

                    # Score : couleur
                    if col_num == 0:
                        fmt = score_fmts.get(val, score_fmts['D'])
                        ws.write(row_num + 1, col_num, val, fmt)
                    # CA et Résultat : format monétaire
                    elif col_name in ["Chiffre d'Affaires (M€)", "Résultat Net (M€)"]:
                        if pd.notna(val) and val != '':
                            ws.write_number(row_num + 1, col_num, float(val), money_fmt)
                        else:
                            ws.write(row_num + 1, col_num, '', cell_fmt)
                    else:
                        ws.write(row_num + 1, col_num, str(val) if pd.notna(val) else '', cell_fmt)

            # --- LARGEURS ---
            widths = {
                'Score': 7, 'Qualification': 30, 'Entreprise': 35,
                "Chiffre d'Affaires (M€)": 18, 'Évolution CA': 22,
                'Résultat Net (M€)': 16, "Secteur d'Activité": 30,
                'Dirigeant Principal': 25, 'Téléphone': 14, 'Email': 25,
                'Site Web': 25, 'Adresse du Siège': 35, 'Ville': 15,
                'Région': 18, 'Effectif': 18, 'Date de Création': 14,
                'Forme Juridique': 14, 'SIREN': 12, 'Fiche Pappers': 40,
                'Résumé Activité': 40, 'Analyse M&A': 40,
                'Justification Score': 35,
            }
            for col_num, col_name in enumerate(df_final.columns):
                ws.set_column(col_num, col_num, widths.get(col_name, 15))

            # Fige header + auto-filtre
            ws.freeze_panes(1, 0)
            ws.autofilter(0, 0, len(df_final), len(df_final.columns) - 1)

            # Hauteur header
            ws.set_row(0, 30)

        if output_file:
            with open(output_file, 'rb') as f:
                return f.read()

        return buffer.getvalue()
