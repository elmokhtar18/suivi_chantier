"""
Point d'entrée de l'application "Suivi de Chantier".

Ce script constitue la page d'accueil : un tableau de bord **interactif**
(drill-down) qui affiche en un coup d'œil le montant total des dépenses, le
budget restant, les dépenses du mois/de l'année, la répartition par catégorie
et par employé — et permet de cliquer sur n'importe quel indicateur, ligne de
catégorie, d'employé ou de mois pour ouvrir une vue détaillée des dépenses
correspondantes, directement sous le tableau de bord.

Les autres écrans (Dépenses, Étapes, Catégories, Fournisseurs, Dettes,
Employés, Paiements, Statistiques, Recherche, Import/Export) sont des pages
Streamlit indépendantes situées dans le dossier `pages/` et apparaissent
automatiquement dans le menu latéral.
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from database import database as db
from utils.helpers import (
    CATEGORICAL,
    CURRENCY,
    SEQUENTIAL_BLUE,
    STATUS_CRITICAL,
    STATUS_GOOD,
    STATUS_WARNING,
    bottom_nav_mobile,
    bouton_voir_detail,
    chantier_selector,
    filtrer_depenses_dashboard,
    format_montant,
    inject_custom_css,
    inject_pwa_head,
    kpi_card,
    kpi_hero,
    ouvrir_dans_page_depenses,
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
inject_pwa_head()
chantier_id = chantier_selector()

# ---------------------------------------------------------------------------
# Barre latérale
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 🏗️ Suivi de Chantier")
    st.caption("Pilotage financier et logistique du chantier")
    st.divider()

    st.markdown("### 💰 Budget global du projet")
    budget_actuel = db.get_budget_global(chantier_id)
    nouveau_budget = st.number_input(
        f"Budget total prévu ({CURRENCY})",
        min_value=0.0,
        value=float(budget_actuel),
        step=10000.0,
        format="%.0f",
        help="Laisser à 0 si aucun budget global n'est défini.",
    )
    if nouveau_budget != budget_actuel:
        db.set_budget_global(chantier_id, nouveau_budget)
        st.rerun()

    st.divider()
    st.caption("Utilisez le menu ci-dessus pour naviguer entre les pages : "
               "Dépenses, Étapes, Catégories, Fournisseurs, Dettes, Employés, "
               "Paiements, Statistiques, Recherche et Import/Export.")

# ---------------------------------------------------------------------------
# Vue d'ensemble : tous les chantiers confondus
# ---------------------------------------------------------------------------
ind_globaux = db.get_indicateurs_tous_chantiers()

section_title("Vue d'ensemble — tous les chantiers", "🌍")
g1, g2, g3, g4 = st.columns(4)
with g1:
    kpi_card("💰", "Total dépenses (tous chantiers)", format_montant(ind_globaux["total_depenses"]))
with g2:
    kpi_card("📉", "Dettes fournisseurs", format_montant(ind_globaux["total_dettes_fournisseurs"]),
              STATUS_CRITICAL, STATUS_CRITICAL)
with g3:
    kpi_card("✅", "Avancé / payé aux employés", format_montant(ind_globaux["total_regle_employes"]),
              STATUS_GOOD, STATUS_GOOD)
with g4:
    kpi_card("⏳", "Reste à payer aux employés", format_montant(ind_globaux["reste_a_payer_employes"]),
              STATUS_WARNING, STATUS_WARNING)

st.divider()

# ---------------------------------------------------------------------------
# Indicateurs du chantier actif
# ---------------------------------------------------------------------------
ind = db.get_indicateurs_globaux(chantier_id)
depenses = db.get_depenses(chantier_id)
df = pd.DataFrame(depenses)
nom_chantier_actif = db.get_chantier(chantier_id)["nom"]

section_title(f"Tableau de bord — {nom_chantier_actif}", "📊")
st.caption("Cliquez sur « 🔍 Voir le détail », ou sur une ligne des tableaux "
           "ci-dessous, pour explorer les dépenses correspondantes.")

kpi_hero(
    "Montant total des dépenses",
    format_montant(ind["total_depenses"]),
    sub=f"{ind['nb_depenses']} dépense(s) enregistrée(s)",
)
bouton_voir_detail("🔍 Voir toutes les dépenses", "hero_total", type="total")

st.write("")
col_mois, col_annee, col_nb = st.columns(3)
with col_mois:
    kpi_card("📅", "Dépenses du mois", format_montant(ind["depenses_mois_courant"]))
    bouton_voir_detail("🔍 Voir le détail", "mois_courant", type="mois", value=ind["mois_courant"])
with col_annee:
    kpi_card("🗓️", "Dépenses de l'année", format_montant(ind["depenses_annee_courante"]))
    bouton_voir_detail("🔍 Voir le détail", "annee_courante", type="annee", value=ind["annee_courante"])
with col_nb:
    kpi_card("🧾", "Dépenses enregistrées", ind["nb_depenses"])
    bouton_voir_detail("🔍 Voir le détail", "nb_total", type="total")

st.write("")
col1, col2, col3, col4 = st.columns(4)
with col1:
    if ind["budget_restant"] is not None:
        kpi_card("💼", "Budget restant", format_montant(ind["budget_restant"]))
    else:
        kpi_card("💼", "Budget global", "Non défini")
with col2:
    kpi_card("🏢", "Fournisseurs", ind["nb_fournisseurs"])
with col3:
    kpi_card("👷", "Employés", ind["nb_employes"])
with col4:
    kpi_card("📉", "Dettes fournisseurs", format_montant(ind["total_dettes_fournisseurs"]), STATUS_CRITICAL, STATUS_CRITICAL)

col5, col6 = st.columns(2)
with col5:
    kpi_card("✅", "Total payé (fournisseurs)", format_montant(ind["total_paye_fournisseurs"]), STATUS_GOOD, STATUS_GOOD)
with col6:
    kpi_card("⏳", "Restant à payer", format_montant(ind["montant_restant_a_payer"]), STATUS_WARNING, STATUS_WARNING)

st.write("")
st.divider()

# ---------------------------------------------------------------------------
# Aperçu graphique : coût par étape / répartition par catégorie
# ---------------------------------------------------------------------------
col_g1, col_g2 = st.columns(2)

with col_g1:
    section_title("Coût par étape", "🏗️")
    couts_etapes = db.get_couts_par_etape(chantier_id)
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
        df_cat_chart = df.groupby("categorie_nom", dropna=False)["montant_total"].sum().reset_index()
        df_cat_chart["categorie_nom"] = df_cat_chart["categorie_nom"].replace("", "Non catégorisé").fillna("Non catégorisé")
        fig2 = px.pie(
            df_cat_chart, names="categorie_nom", values="montant_total", hole=0.45,
            color_discrete_sequence=CATEGORICAL,
        )
        fig2.update_traces(textinfo="percent+label")
        style_fig(fig2, height=360, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig2, width="stretch")
    else:
        st.info("Aucune dépense enregistrée pour le moment.")

st.divider()

# ---------------------------------------------------------------------------
# Répartition cliquable (drill-down) : catégorie / employé / mois
# ---------------------------------------------------------------------------
section_title("Explorer par catégorie, employé ou mois", "🔍")
st.caption("Cliquez sur une ligne d'un des tableaux ci-dessous pour voir le détail des dépenses correspondantes.")

# Clés des 3 tableaux cliquables : réinitialisées à la fermeture de la vue détail
# (sinon la sélection reste visuellement active et rouvrirait le détail en boucle).
CLES_TABLEAUX_DRILLDOWN = ["tbl_dashboard_categories", "tbl_dashboard_employes", "tbl_dashboard_mois"]


def _appliquer_selection(evenement, df_aff, colonne, type_filtre):
    """Pose `dashboard_filtre` à partir d'une ligne sélectionnée dans un tableau
    cliquable, uniquement si la valeur change réellement (évite de redéclencher
    un rerun en boucle tant que la ligne reste sélectionnée à l'écran)."""
    if not evenement.selection.rows:
        return
    valeur = df_aff.iloc[evenement.selection.rows[0]][colonne]
    nouveau_filtre = {"type": type_filtre, "value": valeur}
    if st.session_state.get("dashboard_filtre") != nouveau_filtre:
        st.session_state["dashboard_filtre"] = nouveau_filtre
        st.rerun()


col_cat, col_emp, col_mois_tbl = st.columns(3)

with col_cat:
    st.markdown("**Par catégorie**")
    totaux_cat = db.get_totaux_categories(chantier_id)
    df_cat = pd.DataFrame([t for t in totaux_cat if t["nb_depenses"] > 0])
    if df_cat.empty:
        st.caption("Aucune donnée.")
    else:
        df_cat_aff = df_cat[["nom", "montant_total", "nb_depenses"]].rename(
            columns={"nom": "Catégorie", "montant_total": "Montant", "nb_depenses": "Nb"}
        ).sort_values("Montant", ascending=False)
        evenement = st.dataframe(
            df_cat_aff, hide_index=True, width="stretch", height=210,
            on_select="rerun", selection_mode="single-row", key="tbl_dashboard_categories",
        )
        _appliquer_selection(evenement, df_cat_aff, "Catégorie", "categorie")

with col_emp:
    st.markdown("**Par employé**")
    totaux_emp = db.get_totaux_employes(chantier_id)
    df_emp = pd.DataFrame(totaux_emp)
    if df_emp.empty:
        st.caption("Aucune donnée.")
    else:
        df_emp_montants = df.groupby("employe_nom")["montant_total"].sum().reset_index() if not df.empty else pd.DataFrame(columns=["employe_nom", "montant_total"])
        df_emp_aff = df_emp[["nom"]].merge(
            df_emp_montants.rename(columns={"employe_nom": "nom", "montant_total": "Montant"}), on="nom", how="left"
        ).fillna({"Montant": 0})
        df_emp_aff = df_emp_aff.rename(columns={"nom": "Employé"}).sort_values("Montant", ascending=False)
        df_emp_aff = df_emp_aff[df_emp_aff["Montant"] > 0]
        if df_emp_aff.empty:
            st.caption("Aucune donnée.")
        else:
            evenement_emp = st.dataframe(
                df_emp_aff, hide_index=True, width="stretch", height=210,
                on_select="rerun", selection_mode="single-row", key="tbl_dashboard_employes",
            )
            _appliquer_selection(evenement_emp, df_emp_aff, "Employé", "employe")

with col_mois_tbl:
    st.markdown("**Par mois (12 derniers)**")
    if df.empty:
        st.caption("Aucune donnée.")
    else:
        df_mois = df.copy()
        df_mois["mois"] = df_mois["date"].str[:7]
        df_mois_aff = df_mois.groupby("mois")["montant_total"].sum().reset_index()
        df_mois_aff = df_mois_aff.rename(columns={"mois": "Mois", "montant_total": "Montant"})
        df_mois_aff = df_mois_aff.sort_values("Mois", ascending=False).head(12)
        evenement_mois = st.dataframe(
            df_mois_aff, hide_index=True, width="stretch", height=210,
            on_select="rerun", selection_mode="single-row", key="tbl_dashboard_mois",
        )
        _appliquer_selection(evenement_mois, df_mois_aff, "Mois", "mois")

# ---------------------------------------------------------------------------
# Vue détail (drill-down)
# ---------------------------------------------------------------------------
filtre_actif = st.session_state.get("dashboard_filtre")
if filtre_actif:
    st.divider()
    df_detail, libelle = filtrer_depenses_dashboard(df, filtre_actif)

    c_titre, c_fermer, c_ouvrir = st.columns([4, 1, 1.6])
    with c_titre:
        section_title(f"Détail : {libelle}", "🔎")
    with c_fermer:
        if st.button("↩️ Fermer", width="stretch"):
            st.session_state.pop("dashboard_filtre", None)
            # Désélectionne aussi les tableaux cliquables : sans ça, la ligne resterait
            # sélectionnée à l'écran et rouvrirait immédiatement le même détail.
            for cle in CLES_TABLEAUX_DRILLDOWN:
                st.session_state.pop(cle, None)
            st.rerun()
    with c_ouvrir:
        if st.button("↗️ Page Dépenses", width="stretch"):
            ouvrir_dans_page_depenses(filtre_actif)

    if df_detail.empty:
        st.info("Aucune dépense ne correspond à ce filtre.")
    else:
        m1, m2, m3 = st.columns(3)
        m1.metric("Total", format_montant(df_detail["montant_total"].sum()))
        m2.metric("Nombre de dépenses", len(df_detail))
        m3.metric("Montant moyen", format_montant(df_detail["montant_total"].mean()))

        df_detail_aff = df_detail[[
            "date", "designation", "categorie_nom", "etape_nom", "fournisseur_nom",
            "employe_nom", "montant_total", "statut_paiement",
        ]].rename(columns={
            "date": "Date", "designation": "Désignation", "categorie_nom": "Catégorie",
            "etape_nom": "Étape", "fournisseur_nom": "Fournisseur", "employe_nom": "Employé",
            "montant_total": "Montant", "statut_paiement": "Statut",
        })
        st.dataframe(df_detail_aff, width="stretch", hide_index=True)

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

bottom_nav_mobile()
