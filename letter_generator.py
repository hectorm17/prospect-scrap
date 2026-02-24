"""
Generation de lettres Word (.docx) personnalisees a partir du template Mirabaud.
Copie le template et remplace les champs personnalisables (date, dirigeant, entreprise, secteur).
Tout le reste (header, footer, logo Mirabaud, mise en page) est preserve.
"""

import os
import re
from io import BytesIO
from datetime import datetime

from docx import Document


MOIS_FR = {
    'January': 'janvier', 'February': 'février', 'March': 'mars',
    'April': 'avril', 'May': 'mai', 'June': 'juin',
    'July': 'juillet', 'August': 'août', 'September': 'septembre',
    'October': 'octobre', 'November': 'novembre', 'December': 'décembre'
}

# Template path (relative to project root)
TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), 'templates', 'lettre_template.docx')


def _clean(val, default=''):
    """Nettoie une valeur qui peut etre None, NaN, ou valide."""
    if val is None:
        return default
    if isinstance(val, float) and val != val:  # NaN check
        return default
    return str(val) if val else default


def _replace_in_paragraph(paragraph, old_text, new_text):
    """
    Remplace old_text par new_text dans un paragraphe, meme si le texte
    est reparti sur plusieurs runs. Preserve le formatage du premier run.
    Retourne True si un remplacement a eu lieu.
    """
    full_text = paragraph.text
    if old_text not in full_text:
        return False

    # Cas simple : le texte est dans un seul run
    for run in paragraph.runs:
        if old_text in run.text:
            run.text = run.text.replace(old_text, new_text)
            return True

    # Cas complexe : le texte est reparti sur plusieurs runs
    # On fusionne tout dans le premier run et on vide les autres
    combined = full_text.replace(old_text, new_text)
    paragraph.runs[0].text = combined
    for run in paragraph.runs[1:]:
        run.text = ''
    return True


def _set_paragraph_text(paragraph, new_text):
    """
    Remplace tout le texte d'un paragraphe en preservant le formatage du premier run.
    """
    if paragraph.runs:
        paragraph.runs[0].text = new_text
        for run in paragraph.runs[1:]:
            run.text = ''
    else:
        paragraph.add_run(new_text)


def _format_date_fr():
    """Retourne la date du jour en francais : '24 février 2026'"""
    date_str = datetime.now().strftime("%d %B %Y")
    for en, fr in MOIS_FR.items():
        date_str = date_str.replace(en, fr)
    # Supprimer le zero initial (01 -> 1)
    if date_str.startswith('0'):
        date_str = date_str[1:]
    return date_str


class LetterGenerator:
    """Genere des lettres Word a partir du template Mirabaud."""

    def __init__(self, output_dir: str = "lettres", template_path: str = None):
        self.output_dir = output_dir
        self.template_path = template_path or TEMPLATE_PATH

    def generate_letter(self, prospect: dict) -> BytesIO:
        """
        Copie le template Mirabaud et personnalise :
        - Date (P2)
        - Salutation (P9) : "Monsieur Le Calvé," -> dirigeant du prospect
        - Paragraphe intro (P11) : entreprise, anciennete, secteur
        Retourne un BytesIO contenant le .docx.
        """
        doc = Document(self.template_path)

        entreprise = _clean(prospect.get('nom_entreprise'), 'votre entreprise')
        dirigeant = _clean(prospect.get('dirigeant_enrichi')) or _clean(prospect.get('dirigeant_principal'))
        secteur = _clean(prospect.get('libelle_naf'))
        date_creation = _clean(prospect.get('date_creation'))

        # Anciennete
        annee_creation = ''
        if date_creation and len(date_creation) >= 4:
            try:
                annee_creation = str(int(date_creation[:4]))
            except ValueError:
                pass

        # --- 1. Date (P2) ---
        _replace_in_paragraph(doc.paragraphs[2], '18 février 2026', _format_date_fr())

        # --- 2. Salutation (P9) ---
        if dirigeant:
            _set_paragraph_text(doc.paragraphs[9], f"Monsieur {dirigeant},")
        else:
            _set_paragraph_text(doc.paragraphs[9], "Madame, Monsieur,")

        # --- 3. Paragraphe intro personnalise (P11) ---
        intro = self._build_intro(entreprise, annee_creation, secteur, dirigeant)
        _set_paragraph_text(doc.paragraphs[11], intro)

        # Sauvegarder en memoire
        buffer = BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        return buffer

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
