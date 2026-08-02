# 🏗️ Suivi de Chantier — Dashboard de gestion financière

Application complète de suivi de chantier : dépenses, étapes, catégories,
fournisseurs (avec dettes), employés (avances/paiements), statistiques,
recherche globale et import/export Excel/PDF/CSV. Construite avec
**Streamlit**, **Pandas**, **Plotly** et **SQLite**, avec un thème sombre
façon SaaS moderne (accent indigo/violet).

## Installation

```bash
pip install -r requirements.txt
```

## Lancer l'application

```bash
streamlit run app.py
```

Au premier lancement, `database/suivi_chantier.db` est créée automatiquement
(tables, index, données de référence par défaut : étapes, catégories, modes de
paiement). L'application s'ouvre sur le **Tableau de bord** (`app.py`). Les
autres pages (Dépenses, Étapes, Catégories, Fournisseurs, Dettes Fournisseurs,
Employés, Paiements, Statistiques, Recherche, Import/Export) sont accessibles
depuis le menu latéral.

Pour importer vos propres données Excel (ou repartir d'un nouveau fichier),
utilisez la page **Import / Export** : elle détecte automatiquement la
feuille, la ligne d'en-tête et les colonnes, affiche un aperçu des
correspondances, puis importe sans perte après votre confirmation.

## Architecture

```
app.py                            → Tableau de bord principal (page d'accueil)
pages/
    01_🧾_Dépenses.py             → CRUD dépenses, recherche/filtre/tri, export
    02_🏗️_Étapes.py               → CRUD étapes, coût par étape, % budget
    03_🏷️_Catégories.py           → CRUD catégories (avec confirmation de suppression)
    04_🧱_Fournisseurs.py         → CRUD fournisseurs, fiche, paiements
    05_📉_Dettes_Fournisseurs.py  → Vue consolidée des dettes
    06_👷_Employés.py             → CRUD employés, avances, paiements, fiche
    07_💳_Paiements.py            → Historique unifié des paiements
    08_📊_Statistiques.py         → Graphiques Plotly (mois, année, étape, catégorie...)
    09_🔎_Recherche.py            → Recherche globale
    10_📥_Import_Export.py        → Import Excel intelligent + export
database/
    database.py                   → Schéma SQLite + migrations + fonctions CRUD/calculs
    suivi_chantier.db             → Base de données (créée automatiquement)
utils/
    helpers.py                    → Thème dark SaaS, palettes, cartes KPI, confirm_delete
    excel_import.py               → Détection auto des colonnes + import
    exports.py                    → Export Excel / CSV / PDF
data/                              → Dossier prévu pour d'éventuels fichiers à importer
```

## Base de données et migrations

Le schéma normalise chaque dimension (étape, catégorie, fournisseur, employé)
en table dédiée reliée aux dépenses par clé étrangère (`etape_id`,
`categorie_id`, `fournisseur_id`, `employe_id`), avec index sur toutes ces
colonnes ainsi que sur la date. `database.py::init_db()` crée le schéma s'il
n'existe pas et exécute les migrations nécessaires automatiquement à chaque
démarrage (idempotentes, sans risque à relancer) — la dernière en date a
transformé l'ancienne colonne texte `depenses.categorie` en relation
`categorie_id` vers la table `categories`, pour permettre un renommage propre
des catégories sans désynchronisation.

## Automatisations

Chaque dépense ajoutée met à jour automatiquement :
- le coût total de son étape,
- le total de sa catégorie,
- la dette du fournisseur lié (si renseigné),
- les avances de l'employé lié (si renseigné),
- toutes les statistiques et le tableau de bord (tout est recalculé à la volée,
  rien n'est stocké en double — aucune actualisation manuelle n'est nécessaire).

## Devise

La devise par défaut est le **MRU** (Ouguiya mauritanien). Pour la modifier,
changez la constante `CURRENCY` dans `utils/helpers.py`.

## Thème

Le thème sombre (fond, cartes, boutons, palettes de graphiques) est centralisé
dans `utils/helpers.py` : `inject_custom_css()` pour l'interface, et
`style_fig()` + les constantes `CATEGORICAL` / `SEQUENTIAL_BLUE` / `STATUS_*`
pour les graphiques Plotly. Modifier ces constantes suffit à ajuster
l'ensemble de l'application de façon cohérente.
