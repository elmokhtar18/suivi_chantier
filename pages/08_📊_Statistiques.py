"""
Page "Statistiques" : ensemble de graphiques Plotly pour analyser les dépenses
sous différents angles — par mois, par année, par étape, par fournisseur, par
employé, par catégorie, évolution dans le temps et courbe cumulative.
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from database import database as db
from utils.helpers import (
    ACCENT,
    ACCENT_2,
    CATEGORICAL,
    CURRENCY,
    SEQUENTIAL_BLUE,
    bottom_nav_mobile,
    chantier_selector,
    inject_custom_css,
    inject_pwa_head,
    section_title,
    style_fig,
)

st.set_page_config(page_title="Statistiques - Suivi de Chantier", page_icon="📊", layout="wide")
db.init_db()
inject_custom_css()
inject_pwa_head()
chantier_id = chantier_selector()
section_title("Statistiques du chantier", "📊")

depenses = db.get_depenses(chantier_id)
if not depenses:
    st.info("Aucune dépense enregistrée pour le moment : les statistiques apparaîtront ici dès la première dépense.")
    bottom_nav_mobile()
    st.stop()

df = pd.DataFrame(depenses)
df["date"] = pd.to_datetime(df["date"], errors="coerce")
df["mois"] = df["date"].dt.to_period("M").astype(str)
df["annee"] = df["date"].dt.year

# ---------------------------------------------------------------------------
# Dépenses par mois / par année
# ---------------------------------------------------------------------------
col_mois, col_annee = st.columns(2)

with col_mois:
    section_title("Dépenses par mois", "📅")
    df_mois = df.groupby("mois")["montant_total"].sum().reset_index().sort_values("mois")
    fig_mois = px.bar(df_mois, x="mois", y="montant_total", text="montant_total",
                       color="montant_total", color_continuous_scale=SEQUENTIAL_BLUE,
                       labels={"mois": "Mois", "montant_total": f"Total ({CURRENCY})"})
    fig_mois.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
    style_fig(fig_mois, coloraxis_showscale=False, height=380, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig_mois, width="stretch")

with col_annee:
    section_title("Dépenses annuelles", "🗓️")
    df_annee = df.dropna(subset=["annee"]).groupby("annee")["montant_total"].sum().reset_index()
    df_annee["annee"] = df_annee["annee"].astype(int).astype(str)
    fig_annee = px.bar(df_annee.sort_values("annee"), x="annee", y="montant_total", text="montant_total",
                        color="montant_total", color_continuous_scale=SEQUENTIAL_BLUE,
                        labels={"annee": "Année", "montant_total": f"Total ({CURRENCY})"})
    fig_annee.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
    style_fig(fig_annee, coloraxis_showscale=False, height=380, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig_annee, width="stretch")

col1, col2 = st.columns(2)

# ---------------------------------------------------------------------------
# Dépenses par étape
# ---------------------------------------------------------------------------
with col1:
    section_title("Dépenses par étape", "🏗️")
    df_etape = df.groupby("etape_nom", dropna=False)["montant_total"].sum().reset_index()
    df_etape["etape_nom"] = df_etape["etape_nom"].fillna("Non liée")
    fig_etape = px.bar(df_etape.sort_values("montant_total"), x="montant_total", y="etape_nom", orientation="h",
                        text="montant_total", color="montant_total", color_continuous_scale=SEQUENTIAL_BLUE,
                        labels={"etape_nom": "Étape", "montant_total": f"Total ({CURRENCY})"})
    fig_etape.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
    style_fig(fig_etape, coloraxis_showscale=False, height=360, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig_etape, width="stretch")

# ---------------------------------------------------------------------------
# Répartition par catégorie
# ---------------------------------------------------------------------------
with col2:
    section_title("Répartition par catégorie", "🧱")
    df_cat = df.groupby("categorie_nom", dropna=False)["montant_total"].sum().reset_index()
    df_cat["categorie_nom"] = df_cat["categorie_nom"].replace("", "Non catégorisé").fillna("Non catégorisé")
    fig_cat = px.pie(df_cat, names="categorie_nom", values="montant_total", hole=0.45,
                      color_discrete_sequence=CATEGORICAL)
    fig_cat.update_traces(textinfo="percent+label")
    style_fig(fig_cat, height=360, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig_cat, width="stretch")

col3, col4 = st.columns(2)

# ---------------------------------------------------------------------------
# Dépenses par fournisseur
# ---------------------------------------------------------------------------
with col3:
    section_title("Dépenses par fournisseur", "🧱")
    df_four = df[df["fournisseur_nom"].notna()].groupby("fournisseur_nom")["montant_total"].sum().reset_index()
    if df_four.empty:
        st.info("Aucune dépense liée à un fournisseur pour le moment.")
    else:
        fig_four = px.bar(df_four.sort_values("montant_total"), x="montant_total", y="fournisseur_nom", orientation="h",
                           text="montant_total", color="montant_total", color_continuous_scale=SEQUENTIAL_BLUE,
                           labels={"fournisseur_nom": "Fournisseur", "montant_total": f"Total ({CURRENCY})"})
        fig_four.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
        style_fig(fig_four, coloraxis_showscale=False, height=360, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig_four, width="stretch")

# ---------------------------------------------------------------------------
# Dépenses par employé
# ---------------------------------------------------------------------------
with col4:
    section_title("Dépenses par employé", "👷")
    df_emp = df[df["employe_nom"].notna()].groupby("employe_nom")["montant_total"].sum().reset_index()
    if df_emp.empty:
        st.info("Aucune dépense liée à un employé pour le moment.")
    else:
        fig_emp = px.bar(df_emp.sort_values("montant_total"), x="montant_total", y="employe_nom", orientation="h",
                          text="montant_total", color="montant_total", color_continuous_scale=SEQUENTIAL_BLUE,
                          labels={"employe_nom": "Employé", "montant_total": f"Total ({CURRENCY})"})
        fig_emp.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
        style_fig(fig_emp, coloraxis_showscale=False, height=360, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig_emp, width="stretch")

st.divider()

# ---------------------------------------------------------------------------
# Top 10 des dépenses les plus élevées
# ---------------------------------------------------------------------------
section_title("Top 10 des dépenses les plus élevées", "🏆")
df_top10 = df.nlargest(10, "montant_total")[["designation", "montant_total", "date", "categorie_nom"]].copy()
df_top10["etiquette"] = df_top10["designation"].fillna("").str.slice(0, 35) + " (" + df_top10["date"].dt.strftime("%d/%m/%Y") + ")"
fig_top10 = px.bar(
    df_top10.sort_values("montant_total"), x="montant_total", y="etiquette", orientation="h",
    text="montant_total", color="montant_total", color_continuous_scale=SEQUENTIAL_BLUE,
    labels={"montant_total": f"Montant ({CURRENCY})", "etiquette": "Dépense"},
)
fig_top10.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
style_fig(fig_top10, coloraxis_showscale=False, height=420, margin=dict(l=10, r=10, t=10, b=10))
st.plotly_chart(fig_top10, width="stretch")

st.divider()

# ---------------------------------------------------------------------------
# Évolution dans le temps + courbe cumulative
# ---------------------------------------------------------------------------
section_title("Évolution des dépenses dans le temps", "📈")
df_jour = df.dropna(subset=["date"]).groupby("date")["montant_total"].sum().reset_index().sort_values("date")
df_jour["cumul"] = df_jour["montant_total"].cumsum()

fig_evol = px.line(df_jour, x="date", y="montant_total", markers=True,
                    labels={"date": "Date", "montant_total": f"Dépense du jour ({CURRENCY})"})
fig_evol.update_traces(line_color=ACCENT)
style_fig(fig_evol, height=350, margin=dict(l=10, r=10, t=10, b=10))
st.plotly_chart(fig_evol, width="stretch")

section_title("Courbe cumulative des dépenses", "📈")
fig_cumul = px.area(df_jour, x="date", y="cumul",
                     labels={"date": "Date", "cumul": f"Total cumulé ({CURRENCY})"})
fig_cumul.update_traces(line_color=ACCENT_2, fillcolor="rgba(250,204,21,0.20)")
style_fig(fig_cumul, height=350, margin=dict(l=10, r=10, t=10, b=10))
st.plotly_chart(fig_cumul, width="stretch")

bottom_nav_mobile()
