"""
Page "Catégories" : ajout / modification / suppression des catégories de
dépenses, avec le nombre de dépenses liées et le montant total par catégorie.

`depenses.categorie_id` est une clé étrangère vers `categories` (voir
`database/database.py`) : renommer une catégorie ici met donc à jour
instantanément toutes les dépenses déjà liées, sans risque de doublon ni de
désynchronisation.
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from database import database as db
from utils.helpers import bottom_nav_mobile, CATEGORICAL, confirm_delete, inject_custom_css, inject_pwa_head, section_title, style_fig

st.set_page_config(page_title="Catégories - Suivi de Chantier", page_icon="🏷️", layout="wide")
db.init_db()
inject_custom_css()
inject_pwa_head()
section_title("Gestion des catégories", "🏷️")

# ---------------------------------------------------------------------------
# Ajout d'une catégorie
# ---------------------------------------------------------------------------
with st.expander("➕ Ajouter une nouvelle catégorie", expanded=False):
    with st.form("form_ajout_categorie", clear_on_submit=True):
        nom = st.text_input("Nom de la catégorie *")
        if st.form_submit_button("💾 Ajouter la catégorie", width="stretch", type="primary"):
            if not nom.strip():
                st.error("Le nom de la catégorie est obligatoire.")
            elif db.get_categorie_by_nom(nom.strip()):
                st.error("Une catégorie porte déjà ce nom.")
            else:
                db.add_categorie(nom.strip())
                st.success(f"Catégorie « {nom} » ajoutée.")
                st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# Vue d'ensemble : nombre de dépenses + montant total par catégorie
# ---------------------------------------------------------------------------
section_title("Dépenses par catégorie", "💰")
totaux = db.get_totaux_categories()

if not totaux:
    st.info("Aucune catégorie définie pour le moment.")
else:
    df_totaux = pd.DataFrame(totaux)
    df_affiche = df_totaux[["nom", "nb_depenses", "montant_total"]].rename(
        columns={"nom": "Catégorie", "nb_depenses": "Nb dépenses", "montant_total": "Montant total"}
    )
    st.dataframe(df_affiche, width="stretch", hide_index=True)

    df_avec_depenses = df_totaux[df_totaux["montant_total"] > 0]
    if not df_avec_depenses.empty:
        fig = px.pie(
            df_avec_depenses, names="nom", values="montant_total", hole=0.45,
            color_discrete_sequence=CATEGORICAL,
        )
        fig.update_traces(textinfo="percent+label")
        style_fig(fig, height=380, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, width="stretch")

st.divider()

# ---------------------------------------------------------------------------
# Modifier / supprimer une catégorie
# ---------------------------------------------------------------------------
section_title("Modifier ou supprimer une catégorie", "✏️")
categories = db.get_categories()
if categories:
    options = {c["nom"]: c["id"] for c in categories}
    choix = st.selectbox("Sélectionner une catégorie", ["-"] + list(options.keys()))
    if choix != "-":
        categorie_id = options[choix]
        with st.form("form_edit_categorie"):
            e_nom = st.text_input("Nom", value=choix)
            if st.form_submit_button("💾 Mettre à jour", width="stretch", type="primary"):
                if not e_nom.strip():
                    st.error("Le nom ne peut pas être vide.")
                else:
                    db.update_categorie(categorie_id, e_nom.strip())
                    st.success("Catégorie mise à jour — toutes les dépenses liées sont à jour automatiquement.")
                    st.rerun()

        confirm_delete(
            f"la catégorie « {choix} »", key=f"categorie_{categorie_id}",
            on_confirm=lambda: db.delete_categorie(categorie_id),
        )
        st.caption("Les dépenses liées ne sont pas supprimées : elles n'ont simplement plus de catégorie associée.")
else:
    st.info("Aucune catégorie à modifier.")

bottom_nav_mobile()
