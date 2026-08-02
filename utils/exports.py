"""
Fonctions d'export génériques (Excel, CSV, PDF) utilisées par toutes les pages
pour permettre à l'utilisateur de télécharger un tableau (dépenses, fournisseurs,
employés, historique de paiements, ...).

Chaque fonction prend un DataFrame pandas déjà prêt à l'affichage et retourne
des `bytes`, directement utilisables avec `st.download_button`.
"""

import io

import pandas as pd
from fpdf import FPDF
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter


def export_excel_bytes(df: pd.DataFrame, titre_feuille="Export") -> bytes:
    """Exporte un DataFrame vers un classeur Excel mis en forme (en-tête coloré, colonnes ajustées)."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=titre_feuille[:31] or "Export")
        ws = writer.sheets[titre_feuille[:31] or "Export"]

        header_fill = PatternFill(start_color="1E3C72", end_color="1E3C72", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True)
        for col_idx, col_name in enumerate(df.columns, start=1):
            cell = ws.cell(row=1, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            max_len = max([len(str(col_name))] + [len(str(v)) for v in df[col_name].astype(str).tolist()[:200]])
            ws.column_dimensions[get_column_letter(col_idx)].width = min(max(max_len + 2, 10), 45)

    return buffer.getvalue()


def export_csv_bytes(df: pd.DataFrame) -> bytes:
    """Exporte un DataFrame en CSV (encodage UTF-8 avec BOM pour une ouverture correcte dans Excel)."""
    return df.to_csv(index=False).encode("utf-8-sig")


class _PDFRapport(FPDF):
    def __init__(self, titre, orientation="L"):
        super().__init__(orientation=orientation, unit="mm", format="A4")
        self.titre = titre
        self.set_auto_page_break(auto=True, margin=12)

    def header(self):
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(30, 60, 114)
        self.cell(0, 10, self.titre, ln=1, align="C")
        self.set_draw_color(30, 60, 114)
        self.set_line_width(0.5)
        self.line(10, self.get_y(), self.w - 10, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, f"Page {self.page_no()}", align="C")


def export_pdf_bytes(df: pd.DataFrame, titre="Export") -> bytes:
    """Exporte un DataFrame en PDF sous forme de tableau (paysage, en-tête répété à chaque page)."""
    pdf = _PDFRapport(titre)
    pdf.add_page()

    colonnes = [str(c) for c in df.columns]
    nb_col = max(len(colonnes), 1)
    largeur_page = pdf.w - 20
    largeur_col = largeur_page / nb_col
    hauteur_ligne = 7

    def draw_header():
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_fill_color(30, 60, 114)
        pdf.set_text_color(255, 255, 255)
        for col in colonnes:
            pdf.cell(largeur_col, hauteur_ligne, str(col)[:40], border=1, align="C", fill=True)
        pdf.ln(hauteur_ligne)

    draw_header()
    pdf.set_font("Helvetica", "", 7.5)
    pdf.set_text_color(30, 30, 30)

    for i, row in enumerate(df.itertuples(index=False)):
        if pdf.get_y() + hauteur_ligne > pdf.h - 15:
            pdf.add_page()
            draw_header()
            pdf.set_font("Helvetica", "", 7.5)
            pdf.set_text_color(30, 30, 30)
        pdf.set_fill_color(245, 247, 250) if i % 2 == 0 else pdf.set_fill_color(255, 255, 255)
        for val in row:
            texte = "" if val is None else str(val)
            pdf.cell(largeur_col, hauteur_ligne, texte[:40], border=1, align="C", fill=True)
        pdf.ln(hauteur_ligne)

    return bytes(pdf.output())
