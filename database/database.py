"""
Couche d'accès aux données (SQLite) pour l'application Suivi de Chantier.

Toute la logique de lecture/écriture en base passe par ce module : il crée
automatiquement les tables nécessaires au premier lancement, expose des
fonctions CRUD simples pour chaque entité, ainsi que des fonctions de calcul
(agrégats) réutilisées par les différentes pages Streamlit.

L'application gère plusieurs chantiers en parallèle (table `chantiers`) :
étapes, catégories, fournisseurs, employés et dépenses appartiennent chacun
à exactement un chantier (cloisonnement total, pas de partage entre
chantiers). Les fonctions qui listent/agrègent un ensemble d'entités prennent
donc un paramètre `chantier_id` ; celles qui opèrent sur un id déjà connu
(`get_etape(id)`, `update_fournisseur(id, ...)`, etc.) n'en ont pas besoin,
cet id appartenant déjà à un seul chantier.

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
CREATE TABLE IF NOT EXISTS chantiers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nom             TEXT NOT NULL UNIQUE,
    adresse         TEXT DEFAULT '',
    description     TEXT DEFAULT '',
    statut          TEXT DEFAULT 'En cours',
    date_creation   TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS etapes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    chantier_id     INTEGER NOT NULL REFERENCES chantiers(id) ON DELETE CASCADE,
    nom             TEXT NOT NULL,
    description     TEXT DEFAULT '',
    budget_alloue   REAL DEFAULT 0,
    ordre           INTEGER DEFAULT 0,
    date_creation   TEXT DEFAULT (datetime('now')),
    UNIQUE(chantier_id, nom)
);

CREATE TABLE IF NOT EXISTS categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    chantier_id INTEGER NOT NULL REFERENCES chantiers(id) ON DELETE CASCADE,
    nom         TEXT NOT NULL,
    UNIQUE(chantier_id, nom)
);

CREATE TABLE IF NOT EXISTS fournisseurs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    chantier_id     INTEGER NOT NULL REFERENCES chantiers(id) ON DELETE CASCADE,
    nom             TEXT NOT NULL,
    telephone       TEXT DEFAULT '',
    adresse         TEXT DEFAULT '',
    type_materiaux  TEXT DEFAULT '',
    solde_initial   REAL DEFAULT 0,
    date_creation   TEXT DEFAULT (datetime('now')),
    UNIQUE(chantier_id, nom)
);

CREATE TABLE IF NOT EXISTS employes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    chantier_id     INTEGER NOT NULL REFERENCES chantiers(id) ON DELETE CASCADE,
    nom             TEXT NOT NULL,
    fonction        TEXT DEFAULT '',
    telephone       TEXT DEFAULT '',
    montant_du      REAL DEFAULT 0,
    date_creation   TEXT DEFAULT (datetime('now')),
    UNIQUE(chantier_id, nom)
);

CREATE TABLE IF NOT EXISTS depenses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    chantier_id     INTEGER NOT NULL REFERENCES chantiers(id) ON DELETE CASCADE,
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
    justificatif_path TEXT DEFAULT '',
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

-- Une ligne = un réglage pour un chantier donné (ex. budget_global). Le
-- budget "global" est en réalité un budget par chantier.
CREATE TABLE IF NOT EXISTS settings (
    chantier_id INTEGER NOT NULL REFERENCES chantiers(id) ON DELETE CASCADE,
    key         TEXT NOT NULL,
    value       TEXT,
    PRIMARY KEY (chantier_id, key)
);

-- Abonnements aux notifications push navigateur (Web Push). Architecture
-- prête pour de futures notifications serveur (budget dépassé, rappel...) —
-- non activée : voir utils/notifications.py pour ce qu'il reste à câbler
-- (clé VAPID, envoi via pywebpush, déclencheur planifié). Pas lié à un
-- chantier : un abonnement est propre au navigateur/appareil.
CREATE TABLE IF NOT EXISTS push_subscriptions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    endpoint        TEXT NOT NULL UNIQUE,
    p256dh          TEXT NOT NULL,
    auth            TEXT NOT NULL,
    created_at      TEXT DEFAULT (datetime('now'))
);
"""

# Séparés du schéma des tables : ces index portent sur des colonnes qui
# n'existent pas encore sur une base créée avant les migrations correspondantes
# (`categorie_id` avant `_migrer_categorie_vers_fk`, `chantier_id` avant
# `_migrer_vers_multi_chantier`). Ils sont donc créés APRÈS les migrations,
# une fois ces colonnes garanties présentes.
SCHEMA_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_depenses_etape       ON depenses(etape_id);
CREATE INDEX IF NOT EXISTS idx_depenses_fournisseur ON depenses(fournisseur_id);
CREATE INDEX IF NOT EXISTS idx_depenses_employe     ON depenses(employe_id);
CREATE INDEX IF NOT EXISTS idx_depenses_categorie   ON depenses(categorie_id);
CREATE INDEX IF NOT EXISTS idx_depenses_date        ON depenses(date);
CREATE INDEX IF NOT EXISTS idx_depenses_chantier    ON depenses(chantier_id);
CREATE INDEX IF NOT EXISTS idx_mouv_employe         ON mouvements_employes(employe_id);
CREATE INDEX IF NOT EXISTS idx_paiements_fourn      ON paiements_fournisseurs(fournisseur_id);
CREATE INDEX IF NOT EXISTS idx_etapes_chantier      ON etapes(chantier_id);
CREATE INDEX IF NOT EXISTS idx_categories_chantier  ON categories(chantier_id);
CREATE INDEX IF NOT EXISTS idx_fournisseurs_chantier ON fournisseurs(chantier_id);
CREATE INDEX IF NOT EXISTS idx_employes_chantier    ON employes(chantier_id);
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


