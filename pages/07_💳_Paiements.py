"""
Page "Historique des paiements" : vue unifiée de tous les paiements effectués,
qu'ils concernent un fournisseur (règlement de dette) ou un employé (avance /
paiement complémentaire) — avec date, montant, bénéficiaire, type et
commentaire, filtrables et exportables.
"""

import pandas as pd
import streamlit as st

from database import database as db
from utils.exports import export_csv_bytes, export_excel_bytes, export_pdf_bytes
from utils.helpers import (
    bottom_nav_mobile,
    bouton_partage_pdf,
    format_montant,
    inject_custom_css,
    inject_pwa_head,
    kpi_card,
    section_title,
)

st.set_page_config(page_title="Paiements - Suivi de Chantier", page_icon="💳", layout="wide")
db.init_db()
inject_custom_css()
inject_pwa_head()
section_title("Historique des paiements", "💳")

historique = db.get_historique_paiements()

if not historique:
    st.info("Aucun paiement enregistré pour le moment.")
    bottom_nav_mobile()
    st.stop()

df = pd.DataFrame(historique)

c1, c2, c3 = st.columns(3)
with c1:
    kpi_card("💳", "Nombre de paiements", len(df), "#5c6bc0", "#3949ab")
with c2:
    kpi_card("💰", "Montant total réglé", format_montant(df["montant"].sum()), "#43a047", "#2e7d32")
with c3:
    fournisseur_total = df[df["type"] == "Fournisseur"]["montant"].sum()
    kpi_card("🧱", "Dont fournisseurs", format_montant(fournisseur_total), "#26a69a", "#00796b")

st.divider()

fc1, fc2, fc3 = st.columns(3)
with fc1:
    types_dispo = sorted(df["type"].unique().tolist())
    filtre_type = st.multiselect("Type", types_dispo)
with fc2:
    beneficiaires_dispo = sorted(df["beneficiaire"].unique().tolist())
    filtre_beneficiaire = st.multiselect("Bénéficiaire", beneficiaires_dispo)
with fc3:
    recherche = st.text_input("Recherche (commentaire)")

df_f = df.copy()
if filtre_type:
    df_f = df_f[df_f["type"].isin(filtre_type)]
if filtre_beneficiaire:
    df_f = df_f[df_f["beneficiaire"].isin(filtre_beneficiaire)]
if recherche:
    df_f = df_f[df_f["commentaire"].str.contains(recherche, case=False, na=False)]

df_affiche = df_f[["date", "montant", "beneficiaire", "type", "mode_paiement", "commentaire"]].rename(
    columns={
        "date": "Date", "montant": "Montant", "beneficiaire": "Bénéficiaire",
        "type": "Type", "mode_paiement": "Mode de paiement", "commentaire": "Commentaire",
    }
)
st.caption(f"{len(df_affiche)} paiement(s) — Total : {format_montant(df_f['montant'].sum())}")
st.dataframe(df_affiche, width="stretch", hide_index=True)

exp1, exp2, exp3 = st.columns(3)
with exp1:
    st.download_button("⬇️ Exporter en Excel", export_excel_bytes(df_affiche, "Paiements"),
                        file_name="historique_paiements.xlsx", width="stretch")
with exp2:
    _pdf_paiements = export_pdf_bytes(df_affiche, "Historique des paiements")
    st.download_button("⬇️ Exporter en PDF", _pdf_paiements,
                        file_name="historique_paiements.pdf", width="stretch")
    bouton_partage_pdf(_pdf_paiements, "historique_paiements.pdf", titre="Historique des paiements")
with exp3:
    st.download_button("⬇️ Exporter en CSV", export_csv_bytes(df_affiche),
                        file_name="historique_paiements.csv", width="stretch")

bottom_nav_mobile()
