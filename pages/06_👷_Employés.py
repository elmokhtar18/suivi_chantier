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
from utils import notifications
from utils.helpers import (
    MODES_PAIEMENT,
    STATUTS_PAIEMENT as STATUTS,
    bottom_nav_mobile,
    confirm_delete,
    enregistrer_justificatif,
    flash,
    format_date,
    format_montant,
    inject_custom_css,
    inject_pwa_head,
    render_flash,
    section_title,
)

st.set_page_config(page_title="Employés - Suivi de Chantier", page_icon="👷", layout="wide")
db.init_db()
inject_custom_css()
inject_pwa_head()
render_flash()
section_title("Gestion des employés", "👷")


# ---------------------------------------------------------------------------
# Modales : modifier / supprimer un mouvement (avance / paiement complémentaire)
# saisi manuellement. Un mouvement généré automatiquement par une dépense
# (`depense_id` renseigné) n'est pas modifiable ici : il doit être modifié
# depuis la dépense elle-même (page Dépenses), sinon les deux enregistrements
# se désynchroniseraient silencieusement.
# ---------------------------------------------------------------------------
@st.dialog("✏️ Modifier le mouvement")
def dialog_modifier_mouvement(mouvement_id):
    m = db.get_mouvement_employe(mouvement_id)
    if m is None:
        st.error("Ce mouvement n'existe plus (il a peut-être déjà été supprimé).")
        return

    libelle = "Avance" if m["type"] == "avance" else "Paiement complémentaire"
    with st.form(f"form_edit_mouvement_{mouvement_id}"):
        c1, c2 = st.columns(2)
        with c1:
            m_date = st.date_input(f"Date ({libelle})", value=date.fromisoformat(m["date"]))
            m_montant = st.number_input("Montant", min_value=0.0, value=float(m["montant"] or 0), step=1000.0)
        with c2:
            m_commentaire = st.text_input("Commentaire", value=m["commentaire"] or "")

        if st.form_submit_button("💾 Enregistrer", width="stretch", type="primary"):
            if m_montant <= 0:
                st.error("Le montant doit être supérieur à 0.")
            else:
                db.update_mouvement_employe(mouvement_id, m_montant, m_date.isoformat(), m_commentaire.strip())
                flash(f"{libelle} mis(e) à jour.")
                st.rerun()


