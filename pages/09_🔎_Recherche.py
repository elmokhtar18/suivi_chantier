"""
Page "Recherche globale" : une seule barre de recherche pour retrouver
rapidement un fournisseur, un employé, une dépense (y compris par
désignation/observation, qui tient lieu de numéro de facture), ou une étape.
"""

import pandas as pd
import streamlit as st

from database import database as db
from utils.helpers import bottom_nav_mobile, format_montant, inject_custom_css, inject_pwa_head, section_title

st.set_page_config(page_title="Recherche - Suivi de Chantier", page_icon="🔎", layout="wide")
db.init_db()
inject_custom_css()
inject_pwa_head()
section_title("Recherche globale", "🔎")

requete = st.text_input("🔎 Rechercher un fournisseur, un employé, une dépense, une facture, une étape...")

if not requete or len(requete.strip()) < 2:
    st.info("Saisissez au moins 2 caractères pour lancer la recherche.")
    bottom_nav_mobile()
    st.stop()

q = requete.strip().lower()

# ---------------------------------------------------------------------------
# Étapes
# ---------------------------------------------------------------------------
etapes = [e for e in db.get_etapes() if q in (e["nom"] or "").lower() or q in (e["description"] or "").lower()]
section_title(f"Étapes ({len(etapes)})", "🏗️")
if etapes:
    df_e = pd.DataFrame(etapes)[["nom", "description", "budget_alloue"]]
    df_e.columns = ["Nom", "Description", "Budget alloué"]
    st.dataframe(df_e, width="stretch", hide_index=True)
else:
    st.caption("Aucun résultat.")

# ---------------------------------------------------------------------------
# Fournisseurs
# ---------------------------------------------------------------------------
fournisseurs = [
    f for f in db.get_fournisseurs()
    if q in (f["nom"] or "").lower() or q in (f["telephone"] or "").lower()
    or q in (f["type_materiaux"] or "").lower() or q in (f["adresse"] or "").lower()
]
section_title(f"Fournisseurs ({len(fournisseurs)})", "🧱")
if fournisseurs:
    df_f = pd.DataFrame(fournisseurs)[["nom", "telephone", "adresse", "type_materiaux"]]
    df_f.columns = ["Nom", "Téléphone", "Adresse", "Matériaux"]
    st.dataframe(df_f, width="stretch", hide_index=True)
else:
    st.caption("Aucun résultat.")

# ---------------------------------------------------------------------------
# Employés
# ---------------------------------------------------------------------------
employes = [
    e for e in db.get_employes()
    if q in (e["nom"] or "").lower() or q in (e["fonction"] or "").lower() or q in (e["telephone"] or "").lower()
]
section_title(f"Employés ({len(employes)})", "👷")
if employes:
    df_emp = pd.DataFrame(employes)[["nom", "fonction", "telephone"]]
    df_emp.columns = ["Nom", "Fonction", "Téléphone"]
    st.dataframe(df_emp, width="stretch", hide_index=True)
else:
    st.caption("Aucun résultat.")

# ---------------------------------------------------------------------------
# Dépenses (désignation, catégorie, observation = tient lieu de recherche de facture)
# ---------------------------------------------------------------------------
toutes_depenses = db.get_depenses()
depenses = [
    d for d in toutes_depenses
    if q in (d["designation"] or "").lower() or q in (d["observation"] or "").lower()
    or q in (d["categorie_nom"] or "").lower()
    or q in (d["fournisseur_nom"] or "").lower() or q in (d["employe_nom"] or "").lower()
]
section_title(f"Dépenses ({len(depenses)})", "🧾")
if depenses:
    df_d = pd.DataFrame(depenses)[[
        "date", "designation", "categorie_nom", "etape_nom", "fournisseur_nom", "employe_nom", "montant_total",
    ]]
    df_d.columns = ["Date", "Désignation", "Catégorie", "Étape", "Fournisseur", "Employé", "Montant"]
    st.dataframe(df_d, width="stretch", hide_index=True)
    st.caption(f"Montant total des résultats : {format_montant(df_d['Montant'].sum())}")
else:
    st.caption("Aucun résultat.")

bottom_nav_mobile()