def init_db():
    """Crée les tables si nécessaire et insère les données de référence par défaut."""
    with get_connection() as conn:
        conn.executescript(SCHEMA)

        _migrer_categorie_vers_fk(conn)
        _migrer_justificatif_path(conn)
        _migrer_depense_employe_vers_paiement(conn)
        _migrer_vers_multi_chantier(conn)

        # Premier lancement (aucun chantier existant) : crée un chantier par défaut
        nb_chantiers = conn.execute("SELECT COUNT(*) FROM chantiers").fetchone()[0]
        if nb_chantiers == 0:
            chantier_id = conn.execute(
                "INSERT INTO chantiers (nom) VALUES (?)", ("Chantier 1",)
            ).lastrowid
            _seed_chantier_defaults(conn, chantier_id)

        conn.executescript(SCHEMA_INDEXES)


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


def _migrer_justificatif_path(conn):
    """Migration : ajoute `depenses.justificatif_path` (photo/scan de
    justificatif pris depuis le mobile) sur une base créée avant cette
    fonctionnalité. Idempotente."""
    colonnes = {row["name"] for row in conn.execute("PRAGMA table_info(depenses)").fetchall()}
    if "justificatif_path" not in colonnes:
        conn.execute("ALTER TABLE depenses ADD COLUMN justificatif_path TEXT DEFAULT ''")


def _migrer_depense_employe_vers_paiement(conn):
    """Migration : les mouvements générés automatiquement par une dépense
    (`depense_id` non nul) étaient historiquement enregistrés comme 'avance'.
    Une dépense représente un décaissement déjà effectué, pas une avance
    donnée par anticipation : elle doit compter dans le "Total payé" de
    l'employé, pas dans son "Total avancé". Corrige rétroactivement les
    mouvements existants. Idempotente (ne trouve plus rien à corriger une
    fois appliquée)."""
    conn.execute(
        "UPDATE mouvements_employes SET type = 'paiement' WHERE depense_id IS NOT NULL AND type = 'avance'"
    )


