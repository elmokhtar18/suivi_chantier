"""
Page "Chantiers" : liste, ajout, modification et suppression des chantiers.

L'application gère plusieurs chantiers en parallèle : chacun a ses propres
étapes, catégories, fournisseurs, employés et dépenses (cloisonnement total,
voir `database.database`). Le sélecteur de chantier actif, dans la barre
latérale sur toutes les pages, détermine lequel est affiché/édité ailleurs
dans l'application.
"""

import pandas as pd
import streamlit as st

from database import database as db
from utils.helpers import (
    bottom_nav_mobile,
    chantier_selector,
    confirm_delete,
    flash,
    inject_custom_css,
    inject_pwa_head,
    render_flash,
    section_title,
)

st.set_page_config(page_title="Chantiers - Suivi de Chantier", page_icon="🏗️", layout="wide")
db.init_db()
inject_custom_css()
inject_pwa_head()
render_flash()
chantier_selector()
section_title("Gestion des chantiers", "🏗️")

STATUTS_CHANTIER = ["En cours", "En pause", "Terminé"]

# ---------------------------------------------------------------------------
# Ajout d'un chantier
# ---------------------------------------------------------------------------
with st.expander("➕ Ajouter un nouveau chantier", expanded=False):
    with st.form("form_ajout_chantier", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            nom = st.text_input("Nom *")
            statut = st.selectbox("Statut", STATUTS_CHANTIER, key="statut_ajout_chantier")
        with c2:
            adresse = st.text_input("Adresse / lieu")
        description = st.text_area("Description", height=70)
        if st.form_submit_button("💾 Créer le chantier", width="stretch", type="primary"):
            if not nom.strip():
                st.error("Le nom est obligatoire.")
            elif any(c["nom"] == nom.strip() for c in db.get_chantiers()):
                st.error("Un chantier porte déjà ce nom.")
            else:
                nouveau_id = db.add_chantier(nom.strip(), adresse.strip(), description.strip(), statut)
                flash(f"Chantier « {nom.strip()} » créé.")
                # Bascule automatiquement sur le nouveau chantier (voir chantier_selector).
                st.session_state["_chantier_actif_id_demande"] = nouveau_id
                st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# Liste des chantiers
# ---------------------------------------------------------------------------
section_title("Tous les chantiers", "📋")
totaux = db.get_totaux_chantiers()
df = pd.DataFrame(totaux)
df_affiche = df[["nom", "statut", "adresse", "nb_depenses", "total_depenses"]].rename(columns={
    "nom": "Nom", "statut": "Statut", "adresse": "Adresse",
    "nb_depenses": "Nb dépenses", "total_depenses": "Total dépensé",
})
st.dataframe(df_affiche, width="stretch", hide_index=True)

st.divider()

# ---------------------------------------------------------------------------
# Modifier / supprimer un chantier
# ---------------------------------------------------------------------------
section_title("Modifier ou supprimer un chantier", "✏️")
chantiers = db.get_chantiers()
options = {c["nom"]: c["id"] for c in chantiers}
choix = st.selectbox("Sélectionner un chantier", list(options.keys()), key="select_chantier_edit")
cid = options[choix]
c = db.get_chantier(cid)

with st.form(f"form_edit_chantier_{cid}"):
    c1, c2 = st.columns(2)
    with c1:
        e_nom = st.text_input("Nom", value=c["nom"])
        e_statut = st.selectbox(
            "Statut", STATUTS_CHANTIER,
            index=STATUTS_CHANTIER.index(c["statut"]) if c["statut"] in STATUTS_CHANTIER else 0,
        )
    with c2:
        e_adresse = st.text_input("Adresse / lieu", value=c["adresse"] or "")
    e_description = st.text_area("Description", value=c["description"] or "", height=70)
    if st.form_submit_button("💾 Mettre à jour", width="stretch", type="primary"):
        db.update_chantier(cid, e_nom.strip(), e_adresse.strip(), e_description.strip(), e_statut)
        flash("Chantier mis à jour.")
        # Pas besoin de resynchroniser le sélecteur ici : il est piloté par
        # l'id du chantier (chantier_actif_id, inchangé par un renommage), pas
        # par son nom — voir chantier_selector.
        st.rerun()

st.warning(
    "⚠️ Supprimer un chantier supprime **définitivement** toutes ses données : "
    "étapes, catégories, fournisseurs, employés, dépenses, paiements. Action irréversible."
)
if len(chantiers) <= 1:
    st.info("Impossible de supprimer le dernier chantier restant.")
else:
    confirm_delete(
        f"le chantier « {c['nom']} » et TOUTES ses données", key=f"chantier_{cid}",
        on_confirm=lambda: db.delete_chantier(cid),
    )

bottom_nav_mobile()
