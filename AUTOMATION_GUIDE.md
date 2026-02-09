# 🤖 Guide d'automatisation avec n8n & Make

## 📋 Vue d'ensemble

Ce guide explique comment automatiser complètement le scraping de prospects avec :
- **n8n** (self-hosted, gratuit, recommandé)
- **Make** (cloud, payant, plus simple)

---

## 🔥 OPTION 1 : n8n (RECOMMANDÉ)

### Pourquoi n8n ?

✅ **Gratuit** et open-source  
✅ **Self-hosted** (contrôle total)  
✅ **Pas de limite** de temps d'exécution  
✅ **Intégrations** infinies (Google Drive, Slack, Email, etc.)

---

### Installation de n8n

#### A. Via Docker (le plus simple)

```bash
docker run -it --rm \
  --name n8n \
  -p 5678:5678 \
  -v ~/.n8n:/home/node/.n8n \
  n8nio/n8n
```

Accède à : `http://localhost:5678`

#### B. Via npm

```bash
npm install -g n8n
n8n start
```

---

### Workflow n8n : Architecture

```
┌─────────────────────────────────────────────────────────┐
│  1. SCHEDULE TRIGGER (Cron)                             │
│     → Tous les lundis 9h                                │
└──────────────────┬──────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────────┐
│  2. HTTP REQUEST                                         │
│     → POST vers ton API Python                          │
│     → Body : filtres (CA, région, secteur, etc.)        │
└──────────────────┬──────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────────┐
│  3. IF NODE (check success)                             │
│     → Si scraping OK → continue                         │
│     → Si erreur → envoie notification erreur            │
└──────────────────┬──────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────────┐
│  4. HTTP REQUEST (download)                              │
│     → GET /download/<filename>                          │
│     → Récupère le fichier Excel                         │
└──────────────────┬──────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────────┐
│  5. GOOGLE DRIVE                                         │
│     → Upload du fichier dans un dossier                 │
└──────────────────┬──────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────────┐
│  6. SLACK / EMAIL                                        │
│     → Notification : "Nouveau fichier prospects dispo" │
└─────────────────────────────────────────────────────────┘
```

---

### Configuration détaillée

#### 1. Schedule Trigger

**Node** : `Schedule Trigger`

**Config** :
- Mode : `Every Week`
- Day : `Monday`
- Hour : `9`
- Minute : `0`

Ou en **Cron Expression** :
```
0 9 * * 1
```

---

#### 2. HTTP Request (Lance le scraping)

**Node** : `HTTP Request`

**Config** :
- Method : `POST`
- URL : `http://TON_SERVEUR:5000/scrape`
- Body :
  ```json
  {
    "ca_min": 5000000,
    "ca_max": 50000000,
    "region": "11",
    "secteur_naf": "62",
    "forme_juridique": "SAS",
    "limit": 100
  }
  ```
- Headers :
  ```
  Content-Type: application/json
  ```

**Note** : Remplace `TON_SERVEUR` par :
- `localhost` si n8n et Python sur même machine
- IP publique ou domaine si hébergé ailleurs

---

#### 3. IF Node (Vérification)

**Node** : `IF`

**Config** :
- Condition : `{{ $json.status }}` equals `success`

**Branches** :
- **True** → Continue vers download
- **False** → Envoie notification erreur

---

#### 4. HTTP Request (Download du fichier)

**Node** : `HTTP Request`

**Config** :
- Method : `GET`
- URL : `http://TON_SERVEUR:5000{{ $json.download_url }}`
- Response Format : `File`

---

#### 5. Google Drive Upload

**Node** : `Google Drive`

**Config** :
- Operation : `Upload`
- File : `{{ $binary.data }}`
- Name : `{{ $json.file }}`
- Parents : `[ID_DU_DOSSIER]`

**Obtenir l'ID du dossier** :
- Ouvre le dossier dans Google Drive
- URL : `https://drive.google.com/drive/folders/XXXXXX`
- `XXXXXX` = ID du dossier

