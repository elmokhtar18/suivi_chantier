"""
Page "Dettes Fournisseurs" : vue consolidée des dettes envers les fournisseurs
— total des dettes, fournisseurs les plus endettés, détail par fournisseur et
graphique. Toutes les valeurs sont recalculées en direct depuis les dépenses
et les paiements enregistrés (aucune valeur stockée en dur).
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from database import database as db
from utils.helpers import (
    CATEGORICAL,
    STATUS_CRITICAL,
    format_montant,
    inject_custom_css,
    kpi_card,
    kpi_hero,
    section_title,
    style_fig,
)

DEBT_SEQUENTIAL = ["#5a1f1f", "#8f2f2f", STATUS_CRITICAL]

st.set_page_config(page_title="Dettes Fournisseurs - Suivi de Chantier", page_icon="📉", layout="wide")
db.init_db()
inject_custom_css()
section_title("Dettes Fournisseurs", "📉")

dettes = db.get_dettes_fournisseurs()

if not dettes:
    st.info("Aucun fournisseur enregistré pour le moment.")
    st.stop()

df = pd.DataFrame(dettes)
total_dettes = df["dette_restante"].sum()
nb_endettes = int((df["dette_restante"] > 0).sum())

kpi_hero("Total des dettes fournisseurs", format_montant(total_dettes), sub=f"{nb_endettes} fournisseur(s) endetté(s)")

c1, c2, c3 = st.columns(3)
with c1:
    kpi_card("🧱", "Fournisseurs suivis", len(df), "#5c6bc0", "#3949ab")
with c2:
    kpi_card("🛒", "Total des achats", format_montant(df["total_achats"].sum()), "#26a69a", "#00796b")
with c3:
    kpi_card("✅", "Total payé", format_montant(df["total_paye"].sum()), "#43a047", "#2e7d32")

st.divider()

section_title("Fournisseurs les plus endettés", "🚨")
df_endettes = df[df["dette_restante"] > 0].sort_values("dette_restante", ascending=False)
if df_endettes.empty:
    st.success("Aucun fournisseur endetté actuellement. 🎉")
else:
    top = df_endettes.head(10)
    fig = px.bar(
        top.sort_values("dette_restante"), x="dette_restante", y="nom", orientation="h",
        text="dette_restante", color="dette_restante", color_continuous_scale=DEBT_SEQUENTIAL,
        labels={"dette_restante": "Dette restante", "nom": "Fournisseur"},
    )
    fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
    style_fig(fig, coloraxis_showscale=False, height=380, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, width="stretch")

st.divider()

section_title("Dettes par fournisseur (détail)", "📋")
df_detail = df[["nom", "telephone", "total_achats", "total_paye", "dette_restante"]].sort_values(
    "dette_restante", ascending=False
).rename(columns={
    "nom": "Fournisseur", "telephone": "Téléphone", "total_achats": "Total achats",
    "total_paye": "Total payé", "dette_restante": "Dette restante",
})
st.dataframe(df_detail, width="stretch", hide_index=True)

section_title("Répartition des dettes", "🥧")
if not df_endettes.empty:
    fig2 = px.pie(df_endettes, names="nom", values="dette_restante", hole=0.45,
                  color_discrete_sequence=CATEGORICAL)
    fig2.update_traces(textinfo="percent+label")
    style_fig(fig2, height=380, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig2, width="stretch")
else:
    st.info("Pas de dette à répartir pour le moment.")
