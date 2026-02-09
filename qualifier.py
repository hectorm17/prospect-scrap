"""
Qualification des prospects avec Claude (Anthropic API)
Score A/B/C/D + justification pour chaque entreprise
"""

import anthropic
import pandas as pd
from typing import Dict, List
from tqdm import tqdm
import time
import json
import config


class ProspectQualifier:
    """Qualifie les prospects avec l'IA Claude"""
    
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-20250514"
    
    def build_analysis_prompt(self, company_data: Dict) -> str:
        """Construit le prompt pour analyser une entreprise"""
        
        # Prépare les données
        nom = company_data.get('nom_entreprise', 'N/A')
        siren = company_data.get('siren', 'N/A')
        secteur = company_data.get('libelle_naf', company_data.get('activite_desc', 'N/A'))
        ca = company_data.get('ca_euros', 0)
        ca_formatted = f"{ca/1_000_000:.1f} M€" if ca else "N/A"
        
        forme = company_data.get('forme_juridique', 'N/A')
        date_creation = company_data.get('date_creation', 'N/A')
        dirigeant = company_data.get('dirigeant_nom', company_data.get('dirigeant_principal', 'N/A'))
        fonction = company_data.get('dirigeant_fonction', '')
        ville = company_data.get('ville', 'N/A')
        region = company_data.get('region', 'N/A')
        effectif = company_data.get('tranche_effectif', company_data.get('effectif', 'N/A'))
        resultat = company_data.get('resultat', 'N/A')
        site_web = company_data.get('site_web', '')
        url_pappers = company_data.get('url_pappers', '')
        
        prompt = f"""Tu es un analyste corporate / M&A spécialisé dans les PME françaises.

**ENTREPRISE À ANALYSER**

- Nom : {nom}
- SIREN : {siren}
- Secteur : {secteur}
- Chiffre d'affaires : {ca_formatted}
- Résultat : {resultat}
- Forme juridique : {forme}
- Date de création : {date_creation}
- Dirigeant : {dirigeant} {f'({fonction})' if fonction else ''}
- Localisation : {ville}, {region}
- Effectif : {effectif}
- Site web : {site_web if site_web else 'Non disponible'}
- Pappers : {url_pappers}

---

**MISSION**

Analyse cette entreprise selon les critères suivants :

1. **Taille** : CA entre 5 et 50 M€
2. **Croissance** : stable, modérée ou forte (si inférable)
3. **Complexité** : mono-activité vs diversifiée, B2B vs B2C
4. **Structure capitalistique** : fondateur/famille/fonds (si identifiable)
5. **Maturité** : PME peu structurée vs déjà très accompagnée
6. **Signaux M&A** : acquisitions, levées, LBO visibles (ou absence)

⚠️ Tu travailles uniquement sur données publiques. Ne fais jamais d'affirmations certaines sur l'accompagnement existant.

---

**FORMAT DE RÉPONSE (STRICT)**

Réponds UNIQUEMENT au format JSON suivant :

{{
  "resume_business": "Description activité en 3-4 lignes max : activité réelle, type clients, positionnement, modèle économique",
  "analyse_fit": "Analyse corporate advisory fit en 4-5 lignes : taille, complexité, structure, maturité, signaux M&A",
  "score": "A, B, C ou D",
  "justification": "Justification du score en 2-3 lignes max"
}}

**SCORES**
- **A** = Prospect prioritaire (fondateur indépendant, CA intéressant, peu de signaux d'accompagnement existant)
- **B** = Prospect intéressant mais secondaire (CA correct, structure moyenne)
- **C** = Peu pertinent à court terme (très petite ou très grosse PME, ou secteur peu adapté)
- **D** = Hors cible (critères non remplis)

Réponds UNIQUEMENT en JSON, sans aucun texte avant ou après."""

        return prompt
    
    def analyze_company(self, company_data: Dict) -> Dict:
        """
        Analyse une entreprise avec Claude
        
        Returns:
            Dict avec resume_business, analyse_fit, score, justification
        """
        try:
            prompt = self.build_analysis_prompt(company_data)
            
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            # Extrait le JSON de la réponse
            content = response.content[0].text

            # Nettoie le markdown si présent (```json ... ```)
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]
            content = content.strip()

            # Parse le JSON
            result = json.loads(content)
            
            # Validation
            required_keys = ['resume_business', 'analyse_fit', 'score', 'justification']
            if not all(k in result for k in required_keys):
                raise ValueError("Réponse IA incomplète")
            
            # Normalise le score
            score = result['score'].upper().strip()
            if score not in ['A', 'B', 'C', 'D']:
                score = 'C'  # Par défaut
            
            result['score'] = score
            result['score_label'] = config.SCORING_CATEGORIES.get(score, '')
            
            return result
            
        except json.JSONDecodeError:
            print(f"  ⚠️ Erreur parsing JSON pour {company_data.get('nom_entreprise', 'N/A')}")
            return self._default_analysis()
        except Exception as e:
            print(f"  ⚠️ Erreur analyse IA: {e}")
            return self._default_analysis()
    
    def _default_analysis(self) -> Dict:
        """Analyse par défaut en cas d'erreur"""
        return {
            'resume_business': 'Analyse non disponible',
            'analyse_fit': 'Analyse non disponible',
            'score': 'C',
            'score_label': config.SCORING_CATEGORIES['C'],
            'justification': 'Erreur lors de l\'analyse automatique',
        }
    
    def qualify_dataframe(self, df: pd.DataFrame, batch_size: int = 5) -> pd.DataFrame:
        """
        Qualifie toutes les entreprises d'un DataFrame
        
        Args:
            df: DataFrame avec les entreprises
            batch_size: Nombre d'analyses avant pause (rate limiting)
        
        Returns:
            DataFrame avec colonnes d'analyse ajoutées
        """
        print("\n🤖 Qualification IA des prospects...\n")
        
        qualified_data = []
        
        for idx, row in tqdm(df.iterrows(), total=len(df), desc="Qualification"):
            company_data = row.to_dict()
            
            # Analyse IA
            analysis = self.analyze_company(company_data)
            
            # Fusionne
            qualified_row = {
                **company_data,
                **analysis
            }
            
            qualified_data.append(qualified_row)
            
            # Pause tous les batch_size pour éviter rate limiting
            if (idx + 1) % batch_size == 0:
                time.sleep(2)
        
        qualified_df = pd.DataFrame(qualified_data)
        
        # Trie par score
        score_order = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
        qualified_df['score_order'] = qualified_df['score'].map(score_order)
        qualified_df = qualified_df.sort_values('score_order').drop('score_order', axis=1)
        
        print(f"\n✅ {len(qualified_df)} prospects qualifiés")
        print("\n📊 Répartition des scores:")
        print(qualified_df['score'].value_counts().sort_index())
        
        return qualified_df
    
    def format_excel_output(self, df: pd.DataFrame, output_file: str):
        """
        Formate et exporte le fichier Excel final
        """
        # Réorganise les colonnes
        columns_order = [
            # Scoring
            'score',
            'score_label',
            
            # Identité
            'nom_entreprise',
            'siren',
            'forme_juridique',
            
            # Business
            'ca_euros',
            'resultat',
            'secteur',
            'libelle_naf',
            'activite_desc',
            
            # Dirigeant
            'dirigeant_nom',
            'dirigeant_fonction',
            
            # Localisation
            'ville',
            'code_postal',
            'region',
            'adresse_complete',
            
            # Contact
            'telephone',
            'email',
            'site_web',
            
            # Analyse IA
            'resume_business',
            'analyse_fit',
            'justification',
            
            # Infos complémentaires
            'date_creation',
            'tranche_effectif',
            'effectif',
            
            # Liens
            'url_pappers',
        ]
        
        # Garde seulement les colonnes existantes
        existing_columns = [col for col in columns_order if col in df.columns]
        df_export = df[existing_columns].copy()
        
        # Formate le CA
        if 'ca_euros' in df_export.columns:
            df_export['ca_m_euros'] = (df_export['ca_euros'] / 1_000_000).round(2)
            df_export = df_export.drop('ca_euros', axis=1)
        
        # Export Excel avec formatage
        with pd.ExcelWriter(output_file, engine='xlsxwriter') as writer:
            df_export.to_excel(writer, sheet_name='Prospects', index=False)
            
            workbook = writer.book
            worksheet = writer.sheets['Prospects']
            
            # Formats
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#4472C4',
                'font_color': 'white',
                'border': 1
            })
            
            score_a_format = workbook.add_format({'bg_color': '#C6EFCE', 'bold': True})
            score_b_format = workbook.add_format({'bg_color': '#FFEB9C'})
            score_c_format = workbook.add_format({'bg_color': '#FFC7CE'})
            score_d_format = workbook.add_format({'bg_color': '#CCCCCC'})
            
            # Applique header format
            for col_num, value in enumerate(df_export.columns.values):
                worksheet.write(0, col_num, value, header_format)
            
            # Applique couleurs selon score
            score_col = df_export.columns.get_loc('score')
            for row_num in range(1, len(df_export) + 1):
                score = df_export.iloc[row_num - 1]['score']
                if score == 'A':
                    worksheet.write(row_num, score_col, score, score_a_format)
                elif score == 'B':
                    worksheet.write(row_num, score_col, score, score_b_format)
                elif score == 'C':
                    worksheet.write(row_num, score_col, score, score_c_format)
                else:
                    worksheet.write(row_num, score_col, score, score_d_format)
            
            # Ajuste largeurs colonnes
            worksheet.set_column('A:A', 8)   # Score
            worksheet.set_column('B:B', 30)  # Score label
            worksheet.set_column('C:C', 35)  # Nom entreprise
            worksheet.set_column('D:E', 15)  # SIREN, forme
            worksheet.set_column('F:H', 12)  # CA, résultat, secteur
        
        print(f"\n✅ Fichier Excel final créé: {output_file}")


def main():
    """Test du qualifier"""
    import glob
    import os
    from datetime import datetime
    
    # Vérifie la clé API
    if not config.ANTHROPIC_API_KEY or config.ANTHROPIC_API_KEY == "sk-ant-xxxxx":
        print("❌ ERREUR: Configure ta clé API Anthropic dans config.py")
        print("   Obtiens-la sur: https://console.anthropic.com/")
        return
    
    # Charge le fichier enrichi le plus récent
    files = glob.glob("outputs/enriched_*.xlsx")
    if not files:
        print("❌ Aucun fichier enrichi trouvé. Lance enricher.py d'abord")
        return
    
    latest = max(files, key=os.path.getctime)
    print(f"📂 Chargement: {latest}")
    
    df = pd.read_excel(latest)
    
    # Qualifier
    qualifier = ProspectQualifier(config.ANTHROPIC_API_KEY)
    qualified_df = qualifier.qualify_dataframe(df)
    
    # Sauvegarde
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"outputs/prospects_qualified_{timestamp}.xlsx"
    qualifier.format_excel_output(qualified_df, output_file)


if __name__ == "__main__":
    main()
