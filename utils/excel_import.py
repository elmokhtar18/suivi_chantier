"""
Import intelligent de fichiers Excel existants.

Ce module permet d'importer n'importe quel classeur Excel de suivi de
chantier : il liste les feuilles disponibles, détecte automatiquement la
ligne d'en-tête d'un tableau de dépenses ainsi que la correspondance entre
les colonnes du fichier et les champs attendus par l'application (date,
désignation, catégorie, étape, fournisseur, employé, quantité, prix
unitaire, montant, mode/statut de paiement, observation), puis insère les
lignes en base sans perte de données.

Il est utilisé à la fois par la page "Import / Export" (import interactif
avec confirmation des correspondances) et par le script d'initialisation qui
a chargé les données historiques du fichier Excel fourni par l'utilisateur.
"""

import unicodedata

import pandas as pd

from database import database as db

# Synonymes (normalisés) reconnus pour chaque champ canonique de la table "depenses"
CANONICAL_FIELDS = {
    "date": ["date"],
    "designation": ["designation", "libelle", "description", "article", "objet"],
    "categorie": ["categorie", "type materiau", "nature"],
    "etape": ["phase", "etape", "chantier", "tranche"],
    "fournisseur": ["fournisseur", "founisseur", "vendeur", "founisseur"],
    "employe": ["employe concerne", "employe", "ouvrier", "salarie", "personnel"],
    "quantite": ["quantite", "qte", "qty"],
    "prix_unitaire": ["prix unitaire", "pu", "prix"],
    "montant_total": ["montant total", "cout total", "total", "montant"],
    "mode_paiement": ["mode de paiement", "mode paiement", "moyen de paiement"],
    "statut_paiement": ["statut paiement", "statut", "status", "paye"],
    "observation": ["observation", "remarque", "commentaire", "note"],
}

# Ordre de priorité utilisé quand plusieurs champs canoniques pourraient matcher une même colonne
_FIELD_PRIORITY = list(CANONICAL_FIELDS.keys())


def _normalize(texte):
    """minuscule + suppression des accents, pour comparer les libellés de colonnes sans ambiguïté."""
    if texte is None:
        return ""
    texte = str(texte).strip().lower()
    texte = "".join(c for c in unicodedata.normalize("NFKD", texte) if not unicodedata.combining(c))
    return texte


def list_sheets(source):
    """Retourne la liste des feuilles d'un fichier Excel (chemin ou buffer uploadé)."""
    xls = pd.ExcelFile(source)
    return xls.sheet_names


def read_raw_sheet(source, sheet_name):
    """Lit une feuille sans supposer d'en-tête (pour pouvoir la détecter nous-mêmes)."""
    return pd.read_excel(source, sheet_name=sheet_name, header=None)


def detect_header_row(raw_df, min_matches=3, max_scan_rows=60):
    """Cherche, parmi les premières lignes de la feuille, celle qui ressemble le plus
    à un en-tête de tableau de dépenses (le plus de cellules reconnues comme un champ canonique)."""
    best_row, best_score = None, 0
    for i in range(min(max_scan_rows, len(raw_df))):
        row_values = [_normalize(v) for v in raw_df.iloc[i].tolist()]
        score = 0
        for v in row_values:
            if not v:
                continue
            if any(v == syn or syn in v for syns in CANONICAL_FIELDS.values() for syn in syns):
                score += 1
        if score > best_score:
            best_score, best_row = score, i
    if best_score >= min_matches:
        return best_row
    return None


def map_columns(header_values):
    """Associe chaque index de colonne à un champ canonique (au plus une colonne par champ)."""
    mapping = {}
    used_fields = set()
    normalized = [_normalize(v) for v in header_values]

    for field in _FIELD_PRIORITY:
        synonyms = CANONICAL_FIELDS[field]
        best_col, best_len = None, 0
        for col_idx, val in enumerate(normalized):
            if col_idx in mapping or not val:
                continue
            for syn in synonyms:
                if val == syn or syn in val:
                    if len(syn) > best_len:
                        best_col, best_len = col_idx, len(syn)
        if best_col is not None and field not in used_fields:
            mapping[best_col] = field
            used_fields.add(field)
    return mapping


