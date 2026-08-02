"""
Page "Dépenses" : enregistrement, modification, suppression, recherche,
filtrage, tri et export (Excel / PDF / CSV) de toutes les dépenses du chantier.

Chaque dépense créée ici est automatiquement répercutée :
- sur le coût total de son étape (page Étapes),
- sur la dette du fournisseur concerné (page Fournisseurs / Dettes),
- sur les avances de l'employé concerné (page Employés),
- sur les statistiques (page Statistiques).
Cette automatisation est assurée par `database.add_depense` / `update_depense`
et ne nécessite aucune actualisation manuelle : Streamlit ré-exécute la page
(et donc relit la base) après chaque enregistrement.
"""

from datetime import date

import pandas as pd
import streamlit as st

from database import database as db
from utils.exports import export_csv_bytes, export_excel_bytes, export_pdf_bytes
from utils.helpers import confirm_delete, format_montant, inject_custom_css, section_title

st.set_page_config(page_title="Dépenses - Suivi de Chantier", page_icon="🧾", layout="wide")
db.init_db()
inject_custom_css()
section_title("Gestion des dépenses", "🧾")

MODES_PAIEMENT = ["Espèces", "Bankily", "Sedad", "Masrvi", "Chèque", "Virement", "Autre"]
STATUTS = ["Payé", "Non payé"]

NOUVEAU_SENTINEL = "➕ Nouveau..."


def _selectbox_avec_ajout(label, options, key, aide=None):
    """Selectbox classique + option pour saisir une nouvelle valeur à la volée."""
    choix = st.selectbox(label, options + [NOUVEAU_SENTINEL], key=key, help=aide)
    if choix == NOUVEAU_SENTINEL:
        return st.text_input(f"Nouveau : {label}", key=f"{key}_new").strip()
    return choix


