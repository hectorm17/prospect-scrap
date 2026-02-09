# 🎯 Scraper Prospects B2B - Documentation Complète

Outil automatisé pour scraper, enrichir et qualifier des prospects PME françaises via :
- **Data.gouv.fr** (base publique des entreprises)
- **Pappers** (enrichissement données)
- **Claude AI** (qualification intelligente)

---

## 📋 Table des matières

1. [Installation](#installation)
2. [Configuration](#configuration)
3. [Utilisation - Interface Web](#utilisation-interface-web)
4. [Utilisation - Ligne de commande](#utilisation-ligne-de-commande)
5. [Automatisation avec n8n/Make](#automatisation-avec-n8nmake)
6. [Structure des fichiers](#structure-des-fichiers)
7. [FAQ](#faq)

---

## 🚀 Installation

### Prérequis

- **Python 3.9+** installé
- Compte **Anthropic** (pour la qualification IA)

### Étapes

1. **Clone ou télécharge le dossier** `prospect-scraper/`

2. **Installe les dépendances** :

```bash
cd prospect-scraper
pip install -r requirements.txt
```

3. **Crée le dossier de sortie** :

```bash
mkdir outputs
```

---

## ⚙️ Configuration

### 1. Clé API Anthropic

Obtiens ta clé API sur [console.anthropic.com](https://console.anthropic.com/)

Édite **`config.py`** et remplace :

```python
ANTHROPIC_API_KEY = "sk-ant-xxxxx"  # ← Mets ta vraie clé ici
```

### 2. Personnalise les filtres (optionnel)

Dans **`config.py`**, modifie les filtres par défaut :

```python
FILTRES = {
    "ca_min": 5_000_000,      # 5 M€
    "ca_max": 50_000_000,     # 50 M€
    "region": "11",           # Île-de-France
    "secteur_naf": "62",      # Programmation informatique
    "forme_juridique": "SAS",
    "limit": 50,              # Pour tests
}
```

**Codes utiles** :

Régions :
- `11` = Île-de-France
- `84` = Auvergne-Rhône-Alpes
- `93` = PACA
- `None` = Toute la France

Secteurs NAF :
- `62` = Informatique
- `41-43` = Construction
- `46-47` = Commerce
- `69-74` = Services B2B
- `None` = Tous secteurs

---

## 🖥️ Utilisation - Interface Web

### Lancement

```bash
streamlit run app.py
```

L'interface s'ouvre dans ton navigateur.

### Workflow

1. **Configure les filtres** :
   - CA min/max
   - Région
   - Secteur NAF
   - Forme juridique
   - Limite de résultats (pour tester)

2. **Entre ta clé API** Anthropic dans la sidebar

3. **Lance la recherche** → Le système :
   - ✅ Scrape data.gouv.fr
   - ✅ Enrichit via Pappers
   - ✅ Qualifie avec Claude AI
   - ✅ Génère un Excel avec tout dedans

4. **Télécharge le fichier** Excel final

### Exemple de résultat

Fichier Excel avec :
- Score A/B/C/D
- Nom, SIREN, CA, secteur
- Dirigeant, téléphone, email, site web
- Résumé business (3-4 lignes)
- Analyse corporate fit
- Justification du score

---

## 💻 Utilisation - Ligne de commande

Si tu préfères les scripts :

### 1. Scraping data.gouv

```bash
python scraper.py
```

Génère : `outputs/data_gouv_raw_YYYYMMDD_HHMMSS.xlsx`

### 2. Enrichissement Pappers

```bash
python enricher.py
```

Prend le fichier brut le plus récent, l'enrichit.

Génère : `outputs/enriched_YYYYMMDD_HHMMSS.xlsx`

### 3. Qualification IA

```bash
python qualifier.py
```

Prend le fichier enrichi, qualifie chaque prospect.

Génère : `outputs/prospects_qualified_YYYYMMDD_HHMMSS.xlsx`

### Pipeline complet (1 commande)

Crée un script `run_all.py` :

```python
import os
from datetime import datetime
from scraper import DataGouvScraper
from enricher import PappersEnricher
from qualifier import ProspectQualifier
import config

# Filtres
filtres = config.FILTRES

# 1. Scraping
scraper = DataGouvScraper()
companies = scraper.search_companies(filtres)
df = scraper.to_dataframe(companies)

# 2. Enrichissement
enricher = PappersEnricher()
df = enricher.enrich_dataframe(df)

# 3. Qualification
qualifier = ProspectQualifier(config.ANTHROPIC_API_KEY)
df = qualifier.qualify_dataframe(df)

# 4. Export
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output = f"outputs/prospects_qualified_{timestamp}.xlsx"
qualifier.format_excel_output(df, output)

print(f"\n✅ Terminé : {output}")
```

Puis lance :

```bash
python run_all.py
```

---

## 🤖 Automatisation avec n8n/Make

### Option 1 : n8n (Recommandé pour self-hosted)

**Architecture** :

```
Trigger (Cron 1x/semaine)
    ↓
HTTP Request → Python script sur serveur
    ↓
Webhook → Récupère Excel
    ↓
Google Drive → Upload du fichier
    ↓
Slack/Email → Notification
```

**Étapes** :

1. **Héberge le script Python** sur un serveur (VPS, Render, Heroku)

2. **Crée une API Flask** pour exposer le scraper :

```python
# api.py
from flask import Flask, send_file, request
import run_all  # Ton script

app = Flask(__name__)

@app.route('/scrape', methods=['POST'])
def scrape():
    # Récupère les filtres du POST
    filtres = request.json
    
    # Lance le pipeline
    output_file = run_all.run_pipeline(filtres)
    
    # Retourne le fichier
    return send_file(output_file, as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

3. **Dans n8n** :

- Node **Schedule Trigger** : Cron `0 9 * * 1` (tous les lundis 9h)
- Node **HTTP Request** : POST vers ton API `/scrape`
- Node **Google Drive** : Upload du fichier
- Node **Slack** : Notification "Nouveau fichier prospects dispo !"

### Option 2 : Make (Zapier-like, no-code)

**Workflow** :

1. **Trigger** : Schedule (1x/semaine)
2. **HTTP** : Appelle ton API Python
3. **Webhooks** : Reçoit le fichier Excel
4. **Google Drive** : Upload
5. **Email** : Notification

**Limitations** : Make a des limites de timeout (quelques minutes max), donc il faut que ton scraper soit rapide ou découpe en plusieurs étapes.

### Option 3 : GitHub Actions (Gratuit)

Crée `.github/workflows/scrape.yml` :

```yaml
name: Scrape Prospects

on:
  schedule:
    - cron: '0 9 * * 1'  # Tous les lundis 9h
  workflow_dispatch:  # Bouton manuel

jobs:
  scrape:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Run scraper
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: python run_all.py
      
      - name: Upload to Google Drive
        uses: satackey/action-google-drive@v1
        with:
          credentials: ${{ secrets.GOOGLE_DRIVE_CREDENTIALS }}
          file: outputs/prospects_qualified_*.xlsx
```

---

## 📁 Structure des fichiers

```
prospect-scraper/
│
├── config.py              # Configuration et filtres
├── scraper.py             # Scraper data.gouv.fr
├── enricher.py            # Enrichissement Pappers
├── qualifier.py           # Qualification IA Claude
├── app.py                 # Interface Streamlit
├── requirements.txt       # Dépendances Python
├── README.md              # Cette doc
│
└── outputs/               # Fichiers générés
    ├── raw_*.xlsx         # Données brutes data.gouv
    ├── enriched_*.xlsx    # Données enrichies Pappers
    └── prospects_qualified_*.xlsx  # Fichier final avec scoring
```

---

## ❓ FAQ

### Combien de temps ça prend ?

- **50 entreprises** : ~5-10 min
- **200 entreprises** : ~30-40 min
- **500 entreprises** : ~1h30-2h

Les délais viennent surtout de :
- Pappers (2 sec par entreprise pour éviter le ban)
- API Claude (rate limiting)

### Combien ça coûte ?

**Data.gouv** : Gratuit ✅

**Pappers** : 
- Scraping léger = gratuit
- API payante = 49€/mois (optionnel)

**Claude API** :
- ~$0.015 par analyse
- 100 prospects = ~$1.50
- 1000 prospects = ~$15

**Total** : Quasiment gratuit pour <500 prospects/mois.

### Puis-je utiliser sans clé API ?

Oui, mais tu n'auras pas la qualification IA.

Tu peux :
- Scraper data.gouv
- Enrichir via Pappers
- Exporter l'Excel brut

Ensuite, qualifie manuellement ou via une autre IA.

### Les données sont-elles légales ?

**100% légales** ✅

- Data.gouv = données publiques (Open Data)
- Pappers = registre public des entreprises
- Pas de données personnelles sensibles
- Usage B2B professionnel autorisé

### Puis-je changer les critères de scoring ?

Oui ! Édite le prompt dans `qualifier.py`, fonction `build_analysis_prompt()`.

Exemple : ajouter un critère "présence digitale" :

```python
prompt = f"""
...
6. Présence digitale : site web moderne/ancien, SEO, réseaux sociaux
...
"""
```

### Puis-je ajouter d'autres sources ?

Oui ! Crée un nouveau module `enricher_X.py` et intègre-le dans le pipeline.

Exemples de sources :
- Societe.com
- Infogreffe
- LinkedIn (via API Sales Navigator)
- Google Places

---

## 🆘 Support

**Problèmes courants** :

1. **"No module named X"** → `pip install -r requirements.txt`
2. **"API key invalid"** → Vérifie ta clé Anthropic dans `config.py`
3. **Rate limit exceeded** → Augmente `delay_between_requests` dans config
4. **Pas de résultats** → Élargis les filtres (CA, région, secteur)

---

## 📊 Exemple de résultat final

| Score | Nom | CA (M€) | Ville | Justification |
|-------|-----|---------|-------|---------------|
| **A** | TechCorp SAS | 12.5 | Paris | Fondateur majoritaire, CA croissant, aucun LBO visible |
| **A** | IndusPro SARL | 18.3 | Lyon | PME familiale, potentiel transmission, secteur porteur |
| **B** | ServicePlus | 8.2 | Marseille | CA stable, dirigeant en place depuis 15 ans |
| **C** | MiniCo | 6.1 | Lille | Petite structure, secteur très concurrentiel |

---

## 🚀 Prochaines étapes

1. **Teste avec 10-20 entreprises** pour valider
2. **Affine les filtres** selon tes cibles réelles
3. **Automatise** avec n8n ou GitHub Actions
4. **Ajoute des sources** (LinkedIn, Societe.com)
5. **Intègre ton CRM** (Pipedrive, HubSpot, Salesforce)

---

**Bonne prospection ! 🎯**