@st.dialog("🗑️ Supprimer le mouvement")
def dialog_supprimer_mouvement(mouvement_id):
    m = db.get_mouvement_employe(mouvement_id)
    if m is None:
        st.info("Ce mouvement a déjà été supprimé.")
        return

    libelle = "Avance" if m["type"] == "avance" else "Paiement complémentaire"
    st.warning(
        f"Confirmer la suppression de cette **{libelle.lower()}** de "
        f"{format_montant(m['montant'])} ({format_date(m['date'])}) ?\n\n"
        "Cette action est irréversible."
    )
    c1, c2 = st.columns(2)
    with c1:
        if st.button("✅ Confirmer la suppression", type="primary", width="stretch", key=f"dlg_del_mvt_ok_{mouvement_id}"):
            db.delete_mouvement_employe(mouvement_id)
            flash(f"{libelle} supprimé(e).", icone="🗑️")
            st.rerun()
    with c2:
        if st.button("↩️ Annuler", width="stretch", key=f"dlg_del_mvt_cancel_{mouvement_id}"):
            st.rerun()

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

    tab_hist, tab_depense, tab_avance, tab_paiement, tab_edit = st.tabs([
        "📜 Historique des mouvements",
        "➕ Ajouter une dépense employé",
        "➕ Enregistrer une avance",
        "➕ Enregistrer un paiement complémentaire",
        "✏️ Modifier / supprimer",
    ])

    with tab_hist:
        mouvements = db.get_mouvements_employe(eid)
        if not mouvements:
            st.info("Aucun mouvement enregistré pour cet employé.")
        else:
            for m in mouvements:
                libelle = "Avance" if m["type"] == "avance" else "Paiement complémentaire"
                with st.container(border=True):
                    col_info, col_montant, col_edit, col_del = st.columns([4, 1.3, 0.6, 0.6])
                    with col_info:
                        lien = " · 🔗 lié à une dépense" if m["depense_id"] else ""
                        st.markdown(
                            f"**{libelle}**{lien}  \n"
                            f"{format_date(m['date'])}"
                            + (f" · {m['commentaire']}" if m["commentaire"] else "")
                        )
                    with col_montant:
                        st.markdown(f"**{format_montant(m['montant'])}**")
                    with col_edit:
                        if m["depense_id"]:
                            st.button("✏️", key=f"edit_mvt_{m['id']}", disabled=True, width="stretch",
                                       help="Lié à une dépense : modifiez-la depuis la page Dépenses.")
                        elif st.button("✏️", key=f"edit_mvt_{m['id']}", help="Modifier ce mouvement", width="stretch"):
                            dialog_modifier_mouvement(m["id"])
                    with col_del:
                        if m["depense_id"]:
                            st.button("🗑️", key=f"del_mvt_{m['id']}", disabled=True, width="stretch",
                                       help="Lié à une dépense : supprimez-la depuis la page Dépenses.")
                        elif st.button("🗑️", key=f"del_mvt_{m['id']}", help="Supprimer ce mouvement", width="stretch"):
                            dialog_supprimer_mouvement(m["id"])

    with tab_depense:
        etapes = db.get_etapes()
        if not etapes:
            st.warning("Créez d'abord au moins une étape sur la page **Étapes**.")
        else:
            with st.form(f"form_depense_employe_{eid}", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                with c1:
                    d_date = st.date_input("Date", value=date.today(), key=f"d_date_{eid}")
                    d_designation = st.text_input("Désignation (ex : Salaire semaine 1)", key=f"d_desig_{eid}")
                with c2:
                    d_etape_nom = st.selectbox("Étape *", [e2["nom"] for e2 in etapes], key=f"d_etape_{eid}")
                    d_mode = st.selectbox("Mode de paiement", MODES_PAIEMENT, key=f"d_mode_{eid}")
                with c3:
                    d_montant = st.number_input("Montant", min_value=0.0, step=1000.0, key=f"d_montant_{eid}")
                    d_statut = st.selectbox("Statut paiement", STATUTS, key=f"d_statut_{eid}")
                d_observation = st.text_area("Observation", height=70, key=f"d_obs_{eid}")

                st.markdown("**📎 Justificatif (facultatif)**")
                c4, c5 = st.columns(2)
                with c4:
                    d_photo = st.camera_input("📷 Prendre une photo", key=f"d_cam_{eid}")
                with c5:
                    d_fichier = st.file_uploader(
                        "📁 ...ou importer une image/un PDF", type=["png", "jpg", "jpeg", "pdf"], key=f"d_up_{eid}"
                    )

                if st.form_submit_button("💾 Enregistrer la dépense", width="stretch", type="primary"):
                    if not d_designation.strip():
                        st.error("La désignation est obligatoire.")
                    elif d_montant <= 0:
                        st.error("Le montant doit être supérieur à 0.")
                    else:
                        etape_id = next(e2["id"] for e2 in etapes if e2["nom"] == d_etape_nom)
                        categorie_id = db.get_or_create_categorie("Employé")
                        justificatif_path = enregistrer_justificatif(d_fichier or d_photo, prefixe="depense_employe")
                        db.add_depense(
                            date_depense=d_date.isoformat(),
                            designation=d_designation.strip(),
                            categorie_id=categorie_id,
                            etape_id=etape_id,
                            fournisseur_id=None,
                            employe_id=eid,
                            quantite=0,
                            prix_unitaire=0,
                            montant_total=d_montant,
                            mode_paiement=d_mode,
                            statut_paiement=d_statut,
                            observation=d_observation.strip(),
                            justificatif_path=justificatif_path,
                        )
                        notifications.notifier_nouvelle_depense(d_designation, format_montant(d_montant))
                        notifications.verifier_budget_etape(etape_id)
                        st.rerun()

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
