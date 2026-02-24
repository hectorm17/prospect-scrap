"""
Generation de lettres Word (.docx) personnalisees a partir du template Mirabaud.
Copie le template et remplace les champs personnalisables (date, dirigeant, entreprise, secteur).
Tout le reste (header Mirabaud, footer legal, mise en page) est preserve.
"""

import os
import re
import requests
from io import BytesIO
from datetime import datetime
from urllib.parse import urlparse

from docx import Document
from docx.opc.constants import RELATIONSHIP_TYPE as RT


MOIS_FR = {
    'January': 'janvier', 'February': 'février', 'March': 'mars',
    'April': 'avril', 'May': 'mai', 'June': 'juin',
    'July': 'juillet', 'August': 'août', 'September': 'septembre',
    'October': 'octobre', 'November': 'novembre', 'December': 'décembre'
}

TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), 'templates', 'lettre_template.docx')

PRENOMS_FEMININS = {
    'maria', 'marie', 'anne', 'sophie', 'catherine', 'isabelle', 'nathalie',
    'christine', 'sylvie', 'patricia', 'florence', 'sandrine', 'valérie',
    'valerie', 'caroline', 'julie', 'laura', 'sarah', 'emma', 'alice',
    'claire', 'marguerite', 'louise', 'charlotte', 'camille', 'lucie',
    'brigitte', 'monique', 'nicole', 'danielle', 'françoise', 'francoise',
    'martine', 'véronique', 'veronique', 'dominique', 'céline', 'celine',
    'audrey', 'stéphanie', 'stephanie', 'virginie', 'delphine', 'hélène',
    'helene', 'emilie', 'alexandra', 'béatrice', 'beatrice', 'corinne',
    'myriam', 'muriel', 'chantal', 'agnès', 'agnes', 'laurence',
    'annick', 'joëlle', 'joelle', 'michèle', 'michele', 'pascale',
    'rosalie', 'sabine', 'ségolène', 'segolene', 'élise', 'elise',
    'laetitia', 'léa', 'lea', 'manon', 'océane', 'oceane', 'pauline',
    'amandine', 'mathilde', 'juliette', 'clémence', 'clemence', 'eva',
    'inès', 'ines', 'agathe', 'constance', 'gaëlle', 'gaelle',
    'madeleine', 'jeanne', 'thérèse', 'therese', 'simone', 'yvonne',
    'geneviève', 'genevieve', 'colette', 'jacqueline', 'josette',
    'mireille', 'odette', 'suzanne', 'antoinette', 'bernadette',
    'denise', 'germaine', 'henriette', 'lucienne', 'marcelle',
    'pierrette', 'renée', 'renee', 'solange', 'yvette',
}

# Fonctions a retirer du nom du dirigeant
FONCTIONS_REGEX = re.compile(
    r'\s*\((?:Administrateur|Président|Directeur[^)]*|Gérant|'
    r'PDG|DG|Membre[^)]*|Associé[^)]*|Liquidateur[^)]*|'
    r'Commissaire[^)]*|Secrétaire[^)]*)\)',
    re.IGNORECASE
)


def _clean(val, default=''):
    """Nettoie une valeur qui peut etre None, NaN, ou valide."""
    if val is None:
        return default
    if isinstance(val, float) and val != val:  # NaN check
        return default
    return str(val) if val else default


def _format_date_fr():
    """Retourne la date du jour en francais : '24 février 2026'"""
    date_str = datetime.now().strftime("%d %B %Y")
    for en, fr in MOIS_FR.items():
        date_str = date_str.replace(en, fr)
    if date_str.startswith('0'):
        date_str = date_str[1:]
    return date_str


def _detect_civilite(dirigeant_full):
    """
    Detecte la civilite (Madame/Monsieur) a partir du prenom.
    Retourne (civilite, nom_famille).
    """
    if not dirigeant_full:
        return 'Madame, Monsieur', ''

    # Retirer la fonction entre parentheses
    nom_clean = FONCTIONS_REGEX.sub('', dirigeant_full).strip()
    if not nom_clean:
        return 'Madame, Monsieur', ''

    parts = nom_clean.split()
    if len(parts) < 2:
        return 'Monsieur', nom_clean

    prenom = parts[0].lower()
    nom_famille = ' '.join(parts[1:])

    if prenom in PRENOMS_FEMININS:
        return 'Madame', nom_famille
    return 'Monsieur', nom_famille


def _extract_domain(site_web):
    """Extrait le domaine d'une URL de site web."""
    if not site_web:
        return ''
    url = str(site_web).strip()
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    try:
        return urlparse(url).netloc.lower().replace('www.', '')
    except Exception:
        return ''


