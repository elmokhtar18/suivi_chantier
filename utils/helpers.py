"""
Fonctions utilitaires partagées : mise en forme des nombres/dates, injection du
thème sombre "SaaS moderne" de l'application, palettes de couleurs (chrome +
data-viz), composants d'affichage réutilisables (cartes indicateurs, badges,
en-têtes de section, confirmation de suppression), drill-down du tableau de
bord, et intégration PWA/mobile (manifest, navigation basse, notifications
client) — voir `inject_pwa_head`, `bottom_nav_mobile`, `notification_client`.
"""

import base64
import calendar
import uuid
from datetime import datetime, date as date_cls
from pathlib import Path

import streamlit as st

from database import database as db

# Devise utilisée dans tout le projet (Ouguiya mauritanien). Modifier cette
# seule constante suffit à changer la devise affichée dans toute l'application.
CURRENCY = "MRU"

# Chemin de la page Dépenses, utilisé par le drill-down du tableau de bord
# (st.switch_page) — centralisé ici pour n'avoir qu'un seul endroit à mettre à
# jour si le fichier est renommé.
PAGE_DEPENSES = "pages/01_🧾_Dépenses.py"

# Listes de référence partagées par les pages Dépenses / Fournisseurs / Employés
# (source unique : évite les définitions dupliquées et divergentes entre pages).
MODES_PAIEMENT = ["Espèces", "Bankily", "Sedad", "Masrvi", "Chèque", "Virement", "Autre"]
STATUTS_PAIEMENT = ["Payé", "Non payé"]

# ---------------------------------------------------------------------------
# Palette — chrome (interface) : dark SaaS, accent jaune/ambre
# (cohérente avec .streamlit/config.toml : primaryColor = ACCENT)
# ---------------------------------------------------------------------------
BG_APP = "#0b0c11"
BG_SURFACE = "#151720"
BG_SURFACE_2 = "#1c1f2b"
BORDER = "rgba(255,255,255,0.08)"
TEXT_PRIMARY = "#f5f5f7"
TEXT_SECONDARY = "#a3a7b7"
TEXT_MUTED = "#6b7086"
ACCENT = "#eab308"
ACCENT_2 = "#facc15"
ACCENT_TEXT_ON = "#171200"  # texte sombre lisible sur fond jaune (boutons primaires)

# ---------------------------------------------------------------------------
# Palette — data-viz (steps dark mode validés, cf. skill dataviz)
# ---------------------------------------------------------------------------
CHART_BG = BG_SURFACE
CHART_GRID = "#2c2c2a"
CHART_AXIS = "#383835"
CHART_INK = "#ffffff"
CHART_INK_MUTED = "#c3c2b7"

# Ordre catégoriel fixe (ne jamais permuter selon les données affichées)
CATEGORICAL = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"]
# Séquentiel (magnitude), du plus faible au plus élevé — clair = fort sur fond sombre
SEQUENTIAL_BLUE = ["#184f95", "#1c5cab", "#256abf", "#2a78d6", "#3987e5", "#5598e7", "#86b6ef"]

STATUS_GOOD = "#0ca30c"
STATUS_WARNING = "#fab219"
STATUS_SERIOUS = "#ec835a"
STATUS_CRITICAL = "#d03b3b"

PLOTLY_DARK_TEMPLATE = {
    "paper_bgcolor": CHART_BG,
    "plot_bgcolor": CHART_BG,
    "font": {"color": CHART_INK_MUTED, "family": "Inter, system-ui, -apple-system, 'Segoe UI', sans-serif"},
    "colorway": CATEGORICAL,
    "xaxis": {"gridcolor": CHART_GRID, "linecolor": CHART_AXIS, "zerolinecolor": CHART_AXIS, "title_font_color": CHART_INK_MUTED},
    "yaxis": {"gridcolor": CHART_GRID, "linecolor": CHART_AXIS, "zerolinecolor": CHART_AXIS, "title_font_color": CHART_INK_MUTED},
    "legend": {"font": {"color": CHART_INK_MUTED}},
}


def style_fig(fig, **layout_overrides):
    """Applique le thème sombre Plotly commun à toutes les pages, puis les
    éventuels réglages spécifiques (hauteur, marges...) passés en kwargs."""
    fig.update_layout(**PLOTLY_DARK_TEMPLATE)
    fig.update_layout(**layout_overrides)
    return fig


def format_montant(valeur, devise=True):
    """Formate un nombre en '1 234 567 MRU' (séparateur d'espace, sans décimales inutiles)."""
    try:
        valeur = float(valeur or 0)
    except (TypeError, ValueError):
        valeur = 0
    entier = round(valeur)
    texte = f"{entier:,}".replace(",", " ")
    return f"{texte} {CURRENCY}" if devise else texte