def _migrer_vers_multi_chantier(conn):
    """Migration : introduit la notion de "chantier" pour gérer plusieurs
    chantiers en parallèle. Avant cette migration, toutes les données
    (étapes, catégories, fournisseurs, employés, dépenses, réglages) étaient
    globales, comme s'il n'existait qu'un seul chantier implicite.

    Rattache toutes les données existantes à un premier chantier
    "Chantier 1", et élargit les contraintes d'unicité (nom d'étape/
    catégorie/fournisseur/employé) pour qu'elles ne s'appliquent plus que par
    chantier (ex. deux chantiers peuvent chacun avoir une étape "Fondations").

    SQLite ne permet pas d'ajouter une contrainte UNIQUE composite via
    ALTER TABLE : chaque table concernée est recréée avec le nouveau schéma,
    puis ses lignes sont recopiées (même `id`, pour ne pas casser les clés
    étrangères des dépenses).

    Piège vérifié empiriquement (pas une supposition) : sur SQLite, `DROP
    TABLE parent` déclenche les actions `ON DELETE CASCADE`/`SET NULL` de
    TOUTE table encore vivante référençant `parent` par son nom — y compris
    une table de remplacement fraîchement créée si sa FK cite encore ce nom.
    `ALTER TABLE ... RENAME`, à l'inverse, ne déclenche aucune action et met
    à jour tout seul le texte des FK des autres tables pour suivre le nouveau
    nom. La séquence ci-dessous exploite ceci : toutes les tables `_new` sont
    d'abord créées et peuplées en pointant leurs FK les unes vers les autres
    (`_new` vers `_new`, jamais vers un nom final déjà utilisé par une table
    encore vivante) ; les anciennes tables sont ensuite supprimées (plus rien
    ne les référence) ; enfin chaque `_new` est renommée vers son nom final,
    ce qui met à jour en cascade (sans perte de données, juste du texte SQL)
    les FK des autres tables `_new` qui la citaient.

    Idempotente : ne fait rien si `etapes` a déjà `chantier_id` (cas normal
    après la toute première exécution, ou pour une base neuve créée
    directement avec le nouveau schéma — `chantiers` est alors déjà créée par
    `SCHEMA` et cette fonction n'a rien à recopier)."""
    colonnes_etapes = {row["name"] for row in conn.execute("PRAGMA table_info(etapes)").fetchall()}
    if "chantier_id" in colonnes_etapes:
        return  # déjà migré (ou base neuve créée directement avec le nouveau schéma)

    conn.execute("PRAGMA foreign_keys = OFF")

    chantier_id = conn.execute("INSERT INTO chantiers (nom) VALUES (?)", ("Chantier 1",)).lastrowid

    conn.execute(
        """CREATE TABLE etapes_new (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            chantier_id     INTEGER NOT NULL REFERENCES chantiers(id) ON DELETE CASCADE,
            nom             TEXT NOT NULL,
            description     TEXT DEFAULT '',
            budget_alloue   REAL DEFAULT 0,
            ordre           INTEGER DEFAULT 0,
            date_creation   TEXT DEFAULT (datetime('now')),
            UNIQUE(chantier_id, nom)
        )"""
    )
    conn.execute(
        """INSERT INTO etapes_new (id, chantier_id, nom, description, budget_alloue, ordre, date_creation)
           SELECT id, ?, nom, description, budget_alloue, ordre, date_creation FROM etapes""",
        (chantier_id,),
    )

    conn.execute(
        """CREATE TABLE categories_new (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            chantier_id INTEGER NOT NULL REFERENCES chantiers(id) ON DELETE CASCADE,
            nom         TEXT NOT NULL,
            UNIQUE(chantier_id, nom)
        )"""
    )
    conn.execute(
        "INSERT INTO categories_new (id, chantier_id, nom) SELECT id, ?, nom FROM categories",
        (chantier_id,),
    )

    conn.execute(
        """CREATE TABLE fournisseurs_new (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            chantier_id     INTEGER NOT NULL REFERENCES chantiers(id) ON DELETE CASCADE,
            nom             TEXT NOT NULL,
            telephone       TEXT DEFAULT '',
            adresse         TEXT DEFAULT '',
            type_materiaux  TEXT DEFAULT '',
            solde_initial   REAL DEFAULT 0,
            date_creation   TEXT DEFAULT (datetime('now')),
            UNIQUE(chantier_id, nom)
        )"""
    )
    conn.execute(
        """INSERT INTO fournisseurs_new (id, chantier_id, nom, telephone, adresse, type_materiaux,
                                           solde_initial, date_creation)
           SELECT id, ?, nom, telephone, adresse, type_materiaux, solde_initial, date_creation
           FROM fournisseurs""",
        (chantier_id,),
    )

    conn.execute(
        """CREATE TABLE employes_new (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            chantier_id     INTEGER NOT NULL REFERENCES chantiers(id) ON DELETE CASCADE,
            nom             TEXT NOT NULL,
            fonction        TEXT DEFAULT '',
            telephone       TEXT DEFAULT '',
            montant_du      REAL DEFAULT 0,
            date_creation   TEXT DEFAULT (datetime('now')),
            UNIQUE(chantier_id, nom)
        )"""
    )
    conn.execute(
        """INSERT INTO employes_new (id, chantier_id, nom, fonction, telephone, montant_du, date_creation)
           SELECT id, ?, nom, fonction, telephone, montant_du, date_creation FROM employes""",
        (chantier_id,),
    )

    conn.execute(
        """CREATE TABLE depenses_new (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            chantier_id     INTEGER NOT NULL REFERENCES chantiers(id) ON DELETE CASCADE,
            date            TEXT NOT NULL,
            designation     TEXT DEFAULT '',
            categorie_id    INTEGER REFERENCES categories_new(id) ON DELETE SET NULL,
            etape_id        INTEGER REFERENCES etapes_new(id) ON DELETE SET NULL,
            fournisseur_id  INTEGER REFERENCES fournisseurs_new(id) ON DELETE SET NULL,
            employe_id      INTEGER REFERENCES employes_new(id) ON DELETE SET NULL,
            quantite        REAL DEFAULT 0,
            prix_unitaire   REAL DEFAULT 0,
            montant_total   REAL NOT NULL DEFAULT 0,
            mode_paiement   TEXT DEFAULT '',
            statut_paiement TEXT DEFAULT 'Payé',
            observation     TEXT DEFAULT '',
            justificatif_path TEXT DEFAULT '',
            created_at      TEXT DEFAULT (datetime('now'))
        )"""
    )
    conn.execute(
        """INSERT INTO depenses_new (id, chantier_id, date, designation, categorie_id, etape_id,
                                       fournisseur_id, employe_id, quantite, prix_unitaire, montant_total,
                                       mode_paiement, statut_paiement, observation, justificatif_path, created_at)
           SELECT id, ?, date, designation, categorie_id, etape_id, fournisseur_id, employe_id,
                  quantite, prix_unitaire, montant_total, mode_paiement, statut_paiement, observation,
                  justificatif_path, created_at
           FROM depenses""",
        (chantier_id,),
    )

    conn.execute(
        """CREATE TABLE settings_new (
            chantier_id INTEGER NOT NULL REFERENCES chantiers(id) ON DELETE CASCADE,
            key         TEXT NOT NULL,
            value       TEXT,
            PRIMARY KEY (chantier_id, key)
        )"""
    )
    conn.execute(
        "INSERT INTO settings_new (chantier_id, key, value) SELECT ?, key, value FROM settings",
        (chantier_id,),
    )

    # `mouvements_employes`/`paiements_fournisseurs` ne changent pas de forme,
    # mais doivent quand même être recréées : leurs FK actuelles citent
    # `employes`/`depenses`/`fournisseurs` par leur nom d'origine, qui vont
    # être supprimés juste après (cf. piège documenté en tête de fonction).
    conn.execute(
        """CREATE TABLE mouvements_employes_new (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            employe_id      INTEGER NOT NULL REFERENCES employes_new(id) ON DELETE CASCADE,
            date            TEXT NOT NULL,
            type            TEXT NOT NULL CHECK(type IN ('avance', 'paiement')),
            montant         REAL NOT NULL DEFAULT 0,
            commentaire     TEXT DEFAULT '',
            depense_id      INTEGER REFERENCES depenses_new(id) ON DELETE CASCADE,
            created_at      TEXT DEFAULT (datetime('now'))
        )"""
    )
    conn.execute(
        """INSERT INTO mouvements_employes_new (id, employe_id, date, type, montant, commentaire,
                                                   depense_id, created_at)
           SELECT id, employe_id, date, type, montant, commentaire, depense_id, created_at
           FROM mouvements_employes"""
    )

    conn.execute(
        """CREATE TABLE paiements_fournisseurs_new (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            fournisseur_id  INTEGER NOT NULL REFERENCES fournisseurs_new(id) ON DELETE CASCADE,
            date            TEXT NOT NULL,
            montant         REAL NOT NULL DEFAULT 0,
            mode_paiement   TEXT DEFAULT '',
            commentaire     TEXT DEFAULT '',
            created_at      TEXT DEFAULT (datetime('now'))
        )"""
    )
    conn.execute(
        """INSERT INTO paiements_fournisseurs_new (id, fournisseur_id, date, montant, mode_paiement,
                                                      commentaire, created_at)
           SELECT id, fournisseur_id, date, montant, mode_paiement, commentaire, created_at
           FROM paiements_fournisseurs"""
    )

    # Plus rien ne référence les anciennes tables par leur nom `_new` : on
    # peut les supprimer sans qu'aucune action ON DELETE ne se déclenche
    # contre les tables `_new` (elles, pointent toutes vers d'autres `_new`).
    for table in (
        "mouvements_employes", "paiements_fournisseurs", "depenses",
        "etapes", "categories", "fournisseurs", "employes", "settings",
    ):
        conn.execute(f"DROP TABLE {table}")

    # Renommage final : parents avant enfants, pour que le texte des FK des
    # tables `_new` pas encore renommées (qui citent encore les noms `_new`
    # des tables déjà renommées) soit automatiquement mis à jour au passage.
    for table in (
        "etapes", "categories", "fournisseurs", "employes", "depenses",
        "settings", "mouvements_employes", "paiements_fournisseurs",
    ):
        conn.execute(f"ALTER TABLE {table}_new RENAME TO {table}")

    conn.execute("PRAGMA foreign_keys = ON")


