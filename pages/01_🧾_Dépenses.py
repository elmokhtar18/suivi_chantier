"""
Page "Dépenses" : enregistrement, modification, suppression, recherche,
filtrage, tri et export (Excel / PDF / CSV) de toutes les dépenses du chantier.

Chaque dépense créée, modifiée ou supprimée ici est automatiquement répercutée :
- sur le coût total de son étape (page Étapes),
- sur la dette du fournisseur concerné (page Fournisseurs / Dettes),
- sur le total payé de l'employé concerné (page Employés),
- sur les statistiques et le tableau de bord (page d'accueil).
Cette automatisation est assurée par `database.add_depense`/`update_depense`/
`delete_depense` et ne nécessite aucune actualisation manuelle : Streamlit
ré-exécute la page (et donc relit la base) après chaque enregistrement.

La modification et la suppression se font ligne par ligne (boutons ✏️/🗑️)
via des modales natives Streamlit (`st.dialog`), qui apportent nativement
l'animation d'ouverture/fermeture.
"""

from datetime import date

import pandas as pd
import streamlit as st

from database import database as db
from utils import notifications
from utils.exports import export_csv_bytes, export_excel_bytes, export_pdf_bytes
from utils.helpers import (
    MODES_PAIEMENT,
    STATUTS_PAIEMENT as STATUTS,
    afficher_justificatif,
    bottom_nav_mobile,
    bouton_partage_pdf,
    chantier_selector,
    enregistrer_justificatif,
    flash,
    format_date,
    format_montant,
    inject_custom_css,
    inject_pwa_head,
    render_flash,
    section_title,
    statut_badge,
)

st.set_page_config(page_title="Dépenses - Suivi de Chantier", page_icon="🧾", layout="wide")
db.init_db()
inject_custom_css()
inject_pwa_head()
render_flash()
chantier_id = chantier_selector()
section_title("Gestion des dépenses", "🧾")

NOUVEAU_SENTINEL = "➕ Nouveau..."
PAGE_SIZE = 15


def _selectbox_avec_ajout(label, options, key, aide=None):
    """Selectbox classique + option pour saisir une nouvelle valeur à la volée."""
    choix = st.selectbox(label, options + [NOUVEAU_SENTINEL], key=key, help=aide)
    if choix == NOUVEAU_SENTINEL:
        return st.text_input(f"Nouveau : {label}", key=f"{key}_new").strip()
    return choix


# ---------------------------------------------------------------------------
# Modales : modifier / supprimer une dépense
# ---------------------------------------------------------------------------

