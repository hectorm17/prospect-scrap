"""
Generation de lettres Word (.docx) personnalisees pour chaque prospect.
Utilise python-docx pour creer des documents professionnels en memoire (BytesIO).
"""

import os
import re
import requests
from io import BytesIO
from datetime import datetime

from docx import Document
from docx.shared import Pt, Cm, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH


MOIS_FR = {
    'January': 'janvier', 'February': 'février', 'March': 'mars',
    'April': 'avril', 'May': 'mai', 'June': 'juin',
    'July': 'juillet', 'August': 'août', 'September': 'septembre',
    'October': 'octobre', 'November': 'novembre', 'December': 'décembre'
}


def _clean(val, default=''):
    """Nettoie une valeur qui peut etre None, NaN, ou valide."""
    if val is None:
        return default
    if isinstance(val, float) and val != val:  # NaN check
        return default
    return str(val) if val else default


class LetterGenerator:
    """Genere des lettres Word personnalisees pour chaque prospect."""

    def __init__(self, output_dir: str = "lettres"):
        self.output_dir = output_dir

    def generate_letter(self, prospect: dict) -> BytesIO:
        """Genere une lettre .docx pour un prospect. Retourne un BytesIO."""
        doc = Document()

        # Marges
        for section in doc.sections:
            section.top_margin = Cm(2)
            section.bottom_margin = Cm(2)
            section.left_margin = Cm(2.5)
            section.right_margin = Cm(2.5)

        # Police par defaut
        style = doc.styles['Normal']
        font = style.font
        font.name = 'Calibri'
        font.size = Pt(11)
        font.color.rgb = RGBColor(0x33, 0x33, 0x33)
        pf = style.paragraph_format
        pf.space_after = Pt(0)
        pf.line_spacing = 1.15

        entreprise = _clean(prospect.get('nom_entreprise'))
        dirigeant = _clean(prospect.get('dirigeant_enrichi')) or _clean(prospect.get('dirigeant_principal'))
        adresse = _clean(prospect.get('adresse_complete'))
        if not adresse:
            parts = [
                _clean(prospect.get('adresse')),
                f"{_clean(prospect.get('code_postal'))} {_clean(prospect.get('ville'))}".strip(),
            ]
            adresse = ', '.join(p for p in parts if p)
        region = _clean(prospect.get('region'))

        # --- Logo prospect (en haut a droite) ---
        logo_url = prospect.get('logo_url', '')
        if logo_url and str(logo_url).startswith('http'):
            try:
                r = requests.get(str(logo_url), timeout=5)
                if r.status_code == 200 and len(r.content) > 100:
                    logo_stream = BytesIO(r.content)
                    paragraph = doc.add_paragraph()
                    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                    run = paragraph.add_run()
                    run.add_picture(logo_stream, width=Inches(1.2))
            except Exception:
                pass

        # --- Date ---
        date_str = datetime.now().strftime("%d %B %Y")
        for en, fr in MOIS_FR.items():
            date_str = date_str.replace(en, fr)

        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        run = p.add_run(f"Paris, le {date_str}")
        run.font.size = Pt(11)
        run.font.color.rgb = RGBColor(80, 80, 80)

        doc.add_paragraph()  # espace

        # --- Destinataire ---
        if dirigeant:
            p = doc.add_paragraph()
            run = p.add_run(dirigeant)
            run.bold = True
            run.font.size = Pt(11)

        p = doc.add_paragraph()
        run = p.add_run(entreprise)
        run.bold = True
        run.font.size = Pt(11)

        if adresse:
            p = doc.add_paragraph()
            run = p.add_run(adresse)
            run.font.size = Pt(11)
            run.font.color.rgb = RGBColor(80, 80, 80)

        doc.add_paragraph()  # espace

        # --- Objet ---
        p = doc.add_paragraph()
        run = p.add_run(f"Objet : Accompagnement strat\u00e9gique \u2013 {entreprise}")
        run.bold = True
        run.font.size = Pt(11)

        doc.add_paragraph()  # espace

        # --- Corps de la lettre ---
        # Calculer l'anciennete
        date_creation = _clean(prospect.get('date_creation'))
        anciennete = ""
        if date_creation:
            try:
                year = int(str(date_creation)[:4])
                anciennete = str(datetime.now().year - year)
            except Exception:
                pass

        # Paragraphe 1 : Salutation
        p = doc.add_paragraph()
        run = p.add_run("Madame, Monsieur,")
        run.font.size = Pt(11)

        doc.add_paragraph()

        # Paragraphe 2 : Introduction + anciennete
        texte1 = (
            f"Nous nous permettons de vous adresser ce courrier car le profil "
            f"de {entreprise} a retenu notre attention."
        )
        if anciennete:
            texte1 += (
                f" En tant qu'acteur \u00e9tabli dans votre secteur d'activit\u00e9, "
                f"avec {anciennete} ann\u00e9es d'existence"
            )
            if region:
                texte1 += f" et une pr\u00e9sence reconnue en {region}"
            texte1 += (
                ", votre entreprise correspond aux crit\u00e8res des "
                "soci\u00e9t\u00e9s que nous accompagnons."
            )
        else:
            texte1 += (
                " Votre entreprise correspond aux crit\u00e8res des "
                "soci\u00e9t\u00e9s que nous accompagnons."
            )

        p = doc.add_paragraph()
        run = p.add_run(texte1)
        run.font.size = Pt(11)

        doc.add_paragraph()

        # Paragraphe 3 : Proposition
        texte2 = (
            f"Notre cabinet intervient aupr\u00e8s de dirigeants de PME et ETI "
            f"dans leurs r\u00e9flexions strat\u00e9giques : op\u00e9rations de "
            f"croissance externe, cession, transmission, ou encore lev\u00e9e de fonds. "
            f"Nous serions ravis de pouvoir \u00e9changer avec vous sur vos projets "
            f"et ambitions pour {entreprise}."
        )

        p = doc.add_paragraph()
        run = p.add_run(texte2)
        run.font.size = Pt(11)

        doc.add_paragraph()

        # Paragraphe 4 : Appel a l'action
        texte3 = (
            "Je me tiens \u00e0 votre disposition pour convenir d'un entretien "
            "\u00e0 votre convenance."
        )

        p = doc.add_paragraph()
        run = p.add_run(texte3)
        run.font.size = Pt(11)

        doc.add_paragraph()

        # Formule de politesse
        texte4 = (
            "Dans l'attente de votre retour, je vous prie d'agr\u00e9er, "
            "Madame, Monsieur, l'expression de mes salutations distingu\u00e9es."
        )

        p = doc.add_paragraph()
        run = p.add_run(texte4)
        run.font.size = Pt(11)

        doc.add_paragraph()
        doc.add_paragraph()

        # Signature placeholder
        p = doc.add_paragraph()
        run = p.add_run("[Votre nom]")
        run.bold = True
        run.font.size = Pt(11)

        p = doc.add_paragraph()
        run = p.add_run("[Votre cabinet]")
        run.italic = True
        run.font.size = Pt(10)
        run.font.color.rgb = RGBColor(100, 100, 100)

        # Sauvegarder en BytesIO
        buffer = BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        return buffer

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
