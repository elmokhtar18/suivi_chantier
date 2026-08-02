"""
Page "Import / Export" :
- Import d'un fichier Excel existant avec détection automatique de la ligne
  d'en-tête et des colonnes (date, désignation, catégorie, étape, fournisseur,
  employé, quantité, prix unitaire, montant, statut/mode de paiement,
  observation), aperçu des correspondances avant confirmation, puis import
  sans perte des dépenses (les étapes/fournisseurs/employés référencés sont
  créés automatiquement s'ils n'existent pas encore).
- Export de toutes les données de l'application (Excel multi-feuilles, CSV, PDF).
"""

import io

import pandas as pd
import streamlit as st

from database import database as db
from utils import excel_import
from utils.exports import export_csv_bytes, export_excel_bytes, export_pdf_bytes
from utils.helpers import inject_custom_css, section_title

st.set_page_config(page_title="Import / Export - Suivi de Chantier", page_icon="📥", layout="wide")
db.init_db()
inject_custom_css()
section_title("Importation d'un fichier Excel", "📥")

st.caption(
    "Déposez un fichier Excel de suivi de chantier : l'application détecte automatiquement "
    "la feuille, la ligne d'en-tête et les colonnes, puis vous laisse valider avant d'importer."
)

fichier = st.file_uploader("Fichier Excel (.xlsx)", type=["xlsx", "xls"])

if fichier is not None:
    try:
        feuilles = excel_import.list_sheets(fichier)
    except Exception as exc:  # fichier corrompu / format non supporté
        st.error(f"Impossible de lire ce fichier : {exc}")
        feuilles = []

    if feuilles:
        feuille_choisie = st.selectbox("Feuille à importer", feuilles)

        if st.button("🔍 Analyser la feuille", width="stretch"):
            try:
                raw_df = excel_import.read_raw_sheet(fichier, feuille_choisie)
                header_row = excel_import.detect_header_row(raw_df)
                if header_row is None:
                    st.error("Aucun tableau de dépenses n'a pu être détecté automatiquement dans cette feuille.")
                    st.session_state.pop("import_preview", None)
                else:
                    mapping = excel_import.map_columns(raw_df.iloc[header_row].tolist())
                    df_preview = excel_import.build_dataframe(raw_df, header_row, mapping)
                    st.session_state["import_preview"] = {
                        "header_row": header_row, "mapping": mapping, "df": df_preview,
                    }
            except Exception as exc:
                st.error(f"Erreur lors de l'analyse : {exc}")
                st.session_state.pop("import_preview", None)

    preview = st.session_state.get("import_preview")
    if preview:
        st.success(f"En-tête détecté à la ligne {preview['header_row'] + 1}. Colonnes reconnues :")
        libelles = {
            "date": "Date", "designation": "Désignation", "categorie": "Catégorie", "etape": "Étape",
            "fournisseur": "Fournisseur", "employe": "Employé", "quantite": "Quantité",
            "prix_unitaire": "Prix unitaire", "montant_total": "Montant total",
            "mode_paiement": "Mode de paiement", "statut_paiement": "Statut paiement", "observation": "Observation",
        }
        mapping_affiche = pd.DataFrame(
            [{"Colonne du fichier (index)": idx, "Champ reconnu": libelles.get(champ, champ)}
             for idx, champ in preview["mapping"].items()]
        )
        st.dataframe(mapping_affiche, width="stretch", hide_index=True)

        st.caption(f"Aperçu des données à importer ({len(preview['df'])} ligne(s)) :")
        st.dataframe(preview["df"].head(20), width="stretch", hide_index=True)

        if st.button("✅ Confirmer l'import en base de données", type="primary", width="stretch"):
            resume = excel_import.importer_dataframe(preview["df"])
            st.success(
                f"Import terminé : {resume['nb_importees']} dépense(s) importée(s), "
                f"{resume['nb_ignorees']} ligne(s) ignorée(s) (vides)."
            )
            if resume["etapes_creees"]:
                st.info("Étapes créées automatiquement : " + ", ".join(resume["etapes_creees"]))
            if resume["fournisseurs_crees"]:
                st.info("Fournisseurs créés automatiquement : " + ", ".join(resume["fournisseurs_crees"]))
            if resume["employes_crees"]:
                st.info("Employés créés automatiquement : " + ", ".join(resume["employes_crees"]))
            if resume["categories_creees"]:
                st.info("Catégories créées automatiquement : " + ", ".join(resume["categories_creees"]))
            st.session_state.pop("import_preview", None)
            st.balloons()