def build_dataframe(raw_df, header_row, column_mapping):
    """Construit un DataFrame propre (colonnes canoniques) à partir des lignes situées
    sous la ligne d'en-tête détectée, en ignorant les lignes totalement vides."""
    data_rows = raw_df.iloc[header_row + 1:].reset_index(drop=True)
    columns = {col_idx: field for col_idx, field in column_mapping.items()}

    df = pd.DataFrame({field: data_rows[col_idx] for col_idx, field in columns.items()})

    # Une ligne est ignorée si elle n'a ni désignation, ni montant, ni catégorie exploitable
    critere_presence = [c for c in ("designation", "montant_total", "categorie") if c in df.columns]
    if critere_presence:
        df = df.dropna(how="all", subset=critere_presence)
    df = df.dropna(how="all")
    return df.reset_index(drop=True)


def _to_iso_date(valeur):
    if pd.isna(valeur) or valeur == "":
        return None
    if isinstance(valeur, pd.Timestamp):
        return valeur.date().isoformat()
    try:
        # Nombre de série Excel (jours depuis 1899-12-30)
        if isinstance(valeur, (int, float)):
            return (pd.Timestamp("1899-12-30") + pd.Timedelta(days=float(valeur))).date().isoformat()
    except (ValueError, OverflowError):
        pass
    parsed = pd.to_datetime(valeur, errors="coerce", dayfirst=True)
    return parsed.date().isoformat() if pd.notna(parsed) else None


def interpreter_statut(valeur):
    """Interprète la colonne 'Statut paiement' du fichier source, qui contient tantôt un
    statut (Payé/Non payé), tantôt le nom du canal / de la personne ayant réglé (ex: Bankily).

    Retourne un couple (statut_paiement, mode_paiement_detecte).
    """
    if valeur is None or (isinstance(valeur, float) and pd.isna(valeur)):
        return "Payé", ""
    texte = str(valeur).strip()
    if not texte:
        return "Payé", ""
    upper = texte.upper()
    if upper in ("P", "PAYE", "PAYÉ", "OUI", "YES"):
        return "Payé", ""
    if upper in ("NP", "NON PAYE", "NON PAYÉ", "NON", "NO"):
        return "Non payé", ""
    # Valeur libre (ex: "BANKILY", "DAHAN") : on la conserve comme mode de paiement,
    # et on considère la dépense réglée puisqu'un canal de paiement précis est renseigné.
    return "Payé", texte.title()


def _clean_num(valeur, default=0):
    if valeur is None or (isinstance(valeur, float) and pd.isna(valeur)):
        return default
    if isinstance(valeur, str):
        valeur = valeur.replace(" ", "").replace(",", ".")
        if valeur == "":
            return default
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return default


def _clean_text(valeur):
    if valeur is None or (isinstance(valeur, float) and pd.isna(valeur)):
        return ""
    return str(valeur).strip()