def format_date(valeur, fmt_sortie="%d/%m/%Y"):
    """Convertit une date ISO ('YYYY-MM-DD') en format d'affichage FR. Tolère les valeurs vides."""
    if not valeur:
        return "-"
    if isinstance(valeur, datetime):
        return valeur.strftime(fmt_sortie)
    for fmt_entree in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(str(valeur)[:19], fmt_entree).strftime(fmt_sortie)
        except ValueError:
            continue
    return str(valeur)


def inject_custom_css():
    """Injecte le CSS complémentaire au thème natif Streamlit (`.streamlit/config.toml`,
    qui gère déjà correctement boutons, selectbox/multiselect, date picker et alertes
    en mode sombre avec l'accent jaune). Ce CSS ne cible QUE les composants sur-mesure
    de l'app (cartes KPI, badges, fiches...) — jamais de sélecteur générique
    (`div`, `span`, `p`...) qui pourrait déteindre sur les popovers BaseWeb et les
    rendre illisibles (c'était la cause des listes déroulantes invisibles)."""
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        html, body, [class*="css"] {{
            font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif;
        }}

        .main .block-container {{
            padding-top: 1.5rem; padding-bottom: 3rem; max-width: 1300px;
        }}

        /* ---- Cartes indicateurs (KPI) ---- */
        .kpi-card {{
            border-radius: 18px;
            padding: 1.15rem 1.3rem;
            background: {BG_SURFACE};
            border: 1px solid {BORDER};
            box-shadow: 0 4px 18px rgba(0,0,0,0.35);
            height: 100%;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            min-height: 118px;
            transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease;
        }}
        .kpi-card:hover {{
            transform: translateY(-2px);
            border-color: rgba(234,179,8,0.45);
            box-shadow: 0 10px 26px rgba(0,0,0,0.45);
        }}
        .kpi-card .kpi-icon {{
            width: 38px; height: 38px; border-radius: 11px;
            display: flex; align-items: center; justify-content: center;
            font-size: 1.15rem;
        }}
        .kpi-card .kpi-label {{
            font-size: 0.78rem; font-weight: 600; margin-top: 0.7rem;
            text-transform: uppercase; letter-spacing: 0.04em; color: {TEXT_SECONDARY};
        }}
        .kpi-card .kpi-value {{
            font-size: clamp(1.1rem, 2.2vw, 1.55rem); font-weight: 800; margin-top: 0.15rem; line-height: 1.2;
            color: {TEXT_PRIMARY};
            white-space: normal; overflow-wrap: break-word; word-break: break-word;
        }}

        .kpi-hero {{
            border-radius: 22px;
            padding: 2.4rem 1.5rem;
            text-align: center;
            background: radial-gradient(120% 160% at 50% 0%, rgba(234,179,8,0.22) 0%, rgba(11,12,17,0) 60%), {BG_SURFACE};
            border: 1px solid {BORDER};
            box-shadow: 0 8px 30px rgba(0,0,0,0.4);
            margin-bottom: 1.3rem;
        }}
        .kpi-hero .kpi-hero-label {{
            font-size: 0.95rem; font-weight: 600; color: {TEXT_SECONDARY};
            text-transform: uppercase; letter-spacing: 0.08em;
        }}
        .kpi-hero .kpi-hero-value {{
            font-size: clamp(1.8rem, 5vw, 3.4rem); font-weight: 800; margin-top: 0.35rem;
            background: linear-gradient(135deg, {ACCENT} 0%, {ACCENT_2} 100%);
            -webkit-background-clip: text; background-clip: text; color: transparent;
            white-space: normal; overflow-wrap: break-word; word-break: break-word;
        }}
        .kpi-hero .kpi-hero-sub {{font-size: 0.95rem; color: {TEXT_MUTED}; margin-top: 0.5rem;}}

        /* ---- Badges de statut ---- */
        .badge {{display: inline-block; padding: 0.2rem 0.75rem; border-radius: 999px;
                font-size: 0.76rem; font-weight: 700; border: 1px solid transparent;}}
        .badge-green  {{background: rgba(12,163,12,0.16);  color: #4ade80; border-color: rgba(12,163,12,0.35);}}
        .badge-red    {{background: rgba(208,59,59,0.16);  color: #f87171; border-color: rgba(208,59,59,0.35);}}
        .badge-orange {{background: rgba(250,178,25,0.16); color: #fbbf24; border-color: rgba(250,178,25,0.35);}}
        .badge-blue   {{background: rgba(57,135,229,0.16); color: #60a5fa; border-color: rgba(57,135,229,0.35);}}
        .badge-gray   {{background: {BG_SURFACE_2}; color: {TEXT_SECONDARY}; border-color: {BORDER};}}

        /* ---- En-têtes de section ---- */
        .section-title {{font-size: 1.3rem; font-weight: 700; margin: 0.4rem 0 1rem 0; color: {TEXT_PRIMARY};}}

        /* ---- Fiche entité (fournisseur / employé) ---- */
        .fiche-header {{
            border-radius: 18px; padding: 1.5rem 1.7rem;
            background: linear-gradient(135deg, rgba(234,179,8,0.16) 0%, rgba(250,204,21,0.08) 100%), {BG_SURFACE};
            border: 1px solid {BORDER};
            margin-bottom: 1.2rem;
        }}
        .fiche-header h2 {{margin: 0; color: {TEXT_PRIMARY}; white-space: normal; overflow-wrap: break-word;}}
        .fiche-header p {{margin: 0.3rem 0 0 0; color: {TEXT_SECONDARY}; white-space: normal; overflow-wrap: break-word;}}

        /* ---- Sidebar ---- */
        /* Fond distinct uniquement : la couleur du texte est déjà gérée correctement
           par le thème natif (config.toml) — pas de surcharge générique ici. */
        section[data-testid="stSidebar"] {{
            background-color: {BG_SURFACE}; border-right: 1px solid {BORDER};
        }}

        /* ---- Métriques natives Streamlit ---- */
        div[data-testid="stMetric"] {{
            background: {BG_SURFACE}; border: 1px solid {BORDER}; border-radius: 16px;
            padding: 0.9rem 1.1rem; box-shadow: 0 2px 10px rgba(0,0,0,0.25);
        }}
        div[data-testid="stMetricLabel"] {{color: {TEXT_SECONDARY} !important;}}
        div[data-testid="stMetricValue"] {{
            color: {TEXT_PRIMARY} !important;
            white-space: normal !important;
            overflow: visible !important;
            text-overflow: unset !important;
            word-break: break-word;
            font-size: 1.35rem !important;
            line-height: 1.25 !important;
        }}
        div[data-testid="stMetricValue"] > div {{
            white-space: normal !important;
            overflow: visible !important;
            text-overflow: unset !important;
        }}

        /* ---- Conteneurs avec bordure (st.container(border=True)) ---- */
        div[data-testid="stVerticalBlockBorderWrapper"] > div {{
            background: {BG_SURFACE};
            border-color: {BORDER} !important;
            border-radius: 16px !important;
        }}

        /* ---- Tableaux ---- */
        div[data-testid="stDataFrame"] {{
            border-radius: 14px; overflow: hidden; border: 1px solid {BORDER};
        }}

        /* ---- Boutons ----
           Le fond du bouton primaire (jaune) vient du thème natif (primaryColor,
           config.toml) : on ne le réécrit pas ici, on ajoute seulement coins
           arrondis + animation au survol, cohérents sur primaire et secondaire. */
        .stButton button, .stDownloadButton button, [data-testid="stFormSubmitButton"] button {{
            border-radius: 11px !important;
            font-weight: 600 !important;
            min-height: 44px; /* cible tactile Apple HIG : jamais un bouton trop petit au doigt */
            transition: transform 0.12s ease, box-shadow 0.12s ease, border-color 0.12s ease, filter 0.12s ease;
        }}
        .stButton button:hover, .stDownloadButton button:hover, [data-testid="stFormSubmitButton"] button:hover {{
            transform: translateY(-1px);
            border-color: {ACCENT} !important;
            box-shadow: 0 6px 16px rgba(234,179,8,0.25);
        }}
        .stButton button[kind="primary"], [data-testid="stFormSubmitButton"] button[kind="primary"] {{
            color: {ACCENT_TEXT_ON} !important;
        }}
        .stButton button[kind="primary"]:hover, [data-testid="stFormSubmitButton"] button[kind="primary"]:hover {{
            filter: brightness(1.08);
            box-shadow: 0 8px 22px rgba(234,179,8,0.4);
        }}

        /* ---- Champs de formulaire ---- */
        div[data-baseweb="input"], div[data-baseweb="select"], div[data-baseweb="textarea"],
        div[data-baseweb="base-input"] {{
            border-radius: 10px !important;
        }}
        [data-testid="stForm"] {{
            background: {BG_SURFACE}; border: 1px solid {BORDER}; border-radius: 16px; padding: 1.2rem;
        }}
        [data-testid="stExpander"] {{
            background: {BG_SURFACE}; border: 1px solid {BORDER}; border-radius: 16px;
        }}

        /* ---- Onglets ---- */
        .stTabs [data-baseweb="tab-list"] {{gap: 4px;}}
        .stTabs [data-baseweb="tab"] {{
            border-radius: 10px 10px 0 0; color: {TEXT_SECONDARY};
        }}
        .stTabs [aria-selected="true"] {{color: {ACCENT_2} !important;}}

        hr {{border-color: {BORDER} !important;}}

        /* ---- Responsive ----
           Les tailles de police des cartes utilisent déjà clamp() (rétrécissement
           fluide) : ces points de rupture n'ajustent que les espacements, pas les
           polices, pour ne jamais faire disparaître/couper un chiffre. */
        @media (max-width: 1024px) {{
            .main .block-container {{padding-left: 1rem; padding-right: 1rem;}}
            .kpi-hero {{padding: 1.9rem 1.2rem;}}
        }}
        @media (max-width: 768px) {{
            .kpi-hero {{padding: 1.6rem 1rem;}}
            .kpi-card {{padding: 0.9rem 1rem; min-height: 100px;}}
            .section-title {{font-size: 1.1rem;}}
            /* Place libre pour la barre de navigation mobile fixe + l'encoche iPhone */
            .main .block-container {{padding-bottom: calc(4.5rem + env(safe-area-inset-bottom, 0px));}}
        }}

        /* ---- Barre de navigation mobile (voir bottom_nav_mobile()) ----
           Ciblée via la clé de conteneur Streamlit (classe st-key-<key>) :
           masquée par défaut, affichée uniquement sous 768px. */
        .st-key-bottom_nav_mobile {{display: none;}}
        @media (max-width: 768px) {{
            .st-key-bottom_nav_mobile {{
                display: flex !important;
                flex-direction: row !important;
                position: fixed; left: 0; right: 0; bottom: 0; z-index: 999;
                background: {BG_SURFACE};
                border-top: 1px solid {BORDER};
                padding: 0.3rem 0.4rem calc(0.3rem + env(safe-area-inset-bottom, 0px));
                gap: 0.2rem;
                box-shadow: 0 -4px 18px rgba(0,0,0,0.35);
            }}
            /* `bottom_nav_mobile()` pose les st.page_link à plat (pas de
               st.columns) : un seul niveau de wrapper Streamlit à neutraliser
               ici (stVerticalBlock + stElementContainer), ce qui reste fiable
               avec `display: contents` même sous Safari/WebKit iOS. */
            .st-key-bottom_nav_mobile [data-testid="stVerticalBlock"],
            .st-key-bottom_nav_mobile [data-testid="stElementContainer"] {{
                display: contents !important;
            }}
            .st-key-bottom_nav_mobile [data-testid="stPageLink"] {{
                flex: 1;
            }}
            .st-key-bottom_nav_mobile [data-testid="stPageLink"] a {{
                display: flex; flex-direction: column; align-items: center; justify-content: center;
                gap: 0.15rem; padding: 0.35rem 0.1rem; border-radius: 10px;
                min-height: 48px; text-decoration: none !important;
                color: {TEXT_SECONDARY} !important; font-size: 0.68rem !important;
            }}
            .st-key-bottom_nav_mobile [data-testid="stPageLink"] a:hover {{
                background: {BG_SURFACE_2};
                color: {ACCENT_2} !important;
            }}
            .st-key-bottom_nav_mobile [data-testid="stPageLink"] p {{
                font-size: 0.68rem !important; margin: 0 !important;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def kpi_card(icon, label, value, color_from=ACCENT, color_to=ACCENT_2):
    """Rend une carte indicateur sombre avec une puce d'icône colorée (dégradé accent)."""
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-icon" style="background: linear-gradient(135deg, {color_from} 0%, {color_to} 100%);">{icon}</div>
            <div>
                <div class="kpi-label">{label}</div>
                <div class="kpi-value">{value}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def kpi_hero(label, value, sub=""):
    """Rend la grande carte centrale (montant total des dépenses)."""
    st.markdown(
        f"""
        <div class="kpi-hero">
            <div class="kpi-hero-label">{label}</div>
            <div class="kpi-hero-value">{value}</div>
            <div class="kpi-hero-sub">{sub}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_title(text, icon=""):
    st.markdown(f'<div class="section-title">{icon} {text}</div>', unsafe_allow_html=True)


def badge(text, color="gray"):
    return f'<span class="badge badge-{color}">{text}</span>'


def statut_badge(statut):
    # `statut` peut être un NaN pandas (float) quand la valeur est absente dans
    # un DataFrame — NaN est "truthy", donc `statut or ""` ne suffit pas à s'en
    # prémunir ; on force explicitement une chaîne avant de la traiter.
    statut = str(statut).strip().lower() if statut and not isinstance(statut, float) else ""
    if statut in ("payé", "paye", "p"):
        return badge("Payé", "green")
    if statut in ("non payé", "non paye", "np"):
        return badge("Non payé", "red")
    return badge(statut.title() if statut else "-", "gray")


def dette_badge(montant):
    if montant > 0:
        return badge(f"Doit {format_montant(montant)}", "red")
    if montant < 0:
        return badge(f"Avoir {format_montant(-montant)}", "blue")
    return badge("Soldé", "green")


def confirm_delete(label, key, on_confirm):
    """Affiche un bouton de suppression à confirmation en deux temps.

    Premier clic : affiche un avertissement + boutons Confirmer/Annuler (rien
    n'est supprimé). Un clic sur "Confirmer" appelle `on_confirm()` puis
    déclenche `st.rerun()`. Réutilisé sur toutes les pages qui suppriment une
    entité (dépenses, étapes, catégories, fournisseurs, employés).
    """
    flag_key = f"confirm_delete_{key}"

    if not st.session_state.get(flag_key, False):
        if st.button(f"🗑️ Supprimer {label}", key=f"btn_{flag_key}", width="stretch"):
            st.session_state[flag_key] = True
            st.rerun()
        return

    st.warning(f"⚠️ Confirmer la suppression de **{label}** ? Cette action est irréversible.")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("✅ Confirmer la suppression", key=f"ok_{flag_key}", type="primary", width="stretch"):
            on_confirm()
            st.session_state.pop(flag_key, None)
            st.rerun()
    with c2:
        if st.button("↩️ Annuler", key=f"cancel_{flag_key}", width="stretch"):
            st.session_state.pop(flag_key, None)
            st.rerun()


# ---------------------------------------------------------------------------
# Notifications différées ("flash messages")
# ---------------------------------------------------------------------------
# Une modale (`st.dialog`) qui appelle `st.rerun()` se ferme immédiatement :
# un `st.success()` posé juste avant n'a pas le temps de rester visible. Le
# message est donc stocké en session, puis affiché par `render_flash()` au
# début de la page principale, une fois la modale refermée.

def flash(message, icone="✅", notifier=False, titre_notification=None):
    """À appeler juste avant un `st.rerun()` (depuis une modale, ou après tout
    enregistrement) : le message apparaîtra sur la page une fois le prochain
    rendu terminé — appeler `notification_client()` directement avant un
    `st.rerun()` risquerait de couper le script avant que la notification
    (une iframe + script) ait fini de se charger dans le navigateur.

    Empilable : plusieurs appels avant le même `st.rerun()` (ex. "dépense
    enregistrée" puis "budget dépassé") affichent bien tous leurs messages,
    au lieu de s'écraser les uns les autres.

    `notifier=True` déclenche en plus une notification navigateur (voir
    `notification_client`), utile pour les événements mobiles (ex. "Nouvelle
    dépense enregistrée")."""
    st.session_state.setdefault("_flash_queue", []).append(
        (message, icone, notifier, titre_notification or "Suivi de Chantier")
    )


def render_flash():
    """À appeler en haut d'une page pour afficher (une seule fois) tous les
    messages éventuellement posés par `flash()` depuis le rendu précédent."""
    for message, icone, notifier, titre_notification in st.session_state.pop("_flash_queue", []):
        st.toast(message, icon=icone)
        if notifier:
            notification_client(titre_notification, message)


# ---------------------------------------------------------------------------
# Drill-down du tableau de bord (app.py)
# ---------------------------------------------------------------------------
# Un "filtre de drill-down" est un petit dict {"type": ..., "value": ...} posé
# dans st.session_state["dashboard_filtre"] par un clic sur une carte KPI ou
# une ligne de tableau. `filtrer_depenses_dashboard` l'applique à un DataFrame
# de dépenses pour la vue détail inline ; `bouton_voir_detail` est le petit
# bouton "🔍 Voir le détail" posé sous chaque carte/ligne cliquable.

def bouton_voir_detail(label, key, **filtre):
    """Petit bouton qui pose le filtre de drill-down donné et relance la page.
    (Streamlit ne permet pas de rendre une carte HTML personnalisée directement
    cliquable ; ce bouton associé à chaque carte est le mécanisme robuste natif.)"""
    if st.button(label, key=f"drill_{key}", width="stretch"):
        st.session_state["dashboard_filtre"] = filtre
        st.rerun()


def filtrer_depenses_dashboard(df, filtre):
    """Applique un filtre de drill-down à un DataFrame de dépenses (colonnes
    canoniques de `database.get_depenses`). Retourne (df_filtré, libellé lisible)."""
    if not filtre or filtre.get("type") in (None, "total"):
        return df, "Toutes les dépenses"

    type_, valeur = filtre.get("type"), filtre.get("value")
    if type_ == "categorie":
        return df[df["categorie_nom"] == valeur], f"Catégorie : {valeur}"
    if type_ == "employe":
        return df[df["employe_nom"] == valeur], f"Employé : {valeur}"
    if type_ == "etape":
        return df[df["etape_nom"] == valeur], f"Étape : {valeur}"
    if type_ == "mois":
        libelle = datetime.strptime(valeur, "%Y-%m").strftime("%B %Y")
        return df[df["date"].str.startswith(valeur)], f"Mois : {libelle}"
    if type_ == "annee":
        return df[df["date"].str.startswith(valeur)], f"Année : {valeur}"
    return df, "Toutes les dépenses"


def ouvrir_dans_page_depenses(filtre):
    """Pré-remplit les clés de session des filtres de `pages/01_🧾_Dépenses.py`
    à partir d'un filtre de drill-down, puis y bascule (tri/recherche/export
    complets pour l'utilisateur qui veut aller plus loin que la vue rapide)."""
    for cle in ("filtre_etapes", "filtre_categories", "filtre_fournisseurs", "filtre_employes", "filtre_statuts"):
        st.session_state[cle] = []
    st.session_state["date_min"] = None
    st.session_state["date_max"] = None

    type_, valeur = filtre.get("type"), filtre.get("value")
    if type_ == "categorie":
        st.session_state["filtre_categories"] = [valeur]
    elif type_ == "employe":
        st.session_state["filtre_employes"] = [valeur]
    elif type_ == "etape":
        st.session_state["filtre_etapes"] = [valeur]
    elif type_ == "mois":
        annee, mois = (int(x) for x in valeur.split("-"))
        dernier_jour = calendar.monthrange(annee, mois)[1]
        st.session_state["date_min"] = date_cls(annee, mois, 1)
        st.session_state["date_max"] = date_cls(annee, mois, dernier_jour)
    elif type_ == "annee":
        st.session_state["date_min"] = date_cls(int(valeur), 1, 1)
        st.session_state["date_max"] = date_cls(int(valeur), 12, 31)

    st.switch_page(PAGE_DEPENSES)


# ---------------------------------------------------------------------------
# PWA (installation iPhone/Android) et navigation mobile
# ---------------------------------------------------------------------------
# Streamlit ne fournit aucun hook public pour écrire dans le <head> du
# document, et un <script> injecté via st.markdown(unsafe_allow_html=True)
# n'est JAMAIS exécuté par le navigateur (limitation générale du web : un
# <script> inséré via innerHTML ne s'exécute pas). Le contournement standard
# est de passer par un composant iframe (`st.iframe`, qui lui crée
# un vrai document où les scripts s'exécutent), puis d'atteindre le document
# PARENT via `window.parent` (même origine, donc autorisé) pour modifier le
# <head> réel de la page et enregistrer le service worker à ce niveau.

def inject_pwa_head():
    """Injecte le manifest PWA, les balises Apple (icône, plein écran,
    couleur de thème) et enregistre le service worker (`static/sw.js`). Sans
    effet si déjà fait (vérifie l'absence du lien manifest avant d'agir)."""
    st.iframe(
        """
        <script>
        (function() {
            const doc = window.parent.document;
            if (doc.querySelector('link[rel="manifest"]')) return;
            const head = doc.head;

            const manifest = doc.createElement('link');
            manifest.rel = 'manifest';
            manifest.href = './app/static/manifest.json';
            head.appendChild(manifest);

            const touchIcon = doc.createElement('link');
            touchIcon.rel = 'apple-touch-icon';
            touchIcon.href = './app/static/icons/apple-touch-icon.png';
            head.appendChild(touchIcon);

            const meta = (name, content) => {
                const m = doc.createElement('meta');
                m.name = name;
                m.content = content;
                head.appendChild(m);
            };
            meta('apple-mobile-web-app-capable', 'yes');
            meta('mobile-web-app-capable', 'yes');
            meta('apple-mobile-web-app-status-bar-style', 'black-translucent');
            meta('apple-mobile-web-app-title', 'Chantier');
            meta('theme-color', '#0b0c11');

            // Encoche / barre d'accueil iPhone : autorise le contenu à utiliser toute la zone.
            const vp = doc.querySelector('meta[name="viewport"]');
            if (vp && vp.content.indexOf('viewport-fit') === -1) {
                vp.content = vp.content + ', viewport-fit=cover';
            }

            if ('serviceWorker' in window.parent.navigator) {
                window.parent.navigator.serviceWorker
                    .register('./app/static/sw.js', { scope: './' })
                    .catch(() => {});
            }
        })();
        </script>
        """,
        height=1,
        width=1,
    )


def chantier_selector():
    """Sélecteur du chantier actif, affiché en haut de la barre latérale.
    L'application gère plusieurs chantiers en parallèle, chacun avec ses
    propres étapes/catégories/fournisseurs/employés/dépenses (cloisonnement
    total, voir `database.database`) : ce sélecteur détermine lequel est
    affiché/édité sur la page courante. Mémorise le choix dans
    `st.session_state["chantier_actif_id"]` et **retourne cet id** — à
    appeler une fois en haut de chaque page, juste après `inject_pwa_head()`."""
    chantiers = db.get_chantiers()

    if not chantiers:
        # Cas normalement impossible après le premier lancement (`init_db`
        # crée toujours "Chantier 1" s'il n'en existe aucun) — gardé pour la
        # robustesse si tous les chantiers ont été supprimés.
        st.sidebar.warning("Aucun chantier n'existe encore.")
        with st.sidebar.form("form_creation_premier_chantier"):
            nom = st.text_input("Nom du nouveau chantier")
            if st.form_submit_button("➕ Créer ce chantier", type="primary"):
                if nom.strip():
                    db.add_chantier(nom.strip())
                    st.rerun()
        st.stop()

    noms = [c["nom"] for c in chantiers]
    ids_par_nom = {c["nom"]: c["id"] for c in chantiers}
    noms_par_id = {c["id"]: c["nom"] for c in chantiers}

    # Constat vérifié empiriquement (pas une supposition) : la valeur mémorisée
    # d'un widget Streamlit sous sa `key` (ici "chantier_actif_nom") NE
    # survit PAS à une navigation vers une autre page en multipage — seule
    # une entrée `st.session_state` "libre" (non liée à un widget), ici
    # `chantier_actif_id`, persiste de façon fiable d'une page à l'autre.
    # C'est donc `chantier_actif_id` qui fait autorité, recalculé en `index=`
    # à chaque rendu plutôt que délégué à la mémoire du widget lui-même.
    #
    # Changer le chantier actif par programme (ex. juste après sa création,
    # voir `pages/00_🏗️_Chantiers.py`) écrit dans la clé intermédiaire
    # `_chantier_actif_id_demande` puis appelle `st.rerun()`. Sur une
    # navigation la clé du widget est déjà absente donc `index=` suffit ; sur
    # un rerun resté sur la même page il faut en plus l'effacer explicitement
    # ci-dessous, sinon sa mémoire (valeur *avant* la demande) l'emporterait.
    id_demande = st.session_state.pop("_chantier_actif_id_demande", None)
    if id_demande in noms_par_id:
        st.session_state["chantier_actif_id"] = id_demande
        st.session_state.pop("chantier_actif_nom", None)

    nom_actif = noms_par_id.get(st.session_state.get("chantier_actif_id"), noms[0])

    # Pas de lien manuel vers la page Chantiers ici : Streamlit liste déjà
    # automatiquement toutes les pages de `pages/` dans la navigation latérale
    # (dont "00_🏗️_Chantiers.py", en tête grâce à son préfixe numérique).
    with st.sidebar:
        choix = st.selectbox(
            "🏗️ Chantier actif", noms, index=noms.index(nom_actif), key="chantier_actif_nom"
        )

    chantier_id = ids_par_nom[choix]
    st.session_state["chantier_actif_id"] = chantier_id
    return chantier_id


def bottom_nav_mobile():
    """Barre de navigation fixe en bas d'écran, visible uniquement sur mobile
    (< 768px, cf. CSS dans `inject_custom_css`). Construite avec `st.page_link`
    (jamais un `href` codé en dur) pour rester correcte quels que soient les
    noms de fichiers de pages. À appeler une fois, en fin de script de page."""
    # Volontairement pas de `st.columns` ici : Streamlit imbrique colonnes et
    # blocs horizontaux dans plusieurs divs, et cette nidification profonde
    # combinée à `display: contents` (nécessaire pour "désimbriquer" la mise
    # en page) est peu fiable sous Safari/WebKit (bug connu). En posant les
    # `st.page_link` directement à plat dans le conteneur, un seul niveau de
    # nesting reste à neutraliser en CSS, ce qui est robuste sur iOS.
    with st.container(key="bottom_nav_mobile"):
        st.page_link("app.py", label="Accueil", icon="📊")
        st.page_link(PAGE_DEPENSES, label="Dépenses", icon="🧾")
        st.page_link("pages/08_📊_Statistiques.py", label="Stats", icon="📈")
        st.page_link("pages/09_🔎_Recherche.py", label="Recherche", icon="🔎")
        st.page_link("pages/10_📥_Import_Export.py", label="Plus", icon="⚙️")


def notification_client(titre, message):
    """Déclenche une notification navigateur **immédiate** côté client (l'app
    doit être ouverte) — ex. "Dépense enregistrée". Ne nécessite aucun serveur
    de push. Pour des notifications reçues app fermée, voir `utils/notifications.py`
    (architecture prête, désactivée)."""
    titre_js = titre.replace("\\", "\\\\").replace('"', '\\"')
    message_js = message.replace("\\", "\\\\").replace('"', '\\"')
    st.iframe(
        f"""
        <script>
        (function() {{
            const N = window.parent.Notification;
            if (!N) return;
            if (N.permission === 'granted') {{
                new N("{titre_js}", {{ body: "{message_js}", icon: './app/static/icons/icon-192.png' }});
            }}
        }})();
        </script>
        """,
        height=1,
        width=1,
    )


def demander_permission_notifications():
    """Bouton qui demande la permission d'afficher des notifications au
    navigateur (préalable indispensable à `notification_client` et aux futures
    notifications push)."""
    if st.button("🔔 Activer les notifications", key="btn_notif_permission"):
        st.iframe(
            """
            <script>
            if (window.parent.Notification && Notification.permission !== 'denied') {
                window.parent.Notification.requestPermission();
            }
            </script>
            """,
            height=1,
            width=1,
        )
        st.info("Autorisez les notifications si votre navigateur vous le demande.")


# ---------------------------------------------------------------------------
# Justificatifs (photo/scan de facture) — appareil photo ou galerie mobile
# ---------------------------------------------------------------------------
JUSTIFICATIFS_DIR = Path(__file__).resolve().parent.parent / "data" / "justificatifs"

_MIME_EXTENSIONS = {"image/jpeg": ".jpg", "image/png": ".png", "application/pdf": ".pdf"}


def enregistrer_justificatif(fichier, prefixe="depense"):
    """Enregistre sur disque un fichier reçu via `st.camera_input` ou
    `st.file_uploader` (photo ou scan de facture) et retourne son chemin
    absolu, à stocker tel quel dans `depenses.justificatif_path`. Retourne
    une chaîne vide si `fichier` est `None` (aucun justificatif fourni)."""
    if fichier is None:
        return ""
    JUSTIFICATIFS_DIR.mkdir(parents=True, exist_ok=True)
    extension = _MIME_EXTENSIONS.get(getattr(fichier, "type", ""), ".jpg")
    chemin = JUSTIFICATIFS_DIR / f"{prefixe}_{uuid.uuid4().hex[:12]}{extension}"
    chemin.write_bytes(fichier.getvalue())
    return str(chemin)


def afficher_justificatif(chemin):
    """Affiche un aperçu (image) ou un bouton de téléchargement (PDF/autre)
    pour un justificatif déjà enregistré. Ne fait rien si `chemin` est vide
    ou si le fichier n'existe plus sur disque."""
    if not chemin:
        return
    fichier = Path(chemin)
    if not fichier.exists():
        st.caption("⚠️ Justificatif introuvable (fichier déplacé ou supprimé).")
        return
    if fichier.suffix.lower() in (".jpg", ".jpeg", ".png"):
        st.image(str(fichier), caption="Justificatif", width="stretch")
    else:
        st.download_button(
            "⬇️ Télécharger le justificatif", fichier.read_bytes(),
            file_name=fichier.name, key=f"dl_justif_{fichier.stem}",
        )


def bouton_partage_pdf(pdf_bytes, nom_fichier, titre="Suivi de Chantier"):
    """Bouton de partage natif (feuille de partage iOS/Android via l'API
    `navigator.share`), en complément — jamais en remplacement — du
    `st.download_button` existant. Best-effort : si le navigateur ne supporte
    pas le partage de fichiers (ex. Chrome desktop, anciens Safari), le bouton
    affiche un message et l'utilisateur garde le téléchargement classique."""
    b64 = base64.b64encode(pdf_bytes).decode("ascii")
    nom_js = nom_fichier.replace("\\", "\\\\").replace('"', '\\"')
    titre_js = titre.replace("\\", "\\\\").replace('"', '\\"')
    st.iframe(
        f"""
        <style>
        body {{ margin: 0; font-family: -apple-system, system-ui, sans-serif; }}
        button {{
            width: 100%; min-height: 44px; padding: 8px; border-radius: 10px;
            border: 1px solid #333844; background: #1c1f2b; color: #f5f5f7;
            font-weight: 600; font-size: 14px; cursor: pointer;
        }}
        button:active {{ background: #eab308; color: #0b0c11; }}
        </style>
        <button id="btn-partage-pdf">📤 Partager le PDF</button>
        <script>
        document.getElementById('btn-partage-pdf').addEventListener('click', async function() {{
            try {{
                const binaire = atob("{b64}");
                const octets = new Uint8Array(binaire.length);
                for (let i = 0; i < binaire.length; i++) {{ octets[i] = binaire.charCodeAt(i); }}
                const fichier = new File([octets], "{nom_js}", {{ type: 'application/pdf' }});
                const nav = window.parent.navigator;
                if (nav.canShare && nav.canShare({{ files: [fichier] }})) {{
                    await nav.share({{ files: [fichier], title: "{titre_js}" }});
                }} else {{
                    window.parent.alert("Le partage direct n'est pas pris en charge par ce navigateur : utilisez le bouton de téléchargement ci-dessus.");
                }}
            }} catch (e) {{
                /* partage annulé par l'utilisateur : rien à faire */
            }}
        }});
        </script>
        """,
        height=54,
    )