def _seed_chantier_defaults(conn, chantier_id):
    """Initialise un chantier (nouveau ou tout premier lancement) avec les
    étapes et catégories par défaut."""
    conn.executemany(
        "INSERT INTO etapes (chantier_id, nom, description, ordre) VALUES (?, ?, ?, ?)",
        [(chantier_id, nom, description, ordre) for nom, description, ordre in DEFAULT_ETAPES],
    )
    conn.executemany(
        "INSERT INTO categories (chantier_id, nom) VALUES (?, ?)",
        [(chantier_id, c) for c in DEFAULT_CATEGORIES],
    )


# ---------------------------------------------------------------------------
# Helpers génériques
# ---------------------------------------------------------------------------

def _today():
    return date.today().isoformat()


def _rows_to_dicts(rows):
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# CHANTIERS
# ---------------------------------------------------------------------------

def get_chantiers():
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM chantiers ORDER BY id").fetchall()
        return _rows_to_dicts(rows)


def get_chantier(chantier_id):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM chantiers WHERE id = ?", (chantier_id,)).fetchone()
        return dict(row) if row else None


def add_chantier(nom, adresse="", description="", statut="En cours"):
    """Crée un nouveau chantier et l'initialise avec les étapes/catégories
    par défaut (même logique que le tout premier chantier créé au premier
    lancement de l'application, voir `init_db`)."""
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO chantiers (nom, adresse, description, statut) VALUES (?, ?, ?, ?)",
            (nom, adresse, description, statut),
        )
        chantier_id = cur.lastrowid
        _seed_chantier_defaults(conn, chantier_id)
        return chantier_id


def update_chantier(chantier_id, nom, adresse="", description="", statut="En cours"):
    with get_connection() as conn:
        conn.execute(
            "UPDATE chantiers SET nom=?, adresse=?, description=?, statut=? WHERE id=?",
            (nom, adresse, description, statut, chantier_id),
        )


def delete_chantier(chantier_id):
    """Supprime le chantier et TOUTES ses données (étapes, catégories,
    fournisseurs, employés, dépenses, paiements, mouvements, réglages) via
    les contraintes ON DELETE CASCADE. Action irréversible : à confirmer
    fortement côté interface avant appel."""
    with get_connection() as conn:
        conn.execute("DELETE FROM chantiers WHERE id = ?", (chantier_id,))


def get_totaux_chantiers():
    """Retourne, pour chaque chantier : nombre de dépenses et montant total dépensé."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT c.*, COUNT(d.id) AS nb_depenses, COALESCE(SUM(d.montant_total), 0) AS total_depenses
            FROM chantiers c
            LEFT JOIN depenses d ON d.chantier_id = c.id
            GROUP BY c.id
            ORDER BY c.id
            """
        ).fetchall()
        return _rows_to_dicts(rows)


def get_indicateurs_tous_chantiers():
    """Version agrégée, tous chantiers confondus, des indicateurs clés :
    montant total des dépenses, dettes fournisseurs et situation des
    employés (montant dû, réglé, reste à payer). Utilisée pour la vue
    d'ensemble multi-chantiers du tableau de bord principal — mêmes formules
    que `get_dettes_fournisseurs`/`get_totaux_employes`, simplement sans le
    filtre `chantier_id`."""
    with get_connection() as conn:
        total_depenses = conn.execute("SELECT COALESCE(SUM(montant_total), 0) FROM depenses").fetchone()[0]

        rows_f = conn.execute(
            """
            SELECT f.solde_initial,
                   COALESCE((SELECT SUM(d.montant_total) FROM depenses d WHERE d.fournisseur_id = f.id), 0) AS total_achats,
                   COALESCE((SELECT SUM(p.montant) FROM paiements_fournisseurs p WHERE p.fournisseur_id = f.id), 0) AS total_paye
            FROM fournisseurs f
            """
        ).fetchall()
        total_dettes_fournisseurs = round(
            sum(r["solde_initial"] + r["total_achats"] - r["total_paye"] for r in rows_f), 2
        )

        rows_e = conn.execute(
            """
            SELECT e.montant_du,
                   COALESCE((SELECT SUM(m.montant) FROM mouvements_employes m
                             WHERE m.employe_id = e.id AND m.type = 'avance'), 0) AS total_avance,
                   COALESCE((SELECT SUM(m.montant) FROM mouvements_employes m
                             WHERE m.employe_id = e.id AND m.type = 'paiement'), 0) AS total_paye
            FROM employes e
            """
        ).fetchall()
        total_du_employes = round(sum(r["montant_du"] for r in rows_e), 2)
        total_regle_employes = round(sum(r["total_avance"] + r["total_paye"] for r in rows_e), 2)

    return {
        "total_depenses": total_depenses,
        "total_dettes_fournisseurs": total_dettes_fournisseurs,
        "total_du_employes": total_du_employes,
        "total_regle_employes": total_regle_employes,
        "reste_a_payer_employes": round(total_du_employes - total_regle_employes, 2),
    }


