"""
Page "Employés" : liste, ajout / modification / suppression, et fiche
complète par employé (total dû, total avancé, total payé, reste à payer),
avec enregistrement des avances et des paiements complémentaires.

Le "Total dû" correspond au montant convenu pour la mission de l'employé
(modifiable à tout moment). Chaque dépense de catégorie "Employé" liée à cet
employé crée automatiquement une avance (voir `database.add_depense`) ; des
avances ou paiements complémentaires peuvent aussi être ajoutés manuellement
ici (ex : avances versées avant le début des travaux).
"""

from datetime import date

import pandas as pd
import streamlit as st

from database import database as db
from utils.helpers import bottom_nav_mobile, confirm_delete, format_montant, inject_custom_css, inject_pwa_head, section_title

st.set_page_config(page_title="Employés - Suivi de Chantier", page_icon="👷", layout="wide")
db.init_db()
inject_custom_css()
inject_pwa_head()
section_title("Gestion des employés", "👷")

# ---------------------------------------------------------------------------
# Ajout d'un employé
# ---------------------------------------------------------------------------
with st.expander("➕ Ajouter un nouvel employé", expanded=False):
    with st.form("form_ajout_employe", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            nom = st.text_input("Nom *")
        with c2:
            fonction = st.text_input("Fonction (ex : Maçon, Électricien, Plombier)")
        with c3:
            telephone = st.text_input("Téléphone")
        montant_du = st.number_input("Montant dû / convenu (0 = non défini)", min_value=0.0, step=1000.0)
        if st.form_submit_button("💾 Ajouter l'employé", width="stretch", type="primary"):
            if not nom.strip():
                st.error("Le nom est obligatoire.")
            elif db.get_employe_by_nom(nom.strip()):
                st.error("Un employé porte déjà ce nom.")
            else:
                db.add_employe(nom.strip(), fonction.strip(), telephone.strip(), montant_du)
                st.success(f"Employé « {nom} » ajouté.")
                st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# Liste des employés
# ---------------------------------------------------------------------------
section_title("Liste des employés", "📋")
totaux = db.get_totaux_employes()

if not totaux:
    st.info("Aucun employé enregistré pour le moment.")
else:
    df = pd.DataFrame(totaux)
    df_affiche = df[["nom", "fonction", "telephone", "montant_du", "total_avance", "total_paye", "reste_a_payer"]].rename(
        columns={
            "nom": "Nom", "fonction": "Fonction", "telephone": "Téléphone", "montant_du": "Total dû",
            "total_avance": "Total avancé", "total_paye": "Total payé", "reste_a_payer": "Reste à payer",
        }
    )
    st.dataframe(df_affiche, width="stretch", hide_index=True)

st.divider()

# ---------------------------------------------------------------------------
# Fiche employé
# ---------------------------------------------------------------------------
section_title("Fiche employé", "🪪")
employes = db.get_employes()

if not employes:
    st.info("Ajoutez un employé pour consulter sa fiche.")
else:
    options = {e["nom"]: e["id"] for e in employes}
    choix = st.selectbox("Sélectionner un employé", list(options.keys()))
    eid = options[choix]
    e = db.get_employe(eid)
    t = db.get_totaux_employe(eid)

    st.markdown(
        f"""
        <div class="fiche-header">
            <h2>{e['nom']}</h2>
            <p>🛠️ {e['fonction'] or 'Fonction non renseignée'} &nbsp;·&nbsp; 📞 {e['telephone'] or '-'}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total dû", format_montant(t["montant_du"]))
    m2.metric("Total avancé", format_montant(t["total_avance"]))
    m3.metric("Total payé", format_montant(t["total_paye"]))
    m4.metric("Reste à payer", format_montant(t["reste_a_payer"]))

    tab_hist, tab_avance, tab_paiement, tab_edit = st.tabs(
        ["📜 Historique des mouvements", "➕ Enregistrer une avance", "➕ Enregistrer un paiement complémentaire", "✏️ Modifier / supprimer"]
    )

    with tab_hist:
        mouvements = db.get_mouvements_employe(eid)
        if mouvements:
            df_m = pd.DataFrame(mouvements)
            df_m["type"] = df_m["type"].map({"avance": "Avance", "paiement": "Paiement complémentaire"})
            df_m = df_m[["date", "type", "montant", "commentaire"]]
            df_m.columns = ["Date", "Type", "Montant", "Commentaire"]
            st.dataframe(df_m, width="stretch", hide_index=True)
        else:
            st.info("Aucun mouvement enregistré pour cet employé.")

    with tab_avance:
        with st.form(f"form_avance_{eid}", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                a_date = st.date_input("Date de l'avance", value=date.today())
                a_montant = st.number_input("Montant de l'avance", min_value=0.0, step=1000.0)
            with c2:
                a_commentaire = st.text_input("Commentaire (ex : Avance 1)")
            if st.form_submit_button("💾 Enregistrer l'avance", width="stretch", type="primary"):
                if a_montant <= 0:
                    st.error("Le montant doit être supérieur à 0.")
                else:
                    db.add_mouvement_employe(eid, "avance", a_montant, a_date.isoformat(), a_commentaire.strip())
                    st.success(f"Avance de {format_montant(a_montant)} enregistrée.")
                    st.rerun()

    with tab_paiement:
        with st.form(f"form_paiement_emp_{eid}", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                p_date = st.date_input("Date du paiement", value=date.today())
                p_montant = st.number_input("Montant du paiement", min_value=0.0, step=1000.0)
            with c2:
                p_commentaire = st.text_input("Commentaire")
            if st.form_submit_button("💾 Enregistrer le paiement", width="stretch", type="primary"):
                if p_montant <= 0:
                    st.error("Le montant doit être supérieur à 0.")
                else:
                    db.add_mouvement_employe(eid, "paiement", p_montant, p_date.isoformat(), p_commentaire.strip())
                    st.success(f"Paiement de {format_montant(p_montant)} enregistré.")
                    st.rerun()

    with tab_edit:
        with st.form(f"form_edit_employe_{eid}"):
            c1, c2, c3 = st.columns(3)
            with c1:
                e_nom = st.text_input("Nom", value=e["nom"])
            with c2:
                e_fonction = st.text_input("Fonction", value=e["fonction"] or "")
            with c3:
                e_tel = st.text_input("Téléphone", value=e["telephone"] or "")
            e_montant_du = st.number_input("Montant dû / convenu", min_value=0.0, value=float(e["montant_du"] or 0), step=1000.0)

            if st.form_submit_button("💾 Mettre à jour", width="stretch", type="primary"):
                db.update_employe(eid, e_nom.strip(), e_fonction.strip(), e_tel.strip(), e_montant_du)
                st.success("Employé mis à jour.")
                st.rerun()

        confirm_delete(
            f"l'employé « {e['nom']} »", key=f"employe_{eid}",
            on_confirm=lambda: db.delete_employe(eid),
        )

bottom_nav_mobile()
