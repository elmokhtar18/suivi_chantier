"""
Page "Étapes du chantier" : ajout / modification / suppression des étapes,
coût total par étape (calculé automatiquement à partir des dépenses liées),
graphique comparatif et pourcentage du budget consommé par étape.
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from database import database as db
from utils.helpers import SEQUENTIAL_BLUE, badge, confirm_delete, format_montant, inject_custom_css, section_title, style_fig

st.set_page_config(page_title="Étapes - Suivi de Chantier", page_icon="🏗️", layout="wide")
db.init_db()
inject_custom_css()
section_title("Gestion des étapes du chantier", "🏗️")

# ---------------------------------------------------------------------------
# Ajout d'une étape
# ---------------------------------------------------------------------------
with st.expander("➕ Ajouter une nouvelle étape", expanded=False):
    with st.form("form_ajout_etape", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            nom = st.text_input("Nom de l'étape *")
        with c2:
            description = st.text_input("Description")
        with c3:
            budget = st.number_input("Budget alloué (0 = non défini)", min_value=0.0, step=10000.0)
        if st.form_submit_button("💾 Ajouter l'étape", width="stretch", type="primary"):
            if not nom.strip():
                st.error("Le nom de l'étape est obligatoire.")
            elif nom.strip() in [e["nom"] for e in db.get_etapes()]:
                st.error("Une étape porte déjà ce nom.")
            else:
                db.add_etape(nom.strip(), description.strip(), budget)
                st.success(f"Étape « {nom} » ajoutée.")
                st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# Vue d'ensemble : coût total + % budget consommé
# ---------------------------------------------------------------------------
section_title("Coût total par étape", "💰")
couts = db.get_couts_par_etape()

if not couts:
    st.info("Aucune étape définie pour le moment.")
else:
    for c in couts:
        with st.container(border=True):
            col_a, col_b, col_c, col_d = st.columns([2, 2.2, 1.3, 2.5])
            with col_a:
                st.markdown(f"### {c['nom']}")
                if c["description"]:
                    st.caption(c["description"])
            with col_b:
                st.metric("Coût total", format_montant(c["cout_total"]))
            with col_c:
                st.metric("Nb dépenses", c["nb_depenses"])
            with col_d:
                if c["pct_budget"] is None:
                    st.markdown(badge("Budget non défini", "gray"), unsafe_allow_html=True)
                else:
                    couleur = "green" if c["pct_budget"] < 80 else ("orange" if c["pct_budget"] <= 100 else "red")
                    st.markdown(badge(f"{c['pct_budget']}% du budget consommé", couleur), unsafe_allow_html=True)
                    st.progress(min(int(c["pct_budget"]), 100) / 100)

    st.divider()
    section_title("Graphique comparatif", "📊")
    df_couts = pd.DataFrame(couts)
    fig = px.bar(
        df_couts.sort_values("cout_total", ascending=True),
        x="cout_total", y="nom", orientation="h", text="cout_total",
        color="cout_total", color_continuous_scale=SEQUENTIAL_BLUE,
        labels={"cout_total": "Coût total", "nom": "Étape"},
    )
    fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
    style_fig(fig, coloraxis_showscale=False, height=420, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, width="stretch")

st.divider()

# ---------------------------------------------------------------------------
# Modifier / supprimer une étape
# ---------------------------------------------------------------------------
section_title("Modifier ou supprimer une étape", "✏️")
etapes = db.get_etapes()
if etapes:
    options = {f"{e['nom']}": e["id"] for e in etapes}
    choix = st.selectbox("Sélectionner une étape", ["-"] + list(options.keys()))
    if choix != "-":
        etape = db.get_etape(options[choix])
        with st.form("form_edit_etape"):
            c1, c2, c3 = st.columns(3)
            with c1:
                e_nom = st.text_input("Nom", value=etape["nom"])
            with c2:
                e_description = st.text_input("Description", value=etape["description"] or "")
            with c3:
                e_budget = st.number_input("Budget alloué", min_value=0.0, value=float(etape["budget_alloue"] or 0), step=10000.0)
            e_ordre = st.number_input("Ordre d'affichage", min_value=0, value=int(etape["ordre"] or 0))

            if st.form_submit_button("💾 Mettre à jour", width="stretch", type="primary"):
                db.update_etape(etape["id"], e_nom.strip(), e_description.strip(), e_budget, e_ordre)
                st.success("Étape mise à jour.")
                st.rerun()

        confirm_delete(
            f"l'étape « {etape['nom']} »", key=f"etape_{etape['id']}",
            on_confirm=lambda: db.delete_etape(etape["id"]),
        )
        st.caption("Les dépenses liées ne sont pas supprimées : elles n'ont simplement plus d'étape associée.")
else:
    st.info("Aucune étape à modifier.")