# ---------------------------------------------------------------------------
# ÉTAPES
# ---------------------------------------------------------------------------

def get_etapes(chantier_id):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM etapes WHERE chantier_id = ? ORDER BY ordre, id", (chantier_id,)
        ).fetchall()
        return _rows_to_dicts(rows)


def get_etape(etape_id):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM etapes WHERE id = ?", (etape_id,)).fetchone()
        return dict(row) if row else None


def add_etape(chantier_id, nom, description="", budget_alloue=0, ordre=None):
    with get_connection() as conn:
        if ordre is None:
            ordre = (
                conn.execute(
                    "SELECT COALESCE(MAX(ordre), 0) FROM etapes WHERE chantier_id = ?", (chantier_id,)
                ).fetchone()[0] or 0
            ) + 1
        cur = conn.execute(
            "INSERT INTO etapes (chantier_id, nom, description, budget_alloue, ordre) VALUES (?, ?, ?, ?, ?)",
            (chantier_id, nom, description, budget_alloue, ordre),
        )
        return cur.lastrowid


def update_etape(etape_id, nom, description="", budget_alloue=0, ordre=0):
    with get_connection() as conn:
        conn.execute(
            "UPDATE etapes SET nom=?, description=?, budget_alloue=?, ordre=? WHERE id=?",
            (nom, description, budget_alloue, ordre, etape_id),
        )


def delete_etape(etape_id):
    """Supprime l'étape. Les dépenses liées ne sont pas supprimées : `etape_id`
    passe à NULL automatiquement (contrainte ON DELETE SET NULL du schéma)."""
    with get_connection() as conn:
        conn.execute("DELETE FROM etapes WHERE id = ?", (etape_id,))


def get_couts_par_etape(chantier_id):
    """Retourne, pour chaque étape du chantier, le coût total des dépenses liées
    et le % du budget consommé."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT e.id, e.nom, e.description, e.budget_alloue,
                   COALESCE(SUM(d.montant_total), 0) AS cout_total,
                   COUNT(d.id) AS nb_depenses
            FROM etapes e
            LEFT JOIN depenses d ON d.etape_id = e.id
            WHERE e.chantier_id = ?
            GROUP BY e.id
            ORDER BY e.ordre, e.id
            """,
            (chantier_id,),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            budget = d["budget_alloue"] or 0
            d["pct_budget"] = round((d["cout_total"] / budget) * 100, 1) if budget > 0 else None
            result.append(d)
        return result


def get_cout_etape(etape_id):
    """Équivalent de `get_couts_par_etape` pour une seule étape (déjà identifiée
    par son id, donc sans besoin de `chantier_id`). Retourne `None` si l'étape
    n'existe pas/plus."""
    with get_connection() as conn:
        r = conn.execute(
            """
            SELECT e.id, e.nom, e.description, e.budget_alloue,
                   COALESCE(SUM(d.montant_total), 0) AS cout_total,
                   COUNT(d.id) AS nb_depenses
            FROM etapes e
            LEFT JOIN depenses d ON d.etape_id = e.id
            WHERE e.id = ?
            GROUP BY e.id
            """,
            (etape_id,),
        ).fetchone()
        if r is None:
            return None
        d = dict(r)
        budget = d["budget_alloue"] or 0
        d["pct_budget"] = round((d["cout_total"] / budget) * 100, 1) if budget > 0 else None
        return d


# ---------------------------------------------------------------------------
# CATÉGORIES
# ---------------------------------------------------------------------------

def get_categories(chantier_id):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM categories WHERE chantier_id = ? ORDER BY nom", (chantier_id,)
        ).fetchall()
        return _rows_to_dicts(rows)


def get_categorie_by_nom(chantier_id, nom):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM categories WHERE chantier_id = ? AND nom = ?", (chantier_id, nom)
        ).fetchone()
        return dict(row) if row else None


def add_categorie(chantier_id, nom):
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO categories (chantier_id, nom) VALUES (?, ?)", (chantier_id, nom)
        )
        if cur.lastrowid and cur.rowcount:
            return cur.lastrowid
        row = conn.execute(
            "SELECT id FROM categories WHERE chantier_id = ? AND nom = ?", (chantier_id, nom)
        ).fetchone()
        return row["id"] if row else None


def get_or_create_categorie(chantier_id, nom):
    """Retourne l'id de la catégorie `nom` pour ce chantier, en la créant si besoin
    (même pattern que `get_or_create_fournisseur`/`get_or_create_employe`)."""
    nom = (nom or "").strip()
    if not nom:
        return None
    existing = get_categorie_by_nom(chantier_id, nom)
    if existing:
        return existing["id"]
    return add_categorie(chantier_id, nom)