def importer_dataframe(df):
    """Insère les lignes d'un DataFrame déjà mappé (colonnes canoniques) dans la base.

    Crée automatiquement les étapes, fournisseurs et employés référencés mais absents
    de la base. Retourne un résumé (nombre de lignes importées / ignorées / entités créées).
    """
    etapes_existantes = {e["nom"]: e["id"] for e in db.get_etapes()}
    fournisseurs_crees, employes_crees, etapes_creees, categories_creees = set(), set(), set(), set()
    nb_importees, nb_ignorees = 0, 0

    for _, row in df.iterrows():
        montant_total = _clean_num(row.get("montant_total"))
        quantite = _clean_num(row.get("quantite"))
        prix_unitaire = _clean_num(row.get("prix_unitaire"))
        designation = _clean_text(row.get("designation"))
        categorie = _clean_text(row.get("categorie"))

        if montant_total == 0 and quantite and prix_unitaire:
            montant_total = quantite * prix_unitaire

        if montant_total == 0 and not designation and not categorie:
            nb_ignorees += 1
            continue

        # Catégorie
        categorie_id = None
        if categorie:
            avant = db.get_categorie_by_nom(categorie)
            categorie_id = db.get_or_create_categorie(categorie)
            if not avant:
                categories_creees.add(categorie)

        # Étape
        etape_id = None
        nom_etape = _clean_text(row.get("etape"))
        if nom_etape:
            if nom_etape not in etapes_existantes:
                etapes_existantes[nom_etape] = db.add_etape(nom_etape)
                etapes_creees.add(nom_etape)
            etape_id = etapes_existantes[nom_etape]

        # Fournisseur
        fournisseur_id = None
        nom_fournisseur = _clean_text(row.get("fournisseur"))
        if nom_fournisseur:
            avant = db.get_fournisseur_by_nom(nom_fournisseur)
            fournisseur_id = db.get_or_create_fournisseur(nom_fournisseur)
            if not avant:
                fournisseurs_crees.add(nom_fournisseur)

        # Employé : soit une colonne dédiée, soit (cas du fichier source) la désignation
        # de la ligne quand la catégorie vaut "Employé"
        employe_id = None
        nom_employe = _clean_text(row.get("employe"))
        if not nom_employe and _normalize(categorie).startswith("employ"):
            nom_employe = designation
        if nom_employe:
            avant = db.get_employe_by_nom(nom_employe)
            employe_id = db.get_or_create_employe(nom_employe)
            if not avant:
                employes_crees.add(nom_employe)

        statut_col = row.get("statut_paiement")
        mode_col = _clean_text(row.get("mode_paiement"))
        statut_paiement, mode_detecte = interpreter_statut(statut_col)
        mode_paiement = mode_col or mode_detecte

        date_iso = _to_iso_date(row.get("date")) or db._today()

        db.add_depense(
            date_depense=date_iso,
            designation=designation,
            categorie_id=categorie_id,
            etape_id=etape_id,
            fournisseur_id=fournisseur_id,
            employe_id=employe_id,
            quantite=quantite,
            prix_unitaire=prix_unitaire,
            montant_total=montant_total,
            mode_paiement=mode_paiement,
            statut_paiement=statut_paiement,
            observation=_clean_text(row.get("observation")),
        )
        nb_importees += 1

    # Pour les employés nouvellement créés lors de cet import, le fichier source ne contient
    # pas de "montant dû" (contrat) séparé : on initialise donc le montant dû au montant déjà
    # avancé, pour que le reste à payer parte de 0 plutôt que d'un solde négatif trompeur.
    # L'utilisateur peut ensuite ajuster ce montant dû librement sur la fiche de l'employé.
    for nom in employes_crees:
        employe = db.get_employe_by_nom(nom)
        totaux = db.get_totaux_employe(employe["id"])
        db.update_employe(employe["id"], employe["nom"], employe["fonction"], employe["telephone"],
                           montant_du=totaux["total_regle"])

    return {
        "nb_importees": nb_importees,
        "nb_ignorees": nb_ignorees,
        "etapes_creees": sorted(etapes_creees),
        "fournisseurs_crees": sorted(fournisseurs_crees),
        "employes_crees": sorted(employes_crees),
        "categories_creees": sorted(categories_creees),
    }


def importer_fichier(source, sheet_name=None):
    """Point d'entrée haut niveau : détecte l'en-tête + les colonnes puis importe.

    `source` peut être un chemin de fichier ou un objet fichier uploadé (Streamlit).
    Retourne (resume_dict, colonnes_mappees, df_apercu) ou lève ValueError si aucun
    tableau de dépenses n'a pu être détecté.
    """
    if sheet_name is None:
        sheet_name = list_sheets(source)[0]

    raw_df = read_raw_sheet(source, sheet_name)
    header_row = detect_header_row(raw_df)
    if header_row is None:
        raise ValueError(
            "Impossible de détecter automatiquement un tableau de dépenses dans cette feuille."
        )

    header_values = raw_df.iloc[header_row].tolist()
    mapping = map_columns(header_values)
    if "montant_total" not in mapping.values() and "prix_unitaire" not in mapping.values():
        raise ValueError("Aucune colonne de montant n'a pu être identifiée dans l'en-tête détecté.")

    df = build_dataframe(raw_df, header_row, mapping)
    resume = importer_dataframe(df)
    return resume, mapping, df
