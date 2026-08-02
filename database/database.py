"""
Couche d'accès aux données (SQLite) pour l'application Suivi de Chantier.

Toute la logique de lecture/écriture en base passe par ce module : il crée
automatiquement les tables nécessaires au premier lancement, expose des
fonctions CRUD simples pour chaque entité, ainsi que des fonctions de calcul
(agrégats) réutilisées par les différentes pages Streamlit.

Le fichier SQLite est stocké dans database/suivi_chantier.db, à côté de ce
module, pour que l'application fonctionne quel que soit le répertoire courant
depuis lequel elle est lancée.
"""

import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "suivi_chantier.db"


# ---------------------------------------------------------------------------
# Connexion
# ---------------------------------------------------------------------------

@contextmanager
def get_connection():
    """Fournit une connexion SQLite avec les lignes accessibles par nom de colonne."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Création du schéma
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS etapes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nom             TEXT NOT NULL UNIQUE,
    description     TEXT DEFAULT '',
    budget_alloue   REAL DEFAULT 0,
    ordre           INTEGER DEFAULT 0,
    date_creation   TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS categories (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    nom     TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS fournisseurs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nom             TEXT NOT NULL UNIQUE,
    telephone       TEXT DEFAULT '',
    adresse         TEXT DEFAULT '',
    type_materiaux  TEXT DEFAULT '',
    solde_initial   REAL DEFAULT 0,
    date_creation   TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS employes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nom             TEXT NOT NULL UNIQUE,
    fonction        TEXT DEFAULT '',
    telephone       TEXT DEFAULT '',
    montant_du      REAL DEFAULT 0,
    date_creation   TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS depenses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date            TEXT NOT NULL,
    designation     TEXT DEFAULT '',
    categorie_id    INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    etape_id        INTEGER REFERENCES etapes(id) ON DELETE SET NULL,
    fournisseur_id  INTEGER REFERENCES fournisseurs(id) ON DELETE SET NULL,
    employe_id      INTEGER REFERENCES employes(id) ON DELETE SET NULL,
    quantite        REAL DEFAULT 0,
    prix_unitaire   REAL DEFAULT 0,
    montant_total   REAL NOT NULL DEFAULT 0,
    mode_paiement   TEXT DEFAULT '',
    statut_paiement TEXT DEFAULT 'Payé',
    observation     TEXT DEFAULT '',
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS paiements_fournisseurs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fournisseur_id  INTEGER NOT NULL REFERENCES fournisseurs(id) ON DELETE CASCADE,
    date            TEXT NOT NULL,
    montant         REAL NOT NULL DEFAULT 0,
    mode_paiement   TEXT DEFAULT '',
    commentaire     TEXT DEFAULT '',
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS mouvements_employes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    employe_id      INTEGER NOT NULL REFERENCES employes(id) ON DELETE CASCADE,
    date            TEXT NOT NULL,
    type            TEXT NOT NULL CHECK(type IN ('avance', 'paiement')),
    montant         REAL NOT NULL DEFAULT 0,
    commentaire     TEXT DEFAULT '',
    depense_id      INTEGER REFERENCES depenses(id) ON DELETE CASCADE,
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS settings (
    key     TEXT PRIMARY KEY,
    value   TEXT
);
"""