def update_categorie(categorie_id, nom):
    """Renomme une catégorie : la relation par clé étrangère propage automatiquement
    ce renommage à toutes les dépenses déjà liées, sans risque de désynchronisation."""
    with get_connection() as conn:
        conn.execute("UPDATE categories SET nom = ? WHERE id = ?", (nom, categorie_id))


def delete_categorie(categorie_id):
    """Supprime la catégorie. Les dépenses liées ne sont pas supprimées :
    `categorie_id` passe à NULL automatiquement (ON DELETE SET NULL)."""
    with get_connection() as conn:
        conn.execute("DELETE FROM categories WHERE id = ?", (categorie_id,))


def get_totaux_categories(chantier_id):
    """Retourne, pour chaque catégorie du chantier, le nombre de dépenses liées
    et le montant total dépensé."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT c.id, c.nom,
                   COUNT(d.id) AS nb_depenses,
                   COALESCE(SUM(d.montant_total), 0) AS montant_total
            FROM categories c
            LEFT JOIN depenses d ON d.categorie_id = c.id
            WHERE c.chantier_id = ?
            GROUP BY c.id
            ORDER BY c.nom
            """,
            (chantier_id,),
        ).fetchall()
        return _rows_to_dicts(rows)


# ---------------------------------------------------------------------------
# FOURNISSEURS
# ---------------------------------------------------------------------------

def get_fournisseurs(chantier_id):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM fournisseurs WHERE chantier_id = ? ORDER BY nom", (chantier_id,)
        ).fetchall()
        return _rows_to_dicts(rows)


def get_fournisseur(fournisseur_id):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM fournisseurs WHERE id = ?", (fournisseur_id,)).fetchone()
        return dict(row) if row else None


def get_fournisseur_by_nom(chantier_id, nom):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM fournisseurs WHERE chantier_id = ? AND nom = ?", (chantier_id, nom)
        ).fetchone()
        return dict(row) if row else None


def add_fournisseur(chantier_id, nom, telephone="", adresse="", type_materiaux="", solde_initial=0):
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO fournisseurs (chantier_id, nom, telephone, adresse, type_materiaux, solde_initial)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (chantier_id, nom, telephone, adresse, type_materiaux, solde_initial),
        )
        return cur.lastrowid


def get_or_create_fournisseur(chantier_id, nom):
    """Retourne l'id du fournisseur `nom` pour ce chantier, en le créant s'il
    n'existe pas encore (utile à l'import)."""
    nom = (nom or "").strip()
    if not nom:
        return None
    existing = get_fournisseur_by_nom(chantier_id, nom)
    if existing:
        return existing["id"]
    return add_fournisseur(chantier_id, nom)


def update_fournisseur(fournisseur_id, nom, telephone="", adresse="", type_materiaux="", solde_initial=0):
    with get_connection() as conn:
        conn.execute(
            """UPDATE fournisseurs SET nom=?, telephone=?, adresse=?, type_materiaux=?, solde_initial=?
               WHERE id=?""",
            (nom, telephone, adresse, type_materiaux, solde_initial, fournisseur_id),
        )


def delete_fournisseur(fournisseur_id):
    """Supprime le fournisseur. Les dépenses liées ne sont pas supprimées :
    `fournisseur_id` passe à NULL automatiquement (ON DELETE SET NULL)."""
    with get_connection() as conn:
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


def get_dettes_fournisseurs(chantier_id):
    """Calcule, pour chaque fournisseur du chantier : total achats, total payé
    et dette restante.

    Dette restante = solde_initial + total des achats (dépenses) - total des paiements enregistrés.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT f.id, f.nom, f.telephone, f.adresse, f.type_materiaux, f.solde_initial,
                   COALESCE((SELECT SUM(d.montant_total) FROM depenses d WHERE d.fournisseur_id = f.id), 0) AS total_achats,
                   COALESCE((SELECT SUM(p.montant) FROM paiements_fournisseurs p WHERE p.fournisseur_id = f.id), 0) AS total_paye
            FROM fournisseurs f
            WHERE f.chantier_id = ?
            ORDER BY f.nom
            """,
            (chantier_id,),
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

def get_employes(chantier_id):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM employes WHERE chantier_id = ? ORDER BY nom", (chantier_id,)
        ).fetchall()
        return _rows_to_dicts(rows)


def get_employe(employe_id):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM employes WHERE id = ?", (employe_id,)).fetchone()
        return dict(row) if row else None


def get_employe_by_nom(chantier_id, nom):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM employes WHERE chantier_id = ? AND nom = ?", (chantier_id, nom)
        ).fetchone()
        return dict(row) if row else None


def add_employe(chantier_id, nom, fonction="", telephone="", montant_du=0):
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO employes (chantier_id, nom, fonction, telephone, montant_du) VALUES (?, ?, ?, ?, ?)",
            (chantier_id, nom, fonction, telephone, montant_du),
        )
        return cur.lastrowid


def get_or_create_employe(chantier_id, nom, fonction=""):
    nom = (nom or "").strip()
    if not nom:
        return None
    existing = get_employe_by_nom(chantier_id, nom)
    if existing:
        return existing["id"]
    return add_employe(chantier_id, nom, fonction=fonction)


def update_employe(employe_id, nom, fonction="", telephone="", montant_du=0):
    with get_connection() as conn:
        conn.execute(
            "UPDATE employes SET nom=?, fonction=?, telephone=?, montant_du=? WHERE id=?",
            (nom, fonction, telephone, montant_du, employe_id),
        )