---

#### 6. Slack / Email

**Option A : Slack**

**Node** : `Slack`

**Config** :
- Channel : `#prospects`
- Message :
  ```
  🎯 Nouveau fichier prospects disponible !
  
  📊 Stats :
  - Total : {{ $node["HTTP Request 1"].json.stats.total }}
  - Score A : {{ $node["HTTP Request 1"].json.stats.score_a }}
  - Score B : {{ $node["HTTP Request 1"].json.stats.score_b }}
  
  📂 Fichier : {{ $node["HTTP Request 1"].json.file }}
  ```

**Option B : Email**

**Node** : `Send Email`

**Config** :
- To : `ton@email.com`
- Subject : `[Prospects] Nouveau fichier disponible`
- Body :
  ```html
  <h2>🎯 Scraping terminé</h2>
  
  <p>Un nouveau fichier de prospects est disponible.</p>
  
  <h3>📊 Statistiques</h3>
  <ul>
    <li>Total : {{ $node["HTTP Request 1"].json.stats.total }}</li>
    <li>Score A : {{ $node["HTTP Request 1"].json.stats.score_a }}</li>
    <li>Score B : {{ $node["HTTP Request 1"].json.stats.score_b }}</li>
  </ul>
  
  <p>Le fichier a été uploadé sur Google Drive.</p>
  ```

---

### Hébergement de l'API Python

Tu as plusieurs options :

#### Option A : VPS (DigitalOcean, OVH, etc.)

**Coût** : ~5€/mois

**Étapes** :
1. Loue un VPS Ubuntu
2. Installe Python, clone ton repo
3. Lance l'API :
   ```bash
   python api_server.py
   ```
4. Utilise `screen` ou `tmux` pour que ça tourne en background
5. Configure un domaine ou utilise l'IP publique

#### Option B : Heroku

**Coût** : Gratuit (plan hobby) ou 7$/mois

**Étapes** :
1. Crée un `Procfile` :
   ```
   web: python api_server.py
   ```
2. Deploy via Git :
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   heroku create ton-app-scraper
   git push heroku main
   ```
3. URL : `https://ton-app-scraper.herokuapp.com`

#### Option C : Render

**Coût** : Gratuit (avec limitations)

**Étapes** :
1. Connecte ton repo GitHub
2. Configure :
   - Build : `pip install -r requirements.txt`
   - Start : `python api_server.py`
3. URL auto-générée

---

### Workflow n8n complet (JSON)

Copie-colle ce workflow dans n8n (Import → Paste JSON) :

```json
{
  "name": "Scraper Prospects B2B",
  "nodes": [
    {
      "parameters": {
        "rule": {
          "interval": [
            {
              "field": "cronExpression",
              "expression": "0 9 * * 1"
            }
          ]
        }
      },
      "name": "Schedule Trigger",
      "type": "n8n-nodes-base.scheduleTrigger",
      "position": [250, 300]
    },
    {
      "parameters": {
        "method": "POST",
        "url": "http://localhost:5000/scrape",
        "jsonParameters": true,
        "options": {},
        "bodyParametersJson": "{\n  \"ca_min\": 5000000,\n  \"ca_max\": 50000000,\n  \"region\": \"11\",\n  \"secteur_naf\": \"62\",\n  \"limit\": 100\n}"
      },
      "name": "Scrape API",
      "type": "n8n-nodes-base.httpRequest",
      "position": [450, 300]
    },
    {
      "parameters": {
        "method": "GET",
        "url": "=http://localhost:5000{{ $json.download_url }}",
        "options": {
          "response": {
            "response": {
              "responseFormat": "file"
            }
          }
        }
      },
      "name": "Download File",
      "type": "n8n-nodes-base.httpRequest",
      "position": [650, 300]
    },
    {
      "parameters": {
        "operation": "upload",
        "fileContent": "={{ $binary.data }}",
        "name": "={{ $node[\"Scrape API\"].json.file }}",
        "parents": ["TON_FOLDER_ID"]
      },
      "name": "Google Drive",
      "type": "n8n-nodes-base.googleDrive",
      "position": [850, 300]
    },
    {
      "parameters": {
        "channel": "#prospects",
        "text": "=🎯 Nouveau fichier prospects !\n\n📊 Total : {{ $node[\"Scrape API\"].json.stats.total }}\n- Score A : {{ $node[\"Scrape API\"].json.stats.score_a }}\n- Score B : {{ $node[\"Scrape API\"].json.stats.score_b }}"
      },
      "name": "Slack",
      "type": "n8n-nodes-base.slack",
      "position": [1050, 300]
    }
  ],
  "connections": {
    "Schedule Trigger": {
      "main": [[{"node": "Scrape API"}]]
    },
    "Scrape API": {
      "main": [[{"node": "Download File"}]]
    },
    "Download File": {
      "main": [[{"node": "Google Drive"}]]
    },
    "Google Drive": {
      "main": [[{"node": "Slack"}]]
    }
  }
}
```