# Séparés du schéma des tables : ces index portent sur `depenses.categorie_id`, qui
# n'existe pas encore sur une base créée avant la migration (voir `_migrer_categorie_vers_fk`).
# Ils sont donc créés APRÈS la migration, une fois la colonne garantie présente.
SCHEMA_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_depenses_etape       ON depenses(etape_id);
CREATE INDEX IF NOT EXISTS idx_depenses_fournisseur ON depenses(fournisseur_id);
CREATE INDEX IF NOT EXISTS idx_depenses_employe     ON depenses(employe_id);
CREATE INDEX IF NOT EXISTS idx_depenses_categorie   ON depenses(categorie_id);
CREATE INDEX IF NOT EXISTS idx_depenses_date        ON depenses(date);
CREATE INDEX IF NOT EXISTS idx_mouv_employe         ON mouvements_employes(employe_id);
CREATE INDEX IF NOT EXISTS idx_paiements_fourn      ON paiements_fournisseurs(fournisseur_id);
"""

DEFAULT_ETAPES = [
    ("Fondations", "Fondation", 1),
    ("Élévation", "Élévation (rez-de-chaussée)", 2),
    ("Lma96a", "Dalle supérieure (Lma96a)", 3),
    ("Elevation 1", "Élévation étage 1", 4),
    ("Finitions", "Finitions", 5),
    ("Autres", "Travaux divers", 6),
]

DEFAULT_CATEGORIES = ["Fer", "Ciment", "Brique", "Plomberie", "Électricité", "Employé", "Autres"]

DEFAULT_MODES_PAIEMENT = ["Espèces", "Bankily", "Sedad", "Masrvi", "Chèque", "Virement", "Autre"]


def init_db():
    """Crée les tables si nécessaire et insère les données de référence par défaut."""
    with get_connection() as conn:
        conn.executescript(SCHEMA)

        # Étapes par défaut (uniquement si la table est vide -> premier lancement)
        nb_etapes = conn.execute("SELECT COUNT(*) FROM etapes").fetchone()[0]
        if nb_etapes == 0:
            conn.executemany(
                "INSERT INTO etapes (nom, description, ordre) VALUES (?, ?, ?)",
                DEFAULT_ETAPES,
            )

        nb_categories = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
        if nb_categories == 0:
            conn.executemany(
                "INSERT INTO categories (nom) VALUES (?)",
                [(c,) for c in DEFAULT_CATEGORIES],
            )

        _migrer_categorie_vers_fk(conn)
        conn.executescript(SCHEMA_INDEXES)

        if conn.execute("SELECT value FROM settings WHERE key = 'budget_global'").fetchone() is None:
            conn.execute("INSERT INTO settings (key, value) VALUES ('budget_global', '0')")


def _migrer_categorie_vers_fk(conn):
    """Migration : l'ancienne colonne texte `depenses.categorie` devient `categorie_id`
    (clé étrangère vers `categories`), au même titre que `fournisseur_id`/`employe_id`.

    Idempotente : ne fait rien si la base a déjà le nouveau schéma (cas normal après
    la toute première exécution de cette migration, ou pour une base fraîchement créée
    où `categorie_id` existe déjà nativement dans le schéma).
    """
    colonnes = {row["name"] for row in conn.execute("PRAGMA table_info(depenses)").fetchall()}
    if "categorie" not in colonnes:
        return  # déjà migré (ou base neuve créée directement avec categorie_id)

    if "categorie_id" not in colonnes:
        conn.execute(
            "ALTER TABLE depenses ADD COLUMN categorie_id INTEGER REFERENCES categories(id) ON DELETE SET NULL"
        )

    for ligne in conn.execute("SELECT id, categorie FROM depenses").fetchall():
        nom = (ligne["categorie"] or "").strip()
        if not nom:
            continue
        cat = conn.execute("SELECT id FROM categories WHERE nom = ?", (nom,)).fetchone()
        cat_id = cat["id"] if cat else conn.execute(
            "INSERT INTO categories (nom) VALUES (?)", (nom,)
        ).lastrowid
        conn.execute("UPDATE depenses SET categorie_id = ? WHERE id = ?", (cat_id, ligne["id"]))

    conn.execute("ALTER TABLE depenses DROP COLUMN categorie")


# ---------------------------------------------------------------------------
# Helpers génériques
# ---------------------------------------------------------------------------

def _today():
    return date.today().isoformat()


def _rows_to_dicts(rows):
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# ÉTAPES
# ---------------------------------------------------------------------------

def get_etapes():
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM etapes ORDER BY ordre, id").fetchall()
        return _rows_to_dicts(rows)


def get_etape(etape_id):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM etapes WHERE id = ?", (etape_id,)).fetchone()
        return dict(row) if row else None


def add_etape(nom, description="", budget_alloue=0, ordre=None):
    with get_connection() as conn:
        if ordre is None:
            ordre = (conn.execute("SELECT COALESCE(MAX(ordre), 0) FROM etapes").fetchone()[0] or 0) + 1
        cur = conn.execute(
            "INSERT INTO etapes (nom, description, budget_alloue, ordre) VALUES (?, ?, ?, ?)",
            (nom, description, budget_alloue, ordre),
        )
        return cur.lastrowid


def update_etape(etape_id, nom, description="", budget_alloue=0, ordre=0):
    with get_connection() as conn:
        conn.execute(
            "UPDATE etapes SET nom=?, description=?, budget_alloue=?, ordre=? WHERE id=?",
            (nom, description, budget_alloue, ordre, etape_id),
        )


def delete_etape(etape_id):
    with get_connection() as conn:
        conn.execute("UPDATE depenses SET etape_id = NULL WHERE etape_id = ?", (etape_id,))
        conn.execute("DELETE FROM etapes WHERE id = ?", (etape_id,))


def get_couts_par_etape():
    """Retourne, pour chaque étape, le coût total des dépenses liées et le % du budget consommé."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT e.id, e.nom, e.description, e.budget_alloue,
                   COALESCE(SUM(d.montant_total), 0) AS cout_total,
                   COUNT(d.id) AS nb_depenses
            FROM etapes e
            LEFT JOIN depenses d ON d.etape_id = e.id
            GROUP BY e.id
            ORDER BY e.ordre, e.id
            """
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            budget = d["budget_alloue"] or 0
            d["pct_budget"] = round((d["cout_total"] / budget) * 100, 1) if budget > 0 else None
            result.append(d)
        return result


# ---------------------------------------------------------------------------
# CATÉGORIES
# ---------------------------------------------------------------------------

def get_categories():
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM categories ORDER BY nom").fetchall()
        return _rows_to_dicts(rows)


def get_categorie_by_nom(nom):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM categories WHERE nom = ?", (nom,)).fetchone()
        return dict(row) if row else None


def add_categorie(nom):
    with get_connection() as conn:
        cur = conn.execute("INSERT OR IGNORE INTO categories (nom) VALUES (?)", (nom,))
        if cur.lastrowid and cur.rowcount:
            return cur.lastrowid
        row = conn.execute("SELECT id FROM categories WHERE nom = ?", (nom,)).fetchone()
        return row["id"] if row else None


def get_or_create_categorie(nom):
    """Retourne l'id de la catégorie `nom`, en la créant si besoin (mêmes pattern
    que `get_or_create_fournisseur`/`get_or_create_employe`)."""
    nom = (nom or "").strip()
    if not nom:
        return None
    existing = get_categorie_by_nom(nom)
    if existing:
        return existing["id"]
    return add_categorie(nom)


def update_categorie(categorie_id, nom):
    """Renomme une catégorie : la relation par clé étrangère propage automatiquement
    ce renommage à toutes les dépenses déjà liées, sans risque de désynchronisation."""
    with get_connection() as conn:
        conn.execute("UPDATE categories SET nom = ? WHERE id = ?", (nom, categorie_id))


def delete_categorie(categorie_id):
    with get_connection() as conn:
        conn.execute("UPDATE depenses SET categorie_id = NULL WHERE categorie_id = ?", (categorie_id,))
        conn.execute("DELETE FROM categories WHERE id = ?", (categorie_id,))


def get_totaux_categories():
    """Retourne, pour chaque catégorie, le nombre de dépenses liées et le montant total dépensé."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT c.id, c.nom,
                   COUNT(d.id) AS nb_depenses,
                   COALESCE(SUM(d.montant_total), 0) AS montant_total
            FROM categories c
            LEFT JOIN depenses d ON d.categorie_id = c.id
            GROUP BY c.id
            ORDER BY c.nom
            """
        ).fetchall()
        return _rows_to_dicts(rows)


# ---------------------------------------------------------------------------
# FOURNISSEURS
# ---------------------------------------------------------------------------

def get_fournisseurs():
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM fournisseurs ORDER BY nom").fetchall()
        return _rows_to_dicts(rows)


def get_fournisseur(fournisseur_id):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM fournisseurs WHERE id = ?", (fournisseur_id,)).fetchone()
        return dict(row) if row else None


def get_fournisseur_by_nom(nom):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM fournisseurs WHERE nom = ?", (nom,)).fetchone()
        return dict(row) if row else None


def add_fournisseur(nom, telephone="", adresse="", type_materiaux="", solde_initial=0):
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO fournisseurs (nom, telephone, adresse, type_materiaux, solde_initial)
               VALUES (?, ?, ?, ?, ?)""",
            (nom, telephone, adresse, type_materiaux, solde_initial),
        )
        return cur.lastrowid