def delete_employe(employe_id):
    """Supprime l'employé. Les dépenses liées ne sont pas supprimées :
    `employe_id` passe à NULL automatiquement (ON DELETE SET NULL)."""
    with get_connection() as conn:
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


def get_mouvement_employe(mouvement_id):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM mouvements_employes WHERE id = ?", (mouvement_id,)).fetchone()
        return dict(row) if row else None


def update_mouvement_employe(mouvement_id, montant, date_mouvement, commentaire):
    """Modifie une avance/paiement complémentaire saisi manuellement. Sans effet
    sur un mouvement généré automatiquement par une dépense (`depense_id` non
    nul) : celui-ci doit être modifié depuis la dépense elle-même (page
    Dépenses) pour ne pas désynchroniser les deux enregistrements."""
    with get_connection() as conn:
        conn.execute(
            """UPDATE mouvements_employes SET montant = ?, date = ?, commentaire = ?
               WHERE id = ? AND depense_id IS NULL""",
            (montant, date_mouvement, commentaire, mouvement_id),
        )


def delete_mouvement_employe(mouvement_id):
    """Supprime une avance/paiement complémentaire saisi manuellement. Sans effet
    sur un mouvement lié à une dépense (celui-ci est supprimé automatiquement
    avec la dépense via `delete_depense`, cascade SQL sur `depense_id`)."""
    with get_connection() as conn:
        conn.execute("DELETE FROM mouvements_employes WHERE id = ? AND depense_id IS NULL", (mouvement_id,))


def get_totaux_employes(chantier_id):
    """Calcule pour chaque employé du chantier : total dû, total avancé, total payé, reste à payer."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT e.id, e.nom, e.fonction, e.telephone, e.montant_du,
                   COALESCE((SELECT SUM(m.montant) FROM mouvements_employes m
                             WHERE m.employe_id = e.id AND m.type = 'avance'), 0) AS total_avance,
                   COALESCE((SELECT SUM(m.montant) FROM mouvements_employes m
                             WHERE m.employe_id = e.id AND m.type = 'paiement'), 0) AS total_paye
            FROM employes e
            WHERE e.chantier_id = ?
            ORDER BY e.nom
            """,
            (chantier_id,),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["total_regle"] = round(d["total_avance"] + d["total_paye"], 2)
            d["reste_a_payer"] = round(d["montant_du"] - d["total_regle"], 2)
            result.append(d)
        return result


def get_totaux_employe(employe_id):
    """Équivalent de `get_totaux_employes` pour un seul employé (déjà identifié
    par son id, donc sans besoin de `chantier_id`)."""
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT e.id, e.nom, e.fonction, e.telephone, e.montant_du,
                   COALESCE((SELECT SUM(m.montant) FROM mouvements_employes m
                             WHERE m.employe_id = e.id AND m.type = 'avance'), 0) AS total_avance,
                   COALESCE((SELECT SUM(m.montant) FROM mouvements_employes m
                             WHERE m.employe_id = e.id AND m.type = 'paiement'), 0) AS total_paye
            FROM employes e
            WHERE e.id = ?
            """,
            (employe_id,),
        ).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["total_regle"] = round(d["total_avance"] + d["total_paye"], 2)
        d["reste_a_payer"] = round(d["montant_du"] - d["total_regle"], 2)
        return d


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


def get_depenses(chantier_id):
    with get_connection() as conn:
        rows = conn.execute(
            DEPENSE_SELECT + " WHERE d.chantier_id = ? ORDER BY d.date DESC, d.id DESC", (chantier_id,)
        ).fetchall()
        return _rows_to_dicts(rows)


def get_depense(depense_id):
    with get_connection() as conn:
        row = conn.execute(DEPENSE_SELECT + " WHERE d.id = ?", (depense_id,)).fetchone()
        return dict(row) if row else None


def add_depense(chantier_id, date_depense, designation, categorie_id, etape_id, fournisseur_id, employe_id,
                 quantite, prix_unitaire, montant_total, mode_paiement, statut_paiement, observation,
                 justificatif_path=""):
    """Ajoute une dépense et déclenche automatiquement le mouvement d'employé associé
    si la dépense concerne un employé (catégorie 'Employé' + employé renseigné).
    Une dépense enregistrée représentant un décaissement déjà effectué (et non
    une simple avance donnée par anticipation), elle compte comme un
    'paiement' (Total payé), pas comme une 'avance' (Total avancé) — les
    avances restent réservées à la saisie manuelle sur la page Employés.
    `justificatif_path` est le chemin local (dans data/justificatifs/) d'une photo
    ou d'un scan de facture pris/importé depuis le formulaire, facultatif."""
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO depenses
               (chantier_id, date, designation, categorie_id, etape_id, fournisseur_id, employe_id,
                quantite, prix_unitaire, montant_total, mode_paiement, statut_paiement, observation,
                justificatif_path)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (chantier_id, date_depense, designation, categorie_id, etape_id, fournisseur_id, employe_id,
             quantite, prix_unitaire, montant_total, mode_paiement, statut_paiement, observation,
             justificatif_path),
        )
        depense_id = cur.lastrowid

        if employe_id:
            conn.execute(
                """INSERT INTO mouvements_employes (employe_id, date, type, montant, commentaire, depense_id)
                   VALUES (?, ?, 'paiement', ?, ?, ?)""",
                (employe_id, date_depense, montant_total, f"Dépense: {designation}".strip(": "), depense_id),
            )
        return depense_id


