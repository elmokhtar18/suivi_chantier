# 🏗️ Suivi de Chantier — Dashboard de gestion financière

Application complète de suivi de chantier : dépenses, étapes, catégories,
fournisseurs (avec dettes), employés (avances/paiements), statistiques,
recherche globale et import/export Excel/PDF/CSV. Construite avec
**Streamlit**, **Pandas**, **Plotly** et **SQLite**, avec un thème sombre
façon SaaS moderne (accent **jaune/ambre**) et un **tableau de bord interactif**
(drill-down au clic).

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
paiement). L'application s'ouvre sur le **Tableau de bord** (`app.py`), qui est
**interactif** (drill-down) : cliquez sur « 🔍 Voir le détail » sous une carte,
ou sur une ligne des tableaux « Par catégorie / Par employé / Par mois », pour
ouvrir la liste des dépenses correspondantes directement sous le tableau de
bord (avec un lien vers la page Dépenses pour les filtres/tri/export complets).
Les autres pages (Dépenses, Étapes, Catégories, Fournisseurs, Dettes
Fournisseurs, Employés, Paiements, Statistiques, Recherche, Import/Export)
sont accessibles depuis le menu latéral.

Pour importer vos propres données Excel (ou repartir d'un nouveau fichier),
utilisez la page **Import / Export** : elle détecte automatiquement la
feuille, la ligne d'en-tête et les colonnes, affiche un aperçu des
correspondances, puis importe sans perte après votre confirmation.

## Architecture

```
app.py                            → Tableau de bord principal interactif (drill-down)
.streamlit/config.toml            → Thème natif Streamlit (dark + accent jaune)
pages/
    01_🧾_Dépenses.py             → CRUD dépenses, recherche/filtre/tri (dont Employé), export
    02_🏗️_Étapes.py               → CRUD étapes, coût par étape, % budget
    03_🏷️_Catégories.py           → CRUD catégories (avec confirmation de suppression)
    04_🧱_Fournisseurs.py         → CRUD fournisseurs, fiche, paiements
    05_📉_Dettes_Fournisseurs.py  → Vue consolidée des dettes
    06_👷_Employés.py             → CRUD employés, avances, paiements, fiche
    07_💳_Paiements.py            → Historique unifié des paiements
    08_📊_Statistiques.py         → Graphiques Plotly (mois, année, étape, catégorie, Top 10...)
    09_🔎_Recherche.py            → Recherche globale
    10_📥_Import_Export.py        → Import Excel intelligent + export
database/
    database.py                   → Schéma SQLite + migrations + fonctions CRUD/calculs
    suivi_chantier.db             → Base de données (créée automatiquement)
utils/
    helpers.py                    → Thème, palettes, cartes KPI, confirm_delete, drill-down
    excel_import.py               → Détection auto des colonnes + import
    exports.py                    → Export Excel / CSV / PDF
data/                              → Dossier prévu pour d'éventuels fichiers à importer
```

## Tableau de bord interactif (drill-down)

Chaque carte indicateur cliquable (Total, Dépenses du mois, Dépenses de
l'année, Nombre de dépenses) est accompagnée d'un bouton **« 🔍 Voir le
détail »**. Les tableaux « Par catégorie », « Par employé » et « Par mois »
s'ouvrent au clic sur une ligne (sélection native `st.dataframe`). Dans les
deux cas, une section « 🔎 Détail » apparaît sous le tableau de bord avec les
dépenses filtrées, quelques métriques (total/nombre/moyenne), un bouton
**« ↩️ Fermer »**, et un bouton **« ↗️ Page Dépenses »** qui rouvre le même
filtre sur la page Dépenses complète (tri, recherche, export...).

Ce mécanisme est géré par `utils/helpers.py` : `bouton_voir_detail()`,
`filtrer_depenses_dashboard()` et `ouvrir_dans_page_depenses()` — 100 % natif
Streamlit, sans dépendance tierce.

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

Le thème sombre s'appuie sur le **système de thème natif de Streamlit**
(`.streamlit/config.toml`, section `[theme]`) : il gère correctement tous les
composants natifs (boutons, `selectbox`/`multiselect`, sélecteur de date,
alertes...) sans qu'aucune règle CSS ne doive les réécrire — c'est ce qui
garantit que les listes déroulantes restent lisibles quel que soit le
contexte. `utils/helpers.py::inject_custom_css()` ajoute uniquement le CSS des
composants sur-mesure de l'app (cartes KPI, badges, fiches), ciblés par
classe — jamais de sélecteur générique (`div`, `span`, `p`...).

Palette : `ACCENT`/`ACCENT_2` (jaune/ambre, cohérents avec `primaryColor` du
`config.toml`) pilotent l'interface (boutons, icônes, hero). Les couleurs des
graphiques (`CATEGORICAL`, `SEQUENTIAL_BLUE`, `STATUS_*`) restent volontairement
distinctes : ce sont des couleurs d'**encodage de données** validées pour
l'accessibilité (daltonisme, contraste) via la méthode de la skill `dataviz` —
les mélanger à l'accent de marque romprait cette validation. Modifier ces
constantes dans `utils/helpers.py` suffit à ajuster l'ensemble de
l'application de façon cohérente.