@st.dialog("✏️ Modifier la dépense")
def dialog_modifier_depense(depense_id):
    depense = db.get_depense(depense_id)
    if depense is None:
        st.error("Cette dépense n'existe plus (elle a peut-être déjà été supprimée).")
        return

    etapes = db.get_etapes(chantier_id)
    fournisseurs = db.get_fournisseurs(chantier_id)
    employes = db.get_employes(chantier_id)
    categories = [c["nom"] for c in db.get_categories(chantier_id)]

    if depense["justificatif_path"]:
        st.markdown("**📎 Justificatif actuel**")
        afficher_justificatif(depense["justificatif_path"])

    with st.form(f"form_dialog_edit_{depense_id}"):
        c1, c2, c3 = st.columns(3)
        with c1:
            e_date = st.date_input("Date", value=date.fromisoformat(depense["date"]))
            e_designation = st.text_input("Désignation", value=depense["designation"])
            noms_categories = ["Aucune"] + categories
            e_categorie = st.selectbox(
                "Catégorie", noms_categories,
                index=noms_categories.index(depense["categorie_nom"]) if depense["categorie_nom"] in noms_categories else 0,
            )
        with c2:
            noms_etapes = [e["nom"] for e in etapes]
            e_etape = st.selectbox(
                "Étape", noms_etapes,
                index=noms_etapes.index(depense["etape_nom"]) if depense["etape_nom"] in noms_etapes else 0,
            )
            noms_fournisseurs = ["Aucun"] + [f["nom"] for f in fournisseurs]
            e_fournisseur = st.selectbox(
                "Fournisseur", noms_fournisseurs,
                index=noms_fournisseurs.index(depense["fournisseur_nom"]) if depense["fournisseur_nom"] in noms_fournisseurs else 0,
            )
            noms_employes = ["Aucun"] + [e["nom"] for e in employes]
            e_employe = st.selectbox(
                "Employé concerné", noms_employes,
                index=noms_employes.index(depense["employe_nom"]) if depense["employe_nom"] in noms_employes else 0,
            )
        with c3:
            e_quantite = st.number_input("Quantité", min_value=0.0, value=float(depense["quantite"] or 0))
            e_prix_unitaire = st.number_input("Prix unitaire", min_value=0.0, value=float(depense["prix_unitaire"] or 0))
            e_montant = st.number_input("Montant total", min_value=0.0, value=float(depense["montant_total"] or 0))

        c4, c5 = st.columns(2)
        with c4:
            e_mode = st.selectbox(
                "Mode de paiement", MODES_PAIEMENT,
                index=MODES_PAIEMENT.index(depense["mode_paiement"]) if depense["mode_paiement"] in MODES_PAIEMENT else 0,
            )
        with c5:
            e_statut = st.selectbox(
                "Statut paiement", STATUTS,
                index=STATUTS.index(depense["statut_paiement"]) if depense["statut_paiement"] in STATUTS else 0,
            )
        e_observation = st.text_area("Observation", value=depense["observation"] or "")

        st.markdown("**📎 Remplacer le justificatif (facultatif)**")
        c6, c7 = st.columns(2)
        with c6:
            e_photo = st.camera_input("📷 Prendre une nouvelle photo", key=f"cam_{depense_id}")
        with c7:
            e_fichier = st.file_uploader(
                "📁 ...ou importer un fichier", type=["png", "jpg", "jpeg", "pdf"], key=f"up_{depense_id}"
            )

        if st.form_submit_button("💾 Enregistrer", width="stretch", type="primary"):
            if not e_designation.strip():
                st.error("La désignation est obligatoire.")
            else:
                etape_id = next(e["id"] for e in etapes if e["nom"] == e_etape)
                fournisseur_id = db.get_or_create_fournisseur(chantier_id, e_fournisseur) if e_fournisseur != "Aucun" else None
                employe_id = db.get_or_create_employe(chantier_id, e_employe) if e_employe != "Aucun" else None
                categorie_id = db.get_or_create_categorie(chantier_id, e_categorie) if e_categorie != "Aucune" else None
                nouveau_justificatif = enregistrer_justificatif(e_fichier or e_photo)
                db.update_depense(
                    depense_id=depense_id, date_depense=e_date.isoformat(), designation=e_designation.strip(),
                    categorie_id=categorie_id, etape_id=etape_id, fournisseur_id=fournisseur_id, employe_id=employe_id,
                    quantite=e_quantite, prix_unitaire=e_prix_unitaire, montant_total=e_montant,
                    mode_paiement=e_mode, statut_paiement=e_statut, observation=e_observation.strip(),
                    justificatif_path=nouveau_justificatif or depense["justificatif_path"] or "",
                )
                flash(f"Dépense « {e_designation.strip()} » mise à jour.")
                notifications.verifier_budget_etape(etape_id)
                st.rerun()


@st.dialog("🗑️ Supprimer la dépense")
def dialog_supprimer_depense(depense_id):
    depense = db.get_depense(depense_id)
    if depense is None:
        st.info("Cette dépense a déjà été supprimée.")
        return

    st.warning(
        f"Confirmer la suppression de **{depense['designation']}** "
        f"({format_montant(depense['montant_total'])}, {format_date(depense['date'])}) ?\n\n"
        "Cette action est irréversible."
    )
    c1, c2 = st.columns(2)
    with c1:
        if st.button("✅ Confirmer la suppression", type="primary", width="stretch", key=f"dlg_del_ok_{depense_id}"):
            db.delete_depense(depense_id)
            flash(f"Dépense « {depense['designation']} » supprimée.", icone="🗑️")
            st.rerun()
    with c2:
        if st.button("↩️ Annuler", width="stretch", key=f"dlg_del_cancel_{depense_id}"):
            st.rerun()