class LetterGenerator:
    """Genere des lettres Word a partir du template Mirabaud."""

    def __init__(self, output_dir: str = "lettres", template_path: str = None):
        self.output_dir = output_dir
        self.template_path = template_path or TEMPLATE_PATH

    def generate_letter(self, prospect: dict) -> BytesIO:
        """
        Copie le template Mirabaud et personnalise :
        - Logo (P0) : remplace l'image Bonna Sabla par le favicon du prospect
        - Date (P2) : date du jour en francais
        - Salutation (P9) : civilite + nom de famille du dirigeant
        - Intro (P11) : entreprise, anciennete, secteur d'activite
        Retourne un BytesIO contenant le .docx.
        """
        doc = Document(self.template_path)

        entreprise = _clean(prospect.get('nom_entreprise'), 'votre entreprise')
        dirigeant = _clean(prospect.get('dirigeant_enrichi')) or _clean(prospect.get('dirigeant_principal'))
        secteur = _clean(prospect.get('libelle_naf'))
        date_creation = _clean(prospect.get('date_creation'))
        site_web = _clean(prospect.get('site_web'))

        # Anciennete
        annee_creation = ''
        if date_creation and len(date_creation) >= 4:
            try:
                annee_creation = str(int(date_creation[:4]))
            except ValueError:
                pass

        # --- FIX 1 : Logo (P0) ---
        self._replace_logo(doc, site_web)

        # --- FIX 4 : Date (P2) --- remplacer par index, pas par texte
        para_date = doc.paragraphs[2]
        for run in para_date.runs:
            run.text = ''
        if para_date.runs:
            para_date.runs[0].text = f"Paris, le {_format_date_fr()}"

        # --- FIX 2 : Civilite + nom de famille (P9) ---
        civilite, nom_famille = _detect_civilite(dirigeant)
        if nom_famille:
            salutation = f"{civilite} {nom_famille},"
        else:
            salutation = f"{civilite},"
        para_salut = doc.paragraphs[9]
        for run in para_salut.runs:
            run.text = ''
        if para_salut.runs:
            para_salut.runs[0].text = salutation

        # --- FIX 3 : Intro personnalisee (P11) --- remplacer par index
        intro = self._build_intro(entreprise, annee_creation, secteur, dirigeant)
        para_intro = doc.paragraphs[11]
        for run in para_intro.runs:
            run.text = ''
        if para_intro.runs:
            para_intro.runs[0].text = intro

        # Sauvegarder en memoire
        buffer = BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        return buffer

    def _replace_logo(self, doc, site_web):
        """
        Remplace l'image Bonna Sabla (P0, rId12) par le favicon du prospect.
        Si pas de site web, supprime l'image.
        """
        p0 = doc.paragraphs[0]
        ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'
        blips = p0._element.findall(f'.//{{{ns_a}}}blip')

        if not blips:
            return

        blip = blips[0]
        ns_r = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
        embed_attr = f'{{{ns_r}}}embed'
        old_rid = blip.get(embed_attr)

        if not old_rid:
            return

        domain = _extract_domain(site_web)
        if not domain:
            # Pas de site web -> supprimer le dessin entier de P0
            ns_w = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
            drawings = p0._element.findall(f'{{{ns_w}}}r/{{{ns_w}}}drawing')
            for drawing in drawings:
                drawing.getparent().remove(drawing)
            return

        # Telecharger le favicon
        favicon_url = f"https://www.google.com/s2/favicons?domain={domain}&sz=128"
        try:
            r = requests.get(favicon_url, timeout=5)
            if r.status_code != 200 or len(r.content) < 100:
                # Favicon trop petit ou erreur -> supprimer le logo
                self._remove_drawing(p0)
                return
            favicon_bytes = r.content
        except Exception:
            self._remove_drawing(p0)
            return

        # Remplacer le blob de l'image existante
        old_rel = doc.part.rels[old_rid]
        old_rel.target_part._blob = favicon_bytes

    def _remove_drawing(self, paragraph):
        """Supprime tous les elements drawing d'un paragraphe."""
        ns_w = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
        for run_elem in paragraph._element.findall(f'{{{ns_w}}}r'):
            drawings = run_elem.findall(f'{{{ns_w}}}drawing')
            for d in drawings:
                run_elem.remove(d)

    def _build_intro(self, entreprise, annee_creation, secteur, dirigeant):
        """Construit le paragraphe d'introduction personnalise (P11)."""
        parts = []

        if dirigeant and annee_creation:
            parts.append(
                f"Sous votre impulsion et depuis {annee_creation}, "
                f"{entreprise} s\u2019est affirm\u00e9e comme une entreprise "
                f"r\u00e9f\u00e9rente"
            )
        elif annee_creation:
            parts.append(
                f"Depuis {annee_creation}, {entreprise} s\u2019est affirm\u00e9e "
                f"comme une entreprise r\u00e9f\u00e9rente"
            )
        else:
            parts.append(
                f"{entreprise} s\u2019est affirm\u00e9e comme une entreprise "
                f"r\u00e9f\u00e9rente"
            )

        if secteur:
            parts.append(f" dans le secteur {secteur}")

        parts.append(
            ", et ce, dans un environnement en perp\u00e9tuelle \u00e9volution."
        )

        return ''.join(parts)

    def generate_filename(self, prospect: dict) -> str:
        """Genere un nom de fichier normalise pour la lettre."""
        nom = _clean(prospect.get('nom_entreprise'), 'prospect')
        safe_nom = re.sub(r'[^\w\s-]', '', nom)
        safe_nom = re.sub(r'\s+', '_', safe_nom.strip())[:50]
        return f"Lettre_{safe_nom}.docx"

    def generate_all(self, prospects_df) -> list:
        """
        Genere une lettre pour chaque prospect du DataFrame.
        Retourne la liste des chemins de fichiers crees.
        """
        os.makedirs(self.output_dir, exist_ok=True)
        filepaths = []

        for _, row in prospects_df.iterrows():
            prospect = row.to_dict()
            try:
                buf = self.generate_letter(prospect)
                filename = self.generate_filename(prospect)
                filepath = os.path.join(self.output_dir, filename)
                with open(filepath, 'wb') as f:
                    f.write(buf.getvalue())
                filepaths.append(filepath)
            except Exception as e:
                nom = prospect.get('nom_entreprise', '?')
                print(f"  Erreur lettre pour {nom}: {e}")

        return filepaths
