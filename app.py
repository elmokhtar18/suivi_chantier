"""
Point d'entrée de l'application "Suivi de Chantier".

Ce script constitue la page d'accueil (le Tableau de bord principal, exigence
n°1 du cahier des charges) : il affiche en un coup d'œil le montant total des
dépenses, le budget restant, les compteurs (fournisseurs, employés, dépenses)
et les montants liés aux dettes fournisseurs, ainsi qu'un aperçu graphique
des coûts par étape et par catégorie.

Les autres écrans (Dépenses, Étapes, Fournisseurs, Employés, Paiements,
Statistiques, Recherche, Import/Export) sont des pages Streamlit indépendantes
situées dans le dossier `pages/` et apparaissent automatiquement dans le menu
latéral.
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from database import database as db
from utils.helpers import (
    CATEGORICAL,
    CURRENCY,
    SEQUENTIAL_BLUE,
    format_montant,
    inject_custom_css,
    kpi_card,
    kpi_hero,
    section_title,
    style_fig,
)

st.set_page_config(
    page_title="Suivi de Chantier",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

db.init_db()
inject_custom_css()

# ---------------------------------------------------------------------------
# Barre latérale
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 🏗️ Suivi de Chantier")
    st.caption("Pilotage financier et logistique du chantier")
    st.divider()

    st.markdown("### 💰 Budget global du projet")
    budget_actuel = db.get_budget_global()
    nouveau_budget = st.number_input(
        f"Budget total prévu ({CURRENCY})",
        min_value=0.0,
        value=float(budget_actuel),
        step=10000.0,
        format="%.0f",
        help="Laisser à 0 si aucun budget global n'est défini.",
    )
    if nouveau_budget != budget_actuel:
        db.set_budget_global(nouveau_budget)
        st.rerun()

    st.divider()
    st.caption("Utilisez le menu ci-dessus pour naviguer entre les pages : "
               "Dépenses, Étapes, Catégories, Fournisseurs, Dettes, Employés, "
               "Paiements, Statistiques, Recherche et Import/Export.")

# ---------------------------------------------------------------------------
# Indicateurs globaux
# ---------------------------------------------------------------------------
ind = db.get_indicateurs_globaux()

section_title("Tableau de bord principal", "📊")

kpi_hero(
    "Montant total des dépenses",
    format_montant(ind["total_depenses"]),
    sub=f"{ind['nb_depenses']} dépense(s) enregistrée(s)",
)

col1, col2, col3, col4 = st.columns(4)
with col1:
    if ind["budget_restant"] is not None:
        kpi_card("💼", "Budget restant", format_montant(ind["budget_restant"]), "#2e7d32", "#1b5e20")
    else:
        kpi_card("💼", "Budget global", "Non défini", "#757575", "#4a4a4a")
with col2:
    kpi_card("🧾", "Dépenses enregistrées", ind["nb_depenses"], "#5c6bc0", "#3949ab")
with col3:
    kpi_card("🏢", "Fournisseurs", ind["nb_fournisseurs"], "#26a69a", "#00796b")
with col4:
    kpi_card("👷", "Employés", ind["nb_employes"], "#7e57c2", "#5e35b1")

col5, col6, col7 = st.columns(3)
with col5:
    kpi_card("📉", "Dettes fournisseurs", format_montant(ind["total_dettes_fournisseurs"]), "#e53935", "#b71c1c")
with col6:
    kpi_card("✅", "Total payé (fournisseurs)", format_montant(ind["total_paye_fournisseurs"]), "#43a047", "#2e7d32")
with col7:
    kpi_card("⏳", "Restant à payer", format_montant(ind["montant_restant_a_payer"]), "#fb8c00", "#e65100")

st.write("")
st.divider()

# ---------------------------------------------------------------------------
# Aperçu graphique : coût par étape / répartition par catégorie
# ---------------------------------------------------------------------------
depenses = db.get_depenses()
df = pd.DataFrame(depenses)

col_g1, col_g2 = st.columns(2)

with col_g1:
    section_title("Coût par étape", "🏗️")
    couts_etapes = db.get_couts_par_etape()
    df_etapes = pd.DataFrame(couts_etapes)
    if not df_etapes.empty and df_etapes["cout_total"].sum() > 0:
        fig = px.bar(
            df_etapes.sort_values("cout_total", ascending=True),
            x="cout_total", y="nom", orientation="h",
            text="cout_total", color="cout_total",
            color_continuous_scale=SEQUENTIAL_BLUE,
            labels={"cout_total": f"Coût total ({CURRENCY})", "nom": "Étape"},
        )
        fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
        style_fig(fig, coloraxis_showscale=False, height=360, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("Aucune dépense enregistrée pour le moment.")

with col_g2:
    section_title("Répartition par catégorie", "🧱")
    if not df.empty:
        df_cat = df.groupby("categorie_nom", dropna=False)["montant_total"].sum().reset_index()
        df_cat["categorie_nom"] = df_cat["categorie_nom"].replace("", "Non catégorisé").fillna("Non catégorisé")
        fig2 = px.pie(
            df_cat, names="categorie_nom", values="montant_total", hole=0.45,
            color_discrete_sequence=CATEGORICAL,
        )
        fig2.update_traces(textinfo="percent+label")
        style_fig(fig2, height=360, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig2, width="stretch")
    else:
        st.info("Aucune dépense enregistrée pour le moment.")

st.divider()

# ---------------------------------------------------------------------------
# Dernières dépenses enregistrées
# ---------------------------------------------------------------------------
section_title("Dernières dépenses enregistrées", "🕒")
if not df.empty:
    apercu = df.head(10)[[
        "date", "designation", "categorie_nom", "etape_nom", "fournisseur_nom",
        "employe_nom", "montant_total", "statut_paiement",
    ]].rename(columns={
        "date": "Date", "designation": "Désignation", "categorie_nom": "Catégorie",
        "etape_nom": "Étape", "fournisseur_nom": "Fournisseur", "employe_nom": "Employé",
        "montant_total": "Montant", "statut_paiement": "Statut",
    })
    st.dataframe(apercu, width="stretch", hide_index=True)
else:
    st.info("Aucune dépense enregistrée. Rendez-vous sur la page **Dépenses** pour commencer, "
            "ou sur **Import / Export** pour importer un fichier Excel existant.")