def get_or_create_fournisseur(nom):
    """Retourne l'id du fournisseur `nom`, en le créant s'il n'existe pas encore (utile à l'import)."""
    nom = (nom or "").strip()
    if not nom:
        return None
    existing = get_fournisseur_by_nom(nom)
    if existing:
        return existing["id"]
    return add_fournisseur(nom)


def update_fournisseur(fournisseur_id, nom, telephone="", adresse="", type_materiaux="", solde_initial=0):
    with get_connection() as conn:
        conn.execute(
            """UPDATE fournisseurs SET nom=?, telephone=?, adresse=?, type_materiaux=?, solde_initial=?
               WHERE id=?""",
            (nom, telephone, adresse, type_materiaux, solde_initial, fournisseur_id),
        )


def delete_fournisseur(fournisseur_id):
    with get_connection() as conn:
        conn.execute("UPDATE depenses SET fournisseur_id = NULL WHERE fournisseur_id = ?", (fournisseur_id,))
        conn.execute("DELETE FROM fournisseurs WHERE id = ?", (fournisseur_id,))


def add_paiement_fournisseur(fournisseur_id, montant, date_paiement=None, mode_paiement="", commentaire=""):
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO paiements_fournisseurs (fournisseur_id, date, montant, mode_paiement, commentaire)
               VALUES (?, ?, ?, ?, ?)""",
            (fournisseur_id, date_paiement or _today(), montant, mode_paiement, commentaire),
        )


def get_paiements_fournisseur(fournisseur_id):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM paiements_fournisseurs WHERE fournisseur_id = ? ORDER BY date DESC, id DESC",
            (fournisseur_id,),
        ).fetchall()
        return _rows_to_dicts(rows)


def get_achats_fournisseur(fournisseur_id):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM depenses WHERE fournisseur_id = ? ORDER BY date DESC, id DESC",
            (fournisseur_id,),
        ).fetchall()
        return _rows_to_dicts(rows)


def get_dettes_fournisseurs():
    """Calcule, pour chaque fournisseur : total achats, total payé et dette restante.

    Dette restante = solde_initial + total des achats (dépenses) - total des paiements enregistrés.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT f.id, f.nom, f.telephone, f.adresse, f.type_materiaux, f.solde_initial,
                   COALESCE((SELECT SUM(d.montant_total) FROM depenses d WHERE d.fournisseur_id = f.id), 0) AS total_achats,
                   COALESCE((SELECT SUM(p.montant) FROM paiements_fournisseurs p WHERE p.fournisseur_id = f.id), 0) AS total_paye
            FROM fournisseurs f
            ORDER BY f.nom
            """
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["dette_restante"] = round(d["solde_initial"] + d["total_achats"] - d["total_paye"], 2)
            result.append(d)
        return result


# ---------------------------------------------------------------------------
# EMPLOYÉS
# ---------------------------------------------------------------------------

def get_employes():
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM employes ORDER BY nom").fetchall()
        return _rows_to_dicts(rows)


def get_employe(employe_id):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM employes WHERE id = ?", (employe_id,)).fetchone()
        return dict(row) if row else None


def get_employe_by_nom(nom):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM employes WHERE nom = ?", (nom,)).fetchone()
        return dict(row) if row else None


def add_employe(nom, fonction="", telephone="", montant_du=0):
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO employes (nom, fonction, telephone, montant_du) VALUES (?, ?, ?, ?)",
            (nom, fonction, telephone, montant_du),
        )
        return cur.lastrowid


def get_or_create_employe(nom, fonction=""):
    nom = (nom or "").strip()
    if not nom:
        return None
    existing = get_employe_by_nom(nom)
    if existing:
        return existing["id"]
    return add_employe(nom, fonction=fonction)


def update_employe(employe_id, nom, fonction="", telephone="", montant_du=0):
    with get_connection() as conn:
        conn.execute(
            "UPDATE employes SET nom=?, fonction=?, telephone=?, montant_du=? WHERE id=?",
            (nom, fonction, telephone, montant_du, employe_id),
        )


def delete_employe(employe_id):
    with get_connection() as conn:
        conn.execute("UPDATE depenses SET employe_id = NULL WHERE employe_id = ?", (employe_id,))
        conn.execute("DELETE FROM employes WHERE id = ?", (employe_id,))


def add_mouvement_employe(employe_id, type_mouvement, montant, date_mouvement=None, commentaire="", depense_id=None):
    """Enregistre une avance ou un paiement complémentaire pour un employé."""
    assert type_mouvement in ("avance", "paiement")
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO mouvements_employes (employe_id, date, type, montant, commentaire, depense_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (employe_id, date_mouvement or _today(), type_mouvement, montant, commentaire, depense_id),
        )


def get_mouvements_employe(employe_id):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM mouvements_employes WHERE employe_id = ? ORDER BY date DESC, id DESC",
            (employe_id,),
        ).fetchall()
        return _rows_to_dicts(rows)


def get_totaux_employes():
    """Calcule pour chaque employé : total dû, total avancé, total payé, reste à payer."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT e.id, e.nom, e.fonction, e.telephone, e.montant_du,
                   COALESCE((SELECT SUM(m.montant) FROM mouvements_employes m
                             WHERE m.employe_id = e.id AND m.type = 'avance'), 0) AS total_avance,
                   COALESCE((SELECT SUM(m.montant) FROM mouvements_employes m
                             WHERE m.employe_id = e.id AND m.type = 'paiement'), 0) AS total_paye
            FROM employes e
            ORDER BY e.nom
            """
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["total_regle"] = round(d["total_avance"] + d["total_paye"], 2)
            d["reste_a_payer"] = round(d["montant_du"] - d["total_regle"], 2)
            result.append(d)
        return result


def get_totaux_employe(employe_id):
    totaux = get_totaux_employes()
    for t in totaux:
        if t["id"] == employe_id:
            return t
    return None


# ---------------------------------------------------------------------------
# DÉPENSES
# ---------------------------------------------------------------------------

DEPENSE_SELECT = """
    SELECT d.*, e.nom AS etape_nom, f.nom AS fournisseur_nom, emp.nom AS employe_nom, c.nom AS categorie_nom
    FROM depenses d
    LEFT JOIN etapes e ON e.id = d.etape_id
    LEFT JOIN fournisseurs f ON f.id = d.fournisseur_id
    LEFT JOIN employes emp ON emp.id = d.employe_id
    LEFT JOIN categories c ON c.id = d.categorie_id
