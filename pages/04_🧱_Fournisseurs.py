"""
Page "Fournisseurs" : liste, ajout / modification / suppression, et fiche
complète par fournisseur (total des achats, total payé, dette restante,
historique des achats et des paiements). Permet également d'enregistrer un
paiement effectué à un fournisseur — la dette restante est recalculée
automatiquement (elle est toujours dérivée des dépenses + paiements, jamais
stockée en dur).
"""

from datetime import date

import pandas as pd
import streamlit as st

from database import database as db
from utils.helpers import bottom_nav_mobile, MODES_PAIEMENT, confirm_delete, dette_badge, format_montant, inject_custom_css, inject_pwa_head, section_title

st.set_page_config(page_title="Fournisseurs - Suivi de Chantier", page_icon="🧱", layout="wide")
db.init_db()
inject_custom_css()
inject_pwa_head()
section_title("Gestion des fournisseurs", "🧱")

# ---------------------------------------------------------------------------
# Ajout d'un fournisseur
# ---------------------------------------------------------------------------
with st.expander("➕ Ajouter un nouveau fournisseur", expanded=False):
    with st.form("form_ajout_fournisseur", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            nom = st.text_input("Nom *")
            telephone = st.text_input("Téléphone")
        with c2:
            type_materiaux = st.text_input("Type de matériaux fournis")
            solde_initial = st.number_input("Dette initiale (avant utilisation de l'application)", value=0.0, step=1000.0)
        adresse = st.text_area("Adresse", height=70)
        if st.form_submit_button("💾 Ajouter le fournisseur", width="stretch", type="primary"):
            if not nom.strip():
                st.error("Le nom est obligatoire.")
            elif db.get_fournisseur_by_nom(nom.strip()):
                st.error("Un fournisseur porte déjà ce nom.")
            else:
                db.add_fournisseur(nom.strip(), telephone.strip(), adresse.strip(), type_materiaux.strip(), solde_initial)
                st.success(f"Fournisseur « {nom} » ajouté.")
                st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# Liste des fournisseurs
# ---------------------------------------------------------------------------
section_title("Liste des fournisseurs", "📋")
dettes = db.get_dettes_fournisseurs()

if not dettes:
    st.info("Aucun fournisseur enregistré pour le moment.")
else:
    df = pd.DataFrame(dettes)
    df_affiche = df[["nom", "telephone", "type_materiaux", "total_achats", "total_paye", "dette_restante"]].rename(
        columns={
            "nom": "Nom", "telephone": "Téléphone", "type_materiaux": "Matériaux",
            "total_achats": "Total achats", "total_paye": "Total payé", "dette_restante": "Dette restante",
        }
    )
    st.dataframe(df_affiche, width="stretch", hide_index=True)

st.divider()

# ---------------------------------------------------------------------------
# Fiche fournisseur
# ---------------------------------------------------------------------------
section_title("Fiche fournisseur", "📇")
fournisseurs = db.get_fournisseurs()

if not fournisseurs:
    st.info("Ajoutez un fournisseur pour consulter sa fiche.")
else:
    options = {f["nom"]: f["id"] for f in fournisseurs}
    choix = st.selectbox("Sélectionner un fournisseur", list(options.keys()))
    fid = options[choix]
    f = db.get_fournisseur(fid)
    dette_info = next((d for d in dettes if d["id"] == fid), None)

    st.markdown(
        f"""
        <div class="fiche-header">
            <h2>{f['nom']}</h2>
            <p>📞 {f['telephone'] or '-'} &nbsp;·&nbsp; 📍 {f['adresse'] or '-'} &nbsp;·&nbsp; 🧱 {f['type_materiaux'] or '-'}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total des achats", format_montant(dette_info["total_achats"]))
    m2.metric("Total payé", format_montant(dette_info["total_paye"]))
    m3.metric("Dette restante", format_montant(dette_info["dette_restante"]))
    m4.markdown(dette_badge(dette_info["dette_restante"]), unsafe_allow_html=True)

    tab_achats, tab_paiements, tab_paiement_form, tab_edit = st.tabs(
        ["🧾 Historique des achats", "💳 Historique des paiements", "➕ Enregistrer un paiement", "✏️ Modifier / supprimer"]
    )

    with tab_achats:
        achats = db.get_achats_fournisseur(fid)
        if achats:
            df_achats = pd.DataFrame(achats)[["date", "designation", "categorie_nom", "quantite", "prix_unitaire", "montant_total", "statut_paiement"]]
            df_achats.columns = ["Date", "Désignation", "Catégorie", "Qté", "PU", "Montant", "Statut"]
            st.dataframe(df_achats, width="stretch", hide_index=True)
        else:
            st.info("Aucun achat enregistré pour ce fournisseur.")

    with tab_paiements:
        paiements = db.get_paiements_fournisseur(fid)
        if paiements:
            df_p = pd.DataFrame(paiements)[["date", "montant", "mode_paiement", "commentaire"]]
            df_p.columns = ["Date", "Montant", "Mode de paiement", "Commentaire"]
            st.dataframe(df_p, width="stretch", hide_index=True)
        else:
            st.info("Aucun paiement enregistré pour ce fournisseur.")

    with tab_paiement_form:
        with st.form(f"form_paiement_{fid}", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                p_date = st.date_input("Date du paiement", value=date.today())
                p_montant = st.number_input("Montant payé", min_value=0.0, step=1000.0)
            with c2:
                p_mode = st.selectbox("Mode de paiement", MODES_PAIEMENT)
                p_commentaire = st.text_input("Commentaire")
            if st.form_submit_button("💾 Enregistrer le paiement", width="stretch", type="primary"):
                if p_montant <= 0:
                    st.error("Le montant doit être supérieur à 0.")
                else:
                    db.add_paiement_fournisseur(fid, p_montant, p_date.isoformat(), p_mode, p_commentaire.strip())
                    st.success(f"Paiement de {format_montant(p_montant)} enregistré. Dette recalculée automatiquement.")
                    st.rerun()

    with tab_edit:
        with st.form(f"form_edit_fournisseur_{fid}"):
            c1, c2 = st.columns(2)
            with c1:
                e_nom = st.text_input("Nom", value=f["nom"])
                e_tel = st.text_input("Téléphone", value=f["telephone"] or "")
            with c2:
                e_type = st.text_input("Type de matériaux", value=f["type_materiaux"] or "")
                e_solde = st.number_input("Dette initiale", value=float(f["solde_initial"] or 0), step=1000.0)
            e_adresse = st.text_area("Adresse", value=f["adresse"] or "", height=70)

            if st.form_submit_button("💾 Mettre à jour", width="stretch", type="primary"):
                db.update_fournisseur(fid, e_nom.strip(), e_tel.strip(), e_adresse.strip(), e_type.strip(), e_solde)
                st.success("Fournisseur mis à jour.")
                st.rerun()

        confirm_delete(
            f"le fournisseur « {f['nom']} »", key=f"fournisseur_{fid}",
            on_confirm=lambda: db.delete_fournisseur(fid),
        )

bottom_nav_mobile()