# ---------------------------------------------------------------------------
# Formulaire d'ajout
# ---------------------------------------------------------------------------
with st.expander("➕ Enregistrer une nouvelle dépense", expanded=False):
    etapes = db.get_etapes()
    fournisseurs = db.get_fournisseurs()
    employes = db.get_employes()
    categories = [c["nom"] for c in db.get_categories()]

    if not etapes:
        st.warning("Créez d'abord au moins une étape sur la page **Étapes**.")
    else:
        with st.form("form_ajout_depense", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                f_date = st.date_input("Date", value=date.today())
                f_designation = st.text_input("Désignation")
                f_categorie = _selectbox_avec_ajout("Catégorie", categories, "cat_ajout")
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

            submitted = st.form_submit_button("💾 Enregistrer la dépense", width="stretch", type="primary")
            if submitted:
                if not f_designation.strip():
                    st.error("La désignation est obligatoire.")
                else:
                    montant = f_montant_manuel if f_montant_manuel > 0 else f_quantite * f_prix_unitaire
                    etape_id = next(e["id"] for e in etapes if e["nom"] == f_etape_nom)
                    fournisseur_id = (
                        db.get_or_create_fournisseur(f_fournisseur) if f_fournisseur and f_fournisseur != "Aucun" else None
                    )
                    employe_id = (
                        db.get_or_create_employe(f_employe) if f_employe and f_employe != "Aucun" else None
                    )
                    categorie_id = db.get_or_create_categorie(f_categorie) if f_categorie else None
                    db.add_depense(
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
                    )
                    st.success(f"Dépense « {f_designation} » enregistrée pour {format_montant(montant)}.")
                    st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# Filtres
# ---------------------------------------------------------------------------
depenses = db.get_depenses()
df = pd.DataFrame(depenses)

section_title("Filtrer, rechercher et trier", "🔍")

if df.empty:
    st.info("Aucune dépense enregistrée pour le moment.")
else:
    etapes_dispo = sorted(df["etape_nom"].dropna().unique().tolist())
    categories_dispo = sorted([c for c in df["categorie_nom"].dropna().unique().tolist() if c])
    fournisseurs_dispo = sorted([f for f in df["fournisseur_nom"].dropna().unique().tolist() if f])

    fc1, fc2, fc3, fc4 = st.columns(4)
    with fc1:
        recherche = st.text_input("Recherche (désignation, observation)")
    with fc2:
        filtre_etapes = st.multiselect("Étape", etapes_dispo)
    with fc3:
        filtre_categories = st.multiselect("Catégorie", categories_dispo)
    with fc4:
        filtre_fournisseurs = st.multiselect("Fournisseur", fournisseurs_dispo)

    fc5, fc6, fc7, fc8, fc9 = st.columns(5)
    with fc5:
        filtre_statut = st.multiselect("Statut paiement", STATUTS)
    with fc6:
        date_min = st.date_input("Du", value=None, key="date_min")
    with fc7:
        date_max = st.date_input("Au", value=None, key="date_max")
    with fc8:
        montant_min = st.number_input("Montant min", min_value=0.0, value=0.0, step=1000.0)
    with fc9:
        montant_max = st.number_input("Montant max (0 = illimité)", min_value=0.0, value=0.0, step=1000.0)

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
    df_f = df_f.sort_values(colonne_tri, ascending=not ordre_desc)

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
    st.dataframe(df_affiche, width="stretch", hide_index=True)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    exp1, exp2, exp3 = st.columns(3)
    with exp1:
        st.download_button(
            "⬇️ Exporter en Excel", export_excel_bytes(df_affiche, "Dépenses"),
            file_name="depenses.xlsx", width="stretch",
        )
    with exp2:
        st.download_button(
            "⬇️ Exporter en PDF", export_pdf_bytes(df_affiche, "Dépenses du chantier"),
            file_name="depenses.pdf", width="stretch",
        )
    with exp3:
        st.download_button(
            "⬇️ Exporter en CSV", export_csv_bytes(df_affiche),
            file_name="depenses.csv", width="stretch",
        )

    st.divider()

    # ------------------------------------------------------------------
    # Modifier / supprimer une dépense
    # ------------------------------------------------------------------
    section_title("Modifier ou supprimer une dépense", "✏️")
    options_depenses = {
        f"#{d['id']} · {d['date']} · {d['designation']} · {format_montant(d['montant_total'])}": d["id"]
        for d in depenses
    }
    choix = st.selectbox("Sélectionner une dépense", ["-"] + list(options_depenses.keys()))

    if choix != "-":
        depense = db.get_depense(options_depenses[choix])
        etapes = db.get_etapes()
        fournisseurs = db.get_fournisseurs()
        employes = db.get_employes()
        categories = [c["nom"] for c in db.get_categories()]

        with st.form("form_edit_depense"):
            c1, c2, c3 = st.columns(3)
            with c1:
                e_date = st.date_input("Date", value=date.fromisoformat(depense["date"]))
                e_designation = st.text_input("Désignation", value=depense["designation"])
                e_categorie = st.selectbox(
                    "Catégorie", categories,
                    index=categories.index(depense["categorie_nom"]) if depense["categorie_nom"] in categories else 0,
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

            if st.form_submit_button("💾 Mettre à jour", width="stretch", type="primary"):
                etape_id = next(e["id"] for e in etapes if e["nom"] == e_etape)
                fournisseur_id = db.get_or_create_fournisseur(e_fournisseur) if e_fournisseur != "Aucun" else None
                employe_id = db.get_or_create_employe(e_employe) if e_employe != "Aucun" else None
                categorie_id = db.get_or_create_categorie(e_categorie) if e_categorie else None
                db.update_depense(
                    depense_id=depense["id"], date_depense=e_date.isoformat(), designation=e_designation.strip(),
                    categorie_id=categorie_id, etape_id=etape_id, fournisseur_id=fournisseur_id, employe_id=employe_id,
                    quantite=e_quantite, prix_unitaire=e_prix_unitaire, montant_total=e_montant,
                    mode_paiement=e_mode, statut_paiement=e_statut, observation=e_observation.strip(),
                )
                st.success("Dépense mise à jour.")
                st.rerun()

        confirm_delete(
            f"la dépense « {depense['designation']} »", key=f"depense_{depense['id']}",
            on_confirm=lambda: db.delete_depense(depense["id"]),
        )