"""


def get_depenses():
    with get_connection() as conn:
        rows = conn.execute(DEPENSE_SELECT + " ORDER BY d.date DESC, d.id DESC").fetchall()
        return _rows_to_dicts(rows)


def get_depense(depense_id):
    with get_connection() as conn:
        row = conn.execute(DEPENSE_SELECT + " WHERE d.id = ?", (depense_id,)).fetchone()
        return dict(row) if row else None


def add_depense(date_depense, designation, categorie_id, etape_id, fournisseur_id, employe_id,
                 quantite, prix_unitaire, montant_total, mode_paiement, statut_paiement, observation):
    """Ajoute une dépense et déclenche automatiquement le mouvement d'employé associé
    si la dépense concerne un employé (catégorie 'Employé' + employé renseigné)."""
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO depenses
               (date, designation, categorie_id, etape_id, fournisseur_id, employe_id,
                quantite, prix_unitaire, montant_total, mode_paiement, statut_paiement, observation)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (date_depense, designation, categorie_id, etape_id, fournisseur_id, employe_id,
             quantite, prix_unitaire, montant_total, mode_paiement, statut_paiement, observation),
        )
        depense_id = cur.lastrowid

        if employe_id:
            conn.execute(
                """INSERT INTO mouvements_employes (employe_id, date, type, montant, commentaire, depense_id)
                   VALUES (?, ?, 'avance', ?, ?, ?)""",
                (employe_id, date_depense, montant_total, f"Dépense: {designation}".strip(": "), depense_id),
            )
        return depense_id


def update_depense(depense_id, date_depense, designation, categorie_id, etape_id, fournisseur_id, employe_id,
                    quantite, prix_unitaire, montant_total, mode_paiement, statut_paiement, observation):
    with get_connection() as conn:
        conn.execute(
            """UPDATE depenses SET
                date=?, designation=?, categorie_id=?, etape_id=?, fournisseur_id=?, employe_id=?,
                quantite=?, prix_unitaire=?, montant_total=?, mode_paiement=?, statut_paiement=?, observation=?
               WHERE id=?""",
            (date_depense, designation, categorie_id, etape_id, fournisseur_id, employe_id,
             quantite, prix_unitaire, montant_total, mode_paiement, statut_paiement, observation, depense_id),
        )
        # Le mouvement employé lié est resynchronisé (montant/date/employé peuvent avoir changé)
        conn.execute("DELETE FROM mouvements_employes WHERE depense_id = ?", (depense_id,))
        if employe_id:
            conn.execute(
                """INSERT INTO mouvements_employes (employe_id, date, type, montant, commentaire, depense_id)
                   VALUES (?, ?, 'avance', ?, ?, ?)""",
                (employe_id, date_depense, montant_total, f"Dépense: {designation}".strip(": "), depense_id),
            )


def delete_depense(depense_id):
    with get_connection() as conn:
        conn.execute("DELETE FROM depenses WHERE id = ?", (depense_id,))


# ---------------------------------------------------------------------------
# INDICATEURS GLOBAUX (tableau de bord)
# ---------------------------------------------------------------------------

def get_indicateurs_globaux():
    with get_connection() as conn:
        total_depenses = conn.execute("SELECT COALESCE(SUM(montant_total), 0) FROM depenses").fetchone()[0]
        nb_depenses = conn.execute("SELECT COUNT(*) FROM depenses").fetchone()[0]
        nb_fournisseurs = conn.execute("SELECT COUNT(*) FROM fournisseurs").fetchone()[0]
        nb_employes = conn.execute("SELECT COUNT(*) FROM employes").fetchone()[0]
        budget_row = conn.execute("SELECT value FROM settings WHERE key = 'budget_global'").fetchone()
        budget_global = float(budget_row[0]) if budget_row and budget_row[0] else 0

    dettes = get_dettes_fournisseurs()
    total_dettes = round(sum(d["dette_restante"] for d in dettes), 2)
    total_achats_fournisseurs = round(sum(d["total_achats"] for d in dettes), 2)
    total_paye_fournisseurs = round(sum(d["total_paye"] for d in dettes), 2)

    return {
        "total_depenses": total_depenses,
        "budget_global": budget_global,
        "budget_restant": (budget_global - total_depenses) if budget_global else None,
        "nb_fournisseurs": nb_fournisseurs,
        "nb_employes": nb_employes,
        "nb_depenses": nb_depenses,
        "total_dettes_fournisseurs": total_dettes,
        "total_achats_fournisseurs": total_achats_fournisseurs,
        "total_paye_fournisseurs": total_paye_fournisseurs,
        "montant_restant_a_payer": total_dettes,
    }


def get_budget_global():
    with get_connection() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = 'budget_global'").fetchone()
        return float(row[0]) if row and row[0] else 0.0


def set_budget_global(montant):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES ('budget_global', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (str(montant),),
        )


# ---------------------------------------------------------------------------
# HISTORIQUE DES PAIEMENTS (fournisseurs + employés confondus)
# ---------------------------------------------------------------------------

def get_historique_paiements():
    """Retourne la liste unifiée de tous les paiements (fournisseurs et employés)."""
    with get_connection() as conn:
        rows_f = conn.execute(
            """
            SELECT p.id, p.date, p.montant, f.nom AS beneficiaire, 'Fournisseur' AS type,
                   p.mode_paiement, p.commentaire
            FROM paiements_fournisseurs p
            JOIN fournisseurs f ON f.id = p.fournisseur_id
            """
        ).fetchall()
        rows_e = conn.execute(
            """
            SELECT m.id, m.date, m.montant, e.nom AS beneficiaire,
                   ('Employé - ' || CASE m.type WHEN 'avance' THEN 'Avance' ELSE 'Paiement' END) AS type,
                   '' AS mode_paiement, m.commentaire
            FROM mouvements_employes m
            JOIN employes e ON e.id = m.employe_id
            """
        ).fetchall()

    historique = _rows_to_dicts(rows_f) + _rows_to_dicts(rows_e)
    historique.sort(key=lambda x: (x["date"] or "", x["id"]), reverse=True)
    return historique