---

## 🌐 OPTION 2 : Make (ex-Integromat)

### Pourquoi Make ?

✅ **Interface visuelle** intuitive  
✅ **Pas besoin d'héberger**  
⚠️ **Payant** (~9€/mois)  
⚠️ **Limite de timeout** (40 min max)

---

### Workflow Make

**Modules** :

1. **Schedule**
   - Trigger : `Every Monday at 9:00 AM`

2. **HTTP - Make a Request**
   - URL : `http://TON_SERVEUR:5000/scrape`
   - Method : `POST`
   - Body :
     ```json
     {
       "ca_min": 5000000,
       "ca_max": 50000000,
       "region": "11",
       "secteur_naf": "62"
     }
     ```

3. **HTTP - Make a Request**
   - URL : `{{2.download_url}}`
   - Method : `GET`

4. **Google Drive - Upload a File**
   - File : `{{3.data}}`
   - Folder : Sélectionne ton dossier

5. **Email - Send an Email**
   - To : `ton@email.com`
   - Subject : `Nouveau fichier prospects`
   - Body : `Total : {{2.stats.total}}`

---

## 🔧 OPTION 3 : GitHub Actions (Gratuit)

Si tu veux tout héberger gratuitement :

**Fichier** : `.github/workflows/scrape.yml`

```yaml
name: Scrape Prospects

on:
  schedule:
    - cron: '0 9 * * 1'  # Lundi 9h
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
      
      - name: Install deps
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
          folder: ${{ secrets.DRIVE_FOLDER_ID }}
```

**Secrets à configurer** (dans GitHub Settings) :
- `ANTHROPIC_API_KEY`
- `GOOGLE_DRIVE_CREDENTIALS`
- `DRIVE_FOLDER_ID`

---

## 📊 Comparatif

| Critère | n8n | Make | GitHub Actions |
|---------|-----|------|----------------|
| **Prix** | Gratuit | ~9€/mois | Gratuit |
| **Hébergement** | Self-hosted | Cloud | Cloud |
| **Timeout** | ∞ | 40 min | 6h |
| **Interface** | UI + Code | UI only | Code only |
| **Flexibilité** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Facilité** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |

---

## 🎯 Recommandation finale

**Pour débuter** : Make (si budget OK) ou GitHub Actions (si tech-savvy)

**Pour production** : n8n (contrôle total, gratuit, scalable)

**Setup idéal** :
- API Python hébergée sur VPS (5€/mois)
- n8n sur le même VPS
- Workflow automatisé 1x/semaine
- Upload auto sur Google Drive
- Notifications Slack

**Coût total** : ~5-10€/mois + API Claude (~$10-20/mois pour 1000 prospects)

---

## 🆘 Besoin d'aide ?

Si tu veux que je t'aide à :
- Configurer n8n pas à pas
- Héberger l'API sur un VPS
- Créer le workflow complet

Dis-moi ce qui bloque ! 🚀