def update_depense(depense_id, date_depense, designation, categorie_id, etape_id, fournisseur_id, employe_id,
                    quantite, prix_unitaire, montant_total, mode_paiement, statut_paiement, observation,
                    justificatif_path=""):
    with get_connection() as conn:
        conn.execute(
            """UPDATE depenses SET
                date=?, designation=?, categorie_id=?, etape_id=?, fournisseur_id=?, employe_id=?,
                quantite=?, prix_unitaire=?, montant_total=?, mode_paiement=?, statut_paiement=?, observation=?,
                justificatif_path=?
               WHERE id=?""",
            (date_depense, designation, categorie_id, etape_id, fournisseur_id, employe_id,
             quantite, prix_unitaire, montant_total, mode_paiement, statut_paiement, observation,
             justificatif_path, depense_id),
        )
        # Le mouvement employé lié est resynchronisé (montant/date/employé peuvent avoir changé)
        conn.execute("DELETE FROM mouvements_employes WHERE depense_id = ?", (depense_id,))
        if employe_id:
            conn.execute(
                """INSERT INTO mouvements_employes (employe_id, date, type, montant, commentaire, depense_id)
                   VALUES (?, ?, 'paiement', ?, ?, ?)""",
                (employe_id, date_depense, montant_total, f"Dépense: {designation}".strip(": "), depense_id),
            )


def delete_depense(depense_id):
    """Supprime la dépense et son éventuel fichier justificatif associé."""
    with get_connection() as conn:
        row = conn.execute("SELECT justificatif_path FROM depenses WHERE id = ?", (depense_id,)).fetchone()
        conn.execute("DELETE FROM depenses WHERE id = ?", (depense_id,))

    if row and row["justificatif_path"]:
        try:
            Path(row["justificatif_path"]).unlink(missing_ok=True)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# INDICATEURS GLOBAUX (tableau de bord)
# ---------------------------------------------------------------------------

def get_indicateurs_globaux(chantier_id):
    with get_connection() as conn:
        total_depenses = conn.execute(
            "SELECT COALESCE(SUM(montant_total), 0) FROM depenses WHERE chantier_id = ?", (chantier_id,)
        ).fetchone()[0]
        nb_depenses = conn.execute(
            "SELECT COUNT(*) FROM depenses WHERE chantier_id = ?", (chantier_id,)
        ).fetchone()[0]
        nb_fournisseurs = conn.execute(
            "SELECT COUNT(*) FROM fournisseurs WHERE chantier_id = ?", (chantier_id,)
        ).fetchone()[0]
        nb_employes = conn.execute(
            "SELECT COUNT(*) FROM employes WHERE chantier_id = ?", (chantier_id,)
        ).fetchone()[0]
        budget_row = conn.execute(
            "SELECT value FROM settings WHERE chantier_id = ? AND key = 'budget_global'", (chantier_id,)
        ).fetchone()
        budget_global = float(budget_row[0]) if budget_row and budget_row[0] else 0

        mois_courant = _today()[:7]     # "YYYY-MM"
        annee_courante = _today()[:4]   # "YYYY"
        depenses_mois_courant = conn.execute(
            "SELECT COALESCE(SUM(montant_total), 0) FROM depenses WHERE chantier_id = ? AND strftime('%Y-%m', date) = ?",
            (chantier_id, mois_courant),
        ).fetchone()[0]
        depenses_annee_courante = conn.execute(
            "SELECT COALESCE(SUM(montant_total), 0) FROM depenses WHERE chantier_id = ? AND strftime('%Y', date) = ?",
            (chantier_id, annee_courante),
        ).fetchone()[0]

    dettes = get_dettes_fournisseurs(chantier_id)
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
        "depenses_mois_courant": depenses_mois_courant,
        "depenses_annee_courante": depenses_annee_courante,
        "mois_courant": mois_courant,
        "annee_courante": annee_courante,
    }


def get_budget_global(chantier_id):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE chantier_id = ? AND key = 'budget_global'", (chantier_id,)
        ).fetchone()
        return float(row[0]) if row and row[0] else 0.0


def set_budget_global(chantier_id, montant):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO settings (chantier_id, key, value) VALUES (?, 'budget_global', ?) "
            "ON CONFLICT(chantier_id, key) DO UPDATE SET value = excluded.value",
            (chantier_id, str(montant)),
        )


# ---------------------------------------------------------------------------
# HISTORIQUE DES PAIEMENTS (fournisseurs + employés confondus)
# ---------------------------------------------------------------------------

def get_historique_paiements(chantier_id):
    """Retourne la liste unifiée de tous les paiements du chantier (fournisseurs et employés)."""
    with get_connection() as conn:
        rows_f = conn.execute(
            """
            SELECT p.id, p.date, p.montant, f.nom AS beneficiaire, 'Fournisseur' AS type,
                   p.mode_paiement, p.commentaire
            FROM paiements_fournisseurs p
            JOIN fournisseurs f ON f.id = p.fournisseur_id
            WHERE f.chantier_id = ?
            """,
            (chantier_id,),
        ).fetchall()
        rows_e = conn.execute(
            """
            SELECT m.id, m.date, m.montant, e.nom AS beneficiaire,
                   ('Employé - ' || CASE m.type WHEN 'avance' THEN 'Avance' ELSE 'Paiement' END) AS type,
                   '' AS mode_paiement, m.commentaire
            FROM mouvements_employes m
            JOIN employes e ON e.id = m.employe_id
            WHERE e.chantier_id = ?
            """,
            (chantier_id,),
        ).fetchall()

    historique = _rows_to_dicts(rows_f) + _rows_to_dicts(rows_e)
    historique.sort(key=lambda x: (x["date"] or "", x["id"]), reverse=True)
    return historique