# ---------------------------------------------------------------------------
# Formulaire d'ajout
# ---------------------------------------------------------------------------
with st.expander("➕ Enregistrer une nouvelle dépense", expanded=False):
    etapes = db.get_etapes(chantier_id)
    fournisseurs = db.get_fournisseurs(chantier_id)
    employes = db.get_employes(chantier_id)
    categories = [c["nom"] for c in db.get_categories(chantier_id)]

    if not etapes:
        st.warning("Créez d'abord au moins une étape sur la page **Étapes**.")
    else:
        with st.form("form_ajout_depense", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                f_date = st.date_input("Date", value=date.today())
                f_designation = st.text_input("Désignation")
                f_categorie = _selectbox_avec_ajout("Catégorie", ["Aucune"] + categories, "cat_ajout")
            with c2:
                f_etape_nom = st.selectbox("Étape *", [e["nom"] for e in etapes])
                f_fournisseur = _selectbox_avec_ajout(
                    "Fournisseur (facultatif)", ["Aucun"] + [f["nom"] for f in fournisseurs], "four_ajout"
                )
                f_employe = _selectbox_avec_ajout(
                    "Employé concerné (facultatif)", ["Aucun"] + [e["nom"] for e in employes], "emp_ajout"
                )
            with c3:
                f_quantite = st.number_input("Quantité", min_value=0.0, value=0.0, step=1.0)
                f_prix_unitaire = st.number_input("Prix unitaire", min_value=0.0, value=0.0, step=100.0)
                f_montant_manuel = st.number_input(
                    "Montant total (0 = calcul auto Qté × PU)", min_value=0.0, value=0.0, step=100.0
                )

            c4, c5 = st.columns(2)
            with c4:
                f_mode = st.selectbox("Mode de paiement", MODES_PAIEMENT)
            with c5:
                f_statut = st.selectbox("Statut paiement", STATUTS)
            f_observation = st.text_area("Observation", height=70)

            st.markdown("**📎 Justificatif (facultatif)**")
            c6, c7 = st.columns(2)
            with c6:
                f_photo = st.camera_input("📷 Prendre une photo")
            with c7:
                f_fichier = st.file_uploader("📁 ...ou importer une image/un PDF", type=["png", "jpg", "jpeg", "pdf"])

            submitted = st.form_submit_button("💾 Enregistrer la dépense", width="stretch", type="primary")
            if submitted:
                if not f_designation.strip():
                    st.error("La désignation est obligatoire.")
                else:
                    montant = f_montant_manuel if f_montant_manuel > 0 else f_quantite * f_prix_unitaire
                    etape_id = next(e["id"] for e in etapes if e["nom"] == f_etape_nom)
                    fournisseur_id = (
                        db.get_or_create_fournisseur(chantier_id, f_fournisseur) if f_fournisseur and f_fournisseur != "Aucun" else None
                    )
                    employe_id = (
                        db.get_or_create_employe(chantier_id, f_employe) if f_employe and f_employe != "Aucun" else None
                    )
                    categorie_id = db.get_or_create_categorie(chantier_id, f_categorie) if f_categorie and f_categorie != "Aucune" else None
                    justificatif_path = enregistrer_justificatif(f_fichier or f_photo)
                    db.add_depense(
                        chantier_id=chantier_id,
                        date_depense=f_date.isoformat(),
                        designation=f_designation.strip(),
                        categorie_id=categorie_id,
                        etape_id=etape_id,
                        fournisseur_id=fournisseur_id,
                        employe_id=employe_id,
                        quantite=f_quantite,
                        prix_unitaire=f_prix_unitaire,
                        montant_total=montant,
                        mode_paiement=f_mode,
                        statut_paiement=f_statut,
                        observation=f_observation.strip(),
                        justificatif_path=justificatif_path,
                    )
                    notifications.notifier_nouvelle_depense(f_designation, format_montant(montant))
                    notifications.verifier_budget_etape(etape_id)
                    st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# Filtres
# ---------------------------------------------------------------------------
depenses = db.get_depenses(chantier_id)
df = pd.DataFrame(depenses)

section_title("Filtrer, rechercher et trier", "🔍")

if df.empty:
    st.info("Aucune dépense enregistrée pour le moment.")
else:
    etapes_dispo = sorted(df["etape_nom"].dropna().unique().tolist())
    categories_dispo = sorted([c for c in df["categorie_nom"].dropna().unique().tolist() if c])
    fournisseurs_dispo = sorted([f for f in df["fournisseur_nom"].dropna().unique().tolist() if f])
    employes_dispo = sorted([e for e in df["employe_nom"].dropna().unique().tolist() if e])

    fc1, fc2, fc3, fc4, fc5 = st.columns(5)
    with fc1:
        recherche = st.text_input("Recherche (désignation, observation)", key="filtre_recherche")
    with fc2:
        filtre_etapes = st.multiselect("Étape", etapes_dispo, key="filtre_etapes")
    with fc3:
        filtre_categories = st.multiselect("Catégorie", categories_dispo, key="filtre_categories")
    with fc4:
        filtre_fournisseurs = st.multiselect("Fournisseur", fournisseurs_dispo, key="filtre_fournisseurs")
    with fc5:
        filtre_employes = st.multiselect("Employé", employes_dispo, key="filtre_employes")

    fc6, fc7, fc8, fc9, fc10 = st.columns(5)
    with fc6:
        filtre_statut = st.multiselect("Statut paiement", STATUTS, key="filtre_statuts")
    with fc7:
        date_min = st.date_input("Du", value=None, key="date_min")
    with fc8:
        date_max = st.date_input("Au", value=None, key="date_max")
    with fc9:
        montant_min = st.number_input("Montant min", min_value=0.0, value=0.0, step=1000.0, key="montant_min")
    with fc10:
        montant_max = st.number_input("Montant max (0 = illimité)", min_value=0.0, value=0.0, step=1000.0, key="montant_max")

    df_f = df.copy()
    if recherche:
        masque = (
            df_f["designation"].str.contains(recherche, case=False, na=False)
            | df_f["observation"].str.contains(recherche, case=False, na=False)
        )
        df_f = df_f[masque]
    if filtre_etapes:
        df_f = df_f[df_f["etape_nom"].isin(filtre_etapes)]
    if filtre_categories:
        df_f = df_f[df_f["categorie_nom"].isin(filtre_categories)]
    if filtre_fournisseurs:
        df_f = df_f[df_f["fournisseur_nom"].isin(filtre_fournisseurs)]
    if filtre_employes:
        df_f = df_f[df_f["employe_nom"].isin(filtre_employes)]
    if filtre_statut:
        df_f = df_f[df_f["statut_paiement"].isin(filtre_statut)]
    if date_min:
        df_f = df_f[df_f["date"] >= date_min.isoformat()]
    if date_max:
        df_f = df_f[df_f["date"] <= date_max.isoformat()]
    if montant_min > 0:
        df_f = df_f[df_f["montant_total"] >= montant_min]
    if montant_max > 0:
        df_f = df_f[df_f["montant_total"] <= montant_max]

    tri_col, tri_dir = st.columns([3, 1])
    with tri_col:
        colonne_tri = st.selectbox(
            "Trier par", ["date", "montant_total", "designation", "etape_nom", "categorie_nom"], index=0
        )
    with tri_dir:
        ordre_desc = st.checkbox("Décroissant", value=True)
    df_f = df_f.sort_values(colonne_tri, ascending=not ordre_desc).reset_index(drop=True)

    st.caption(f"{len(df_f)} dépense(s) trouvée(s) sur {len(df)} — Total : {format_montant(df_f['montant_total'].sum())}")

    df_affiche = df_f[[
        "id", "date", "designation", "categorie_nom", "etape_nom", "fournisseur_nom",
        "employe_nom", "quantite", "prix_unitaire", "montant_total", "mode_paiement",
        "statut_paiement", "observation",
    ]].rename(columns={
        "id": "ID", "date": "Date", "designation": "Désignation", "categorie_nom": "Catégorie",
        "etape_nom": "Étape", "fournisseur_nom": "Fournisseur", "employe_nom": "Employé",
        "quantite": "Qté", "prix_unitaire": "PU", "montant_total": "Montant",
        "mode_paiement": "Mode paiement", "statut_paiement": "Statut", "observation": "Observation",
    })

    # ------------------------------------------------------------------
    # Export (porte toujours sur l'intégralité du résultat filtré, pas
    # seulement sur la page actuellement affichée à l'écran)
    # ------------------------------------------------------------------
    exp1, exp2, exp3 = st.columns(3)
    with exp1:
        st.download_button(
            "⬇️ Exporter en Excel", export_excel_bytes(df_affiche, "Dépenses"),
            file_name="depenses.xlsx", width="stretch",
        )
    with exp2:
        _pdf_depenses = export_pdf_bytes(df_affiche, "Dépenses du chantier")
        st.download_button(
            "⬇️ Exporter en PDF", _pdf_depenses,
            file_name="depenses.pdf", width="stretch",
        )
        bouton_partage_pdf(_pdf_depenses, "depenses.pdf", titre="Dépenses du chantier")
    with exp3:
        st.download_button(
            "⬇️ Exporter en CSV", export_csv_bytes(df_affiche),
            file_name="depenses.csv", width="stretch",
        )

    st.divider()

    # ------------------------------------------------------------------
    # Liste des dépenses (paginée), avec actions ✏️ Modifier / 🗑️ Supprimer
    # sur chaque ligne
    # ------------------------------------------------------------------
    section_title("Dépenses", "📋")

    total_pages = max(1, -(-len(df_f) // PAGE_SIZE))  # division entière arrondie au-dessus
    page_actuelle = min(max(st.session_state.get("depenses_page", 1), 1), total_pages)
    st.session_state["depenses_page"] = page_actuelle

    pc1, pc2, pc3 = st.columns([1, 2, 1])
    with pc1:
        if st.button("◀ Précédent", disabled=page_actuelle <= 1, width="stretch", key="page_prec"):
            st.session_state["depenses_page"] = page_actuelle - 1
            st.rerun()
    with pc2:
        st.markdown(
            f"<div style='text-align:center; padding-top:0.45rem;'>Page {page_actuelle} sur {total_pages}</div>",
            unsafe_allow_html=True,
        )
    with pc3:
        if st.button("Suivant ▶", disabled=page_actuelle >= total_pages, width="stretch", key="page_suiv"):
            st.session_state["depenses_page"] = page_actuelle + 1
            st.rerun()

    debut = (page_actuelle - 1) * PAGE_SIZE
    depenses_page = df_f.iloc[debut:debut + PAGE_SIZE]

    for _, d in depenses_page.iterrows():
        with st.container(border=True):
            col_info, col_montant, col_statut, col_edit, col_del = st.columns([4, 1.3, 1.1, 0.6, 0.6])
            with col_info:
                # Les colonnes optionnelles (catégorie/étape/fournisseur/employé absents)
                # remontent en NaN (float) dans le DataFrame, pas en None : pd.notna()
                # est nécessaire, un simple `or`/`if x` laisserait passer le NaN (truthy).
                complements = " · ".join(filter(None, [
                    d["categorie_nom"] if pd.notna(d["categorie_nom"]) else "Non catégorisé",
                    d["etape_nom"] if pd.notna(d["etape_nom"]) else None,
                    f"🧱 {d['fournisseur_nom']}" if pd.notna(d["fournisseur_nom"]) else None,
                    f"👷 {d['employe_nom']}" if pd.notna(d["employe_nom"]) else None,
                ]))
                designation = d["designation"] if pd.notna(d["designation"]) and d["designation"] else "(sans désignation)"
                piece_jointe = " 📎" if pd.notna(d["justificatif_path"]) and d["justificatif_path"] else ""
                st.markdown(f"**{designation}**{piece_jointe}  \n"
                            f"{format_date(d['date'])} · {complements}")
            with col_montant:
                st.markdown(f"**{format_montant(d['montant_total'])}**")
            with col_statut:
                st.markdown(statut_badge(d["statut_paiement"]), unsafe_allow_html=True)
            with col_edit:
                if st.button("✏️", key=f"edit_{d['id']}", help="Modifier cette dépense", width="stretch"):
                    dialog_modifier_depense(d["id"])
            with col_del:
                if st.button("🗑️", key=f"del_{d['id']}", help="Supprimer cette dépense", width="stretch"):
                    dialog_supprimer_depense(d["id"])

bottom_nav_mobile()