st.divider()

# ---------------------------------------------------------------------------
# Export global
# ---------------------------------------------------------------------------
section_title("Exportation des données", "📤")
st.caption("Exportez l'ensemble des données de l'application, table par table, ou en un seul classeur Excel.")

depenses_df = pd.DataFrame(db.get_depenses())
fournisseurs_df = pd.DataFrame(db.get_dettes_fournisseurs())
employes_df = pd.DataFrame(db.get_totaux_employes())
etapes_df = pd.DataFrame(db.get_couts_par_etape())
paiements_df = pd.DataFrame(db.get_historique_paiements())

c1, c2 = st.columns(2)
with c1:
    if st.button("📦 Générer le classeur Excel complet (toutes les données)", width="stretch"):
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            (depenses_df if not depenses_df.empty else pd.DataFrame(columns=["Aucune donnée"])).to_excel(
                writer, index=False, sheet_name="Depenses")
            (fournisseurs_df if not fournisseurs_df.empty else pd.DataFrame(columns=["Aucune donnée"])).to_excel(
                writer, index=False, sheet_name="Fournisseurs")
            (employes_df if not employes_df.empty else pd.DataFrame(columns=["Aucune donnée"])).to_excel(
                writer, index=False, sheet_name="Employes")
            (etapes_df if not etapes_df.empty else pd.DataFrame(columns=["Aucune donnée"])).to_excel(
                writer, index=False, sheet_name="Etapes")
            (paiements_df if not paiements_df.empty else pd.DataFrame(columns=["Aucune donnée"])).to_excel(
                writer, index=False, sheet_name="Paiements")
        st.download_button("⬇️ Télécharger le classeur complet", buffer.getvalue(),
                            file_name="suivi_chantier_export_complet.xlsx", width="stretch")

st.write("")
tabs = st.tabs(["🧾 Dépenses", "🧱 Fournisseurs", "👷 Employés", "🏗️ Étapes", "💳 Paiements"])

_exports = [
    (tabs[0], depenses_df, "depenses", "Dépenses"),
    (tabs[1], fournisseurs_df, "fournisseurs", "Fournisseurs"),
    (tabs[2], employes_df, "employes", "Employés"),
    (tabs[3], etapes_df, "etapes", "Étapes"),
    (tabs[4], paiements_df, "paiements", "Paiements"),
]

for tab, dataframe, fichier_base, titre in _exports:
    with tab:
        if dataframe.empty:
            st.info("Aucune donnée disponible pour cet export.")
        else:
            st.dataframe(dataframe, width="stretch", hide_index=True)
            e1, e2, e3 = st.columns(3)
            with e1:
                st.download_button("⬇️ Excel", export_excel_bytes(dataframe, titre),
                                    file_name=f"{fichier_base}.xlsx", width="stretch", key=f"xlsx_{fichier_base}")
            with e2:
                st.download_button("⬇️ PDF", export_pdf_bytes(dataframe, titre),
                                    file_name=f"{fichier_base}.pdf", width="stretch", key=f"pdf_{fichier_base}")
            with e3:
                st.download_button("⬇️ CSV", export_csv_bytes(dataframe),
                                    file_name=f"{fichier_base}.csv", width="stretch", key=f"csv_{fichier_base}")
