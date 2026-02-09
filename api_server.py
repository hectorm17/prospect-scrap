"""
API Flask pour automatisation avec n8n, Make ou Zapier
Expose le scraper via endpoint HTTP

Usage:
    python api_server.py
    
    Puis dans n8n/Make :
    POST http://localhost:5000/scrape
    Body: {
        "ca_min": 5000000,
        "ca_max": 50000000,
        "region": "11",
        "secteur_naf": "62",
        "forme_juridique": "SAS",
        "limit": 50
    }
"""

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os
from datetime import datetime
from run_all import run_pipeline
import config

app = Flask(__name__)
CORS(app)  # Permet les requêtes cross-origin

@app.route('/', methods=['GET'])
def home():
    """Page d'accueil de l'API"""
    return jsonify({
        'status': 'online',
        'service': 'Scraper Prospects B2B',
        'version': '1.0',
        'endpoints': {
            '/scrape': 'POST - Lance le scraping avec filtres custom',
            '/health': 'GET - Vérifie l\'état du service',
            '/download/<filename>': 'GET - Télécharge un fichier généré'
        }
    })


@app.route('/health', methods=['GET'])
def health():
    """Health check pour monitoring"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'api_configured': config.ANTHROPIC_API_KEY != "sk-ant-xxxxx"
    })


@app.route('/scrape', methods=['POST'])
def scrape():
    """
    Endpoint principal de scraping
    
    Body JSON attendu:
    {
        "ca_min": 5000000,       // Optionnel (défaut: config)
        "ca_max": 50000000,      // Optionnel
        "region": "11",          // Optionnel
        "secteur_naf": "62",     // Optionnel
        "forme_juridique": "SAS", // Optionnel
        "limit": 50,             // Optionnel
        "age_min": 3             // Optionnel
    }
    
    Returns:
    {
        "status": "success",
        "file": "prospects_qualified_20240209_153045.xlsx",
        "download_url": "/download/prospects_qualified_20240209_153045.xlsx",
        "stats": {
            "total": 42,
            "score_a": 12,
            "score_b": 18,
            "score_c": 10,
            "score_d": 2
        }
    }
    """
    
    try:
        # Récupère les filtres du body (ou utilise config par défaut)
        data = request.get_json() or {}
        
        filtres = {
            'ca_min': data.get('ca_min', config.FILTRES['ca_min']),
            'ca_max': data.get('ca_max', config.FILTRES['ca_max']),
            'region': data.get('region', config.FILTRES.get('region')),
            'secteur_naf': data.get('secteur_naf', config.FILTRES.get('secteur_naf')),
            'forme_juridique': data.get('forme_juridique', config.FILTRES.get('forme_juridique')),
            'age_min': data.get('age_min', config.FILTRES.get('age_min', 0)),
            'limit': data.get('limit', config.FILTRES.get('limit')),
        }
        
        # Lance le pipeline
        result_file = run_pipeline(filtres)
        
        if not result_file:
            return jsonify({
                'status': 'error',
                'message': 'Aucune entreprise trouvée avec ces filtres'
            }), 404
        
        # Lit les stats du fichier
        import pandas as pd
        df = pd.read_excel(result_file)
        
        stats = {
            'total': len(df)
        }
        
        if 'score' in df.columns:
            score_counts = df['score'].value_counts()
            stats.update({
                'score_a': int(score_counts.get('A', 0)),
                'score_b': int(score_counts.get('B', 0)),
                'score_c': int(score_counts.get('C', 0)),
                'score_d': int(score_counts.get('D', 0)),
            })
        
        filename = os.path.basename(result_file)
        
        return jsonify({
            'status': 'success',
            'message': 'Scraping terminé avec succès',
            'file': filename,
            'download_url': f'/download/{filename}',
            'stats': stats,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/download/<filename>', methods=['GET'])
def download(filename):
    """
    Télécharge un fichier généré
    
    Usage:
        GET /download/prospects_qualified_20240209_153045.xlsx
    """
    
    try:
        filepath = os.path.join('outputs', filename)
        
        if not os.path.exists(filepath):
            return jsonify({
                'status': 'error',
                'message': 'Fichier non trouvé'
            }), 404
        
        return send_file(
            filepath,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/files', methods=['GET'])
def list_files():
    """
    Liste tous les fichiers générés
    
    Returns:
    {
        "files": [
            {
                "name": "prospects_qualified_20240209_153045.xlsx",
                "created": "2024-02-09T15:30:45",
                "size": 125000,
                "download_url": "/download/prospects_qualified_20240209_153045.xlsx"
            }
        ]
    }
    """
    
    try:
        import glob
        
        files = glob.glob('outputs/prospects_qualified_*.xlsx')
        
        result = []
        for filepath in files:
            filename = os.path.basename(filepath)
            stat = os.stat(filepath)
            
            result.append({
                'name': filename,
                'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                'size': stat.st_size,
                'download_url': f'/download/{filename}'
            })
        
        # Trie par date (plus récent d'abord)
        result.sort(key=lambda x: x['created'], reverse=True)
        
        return jsonify({
            'status': 'success',
            'count': len(result),
            'files': result
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


if __name__ == '__main__':
    # Crée le dossier outputs
    os.makedirs('outputs', exist_ok=True)
    
    print("\n" + "="*60)
    print("🚀 API SCRAPER PROSPECTS B2B")
    print("="*60)
    print("\nEndpoints disponibles :")
    print("  GET  /             - Informations API")
    print("  GET  /health       - Health check")
    print("  POST /scrape       - Lance le scraping")
    print("  GET  /download/<f> - Télécharge un fichier")
    print("  GET  /files        - Liste les fichiers")
    print("\n" + "="*60)
    print("Serveur démarré sur http://localhost:5000")
    print("Appuie sur Ctrl+C pour arrêter")
    print("="*60 + "\n")
    
    # Lance le serveur
    app.run(
        host='0.0.0.0',  # Accessible depuis l'extérieur
        port=5000,
        debug=True
    )
