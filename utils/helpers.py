"""
Fonctions utilitaires partagées : mise en forme des nombres/dates, injection du
thème sombre "SaaS moderne" de l'application, palettes de couleurs (chrome +
data-viz) et composants d'affichage réutilisables (cartes indicateurs, badges,
en-têtes de section, confirmation de suppression).
"""

from datetime import datetime

import streamlit as st

# Devise utilisée dans tout le projet (Ouguiya mauritanien). Modifier cette
# seule constante suffit à changer la devise affichée dans toute l'application.
CURRENCY = "MRU"

# ---------------------------------------------------------------------------
# Palette — chrome (interface) : dark SaaS, accent indigo/violet
# ---------------------------------------------------------------------------
BG_APP = "#0b0c11"
BG_SURFACE = "#151720"
BG_SURFACE_2 = "#1c1f2b"
BORDER = "rgba(255,255,255,0.08)"
TEXT_PRIMARY = "#f5f5f7"
TEXT_SECONDARY = "#a3a7b7"
TEXT_MUTED = "#6b7086"
ACCENT = "#6366f1"
ACCENT_2 = "#8b5cf6"

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
    """Injecte le thème visuel sombre (SaaS moderne : cartes arrondies, ombres
    légères, accent indigo/violet, typographie Inter) utilisé sur toutes les pages."""
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        html, body, [class*="css"] {{
            font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif;
        }}

        .stApp {{
            background: {BG_APP};
        }}

        .main .block-container {{
            padding-top: 1.5rem; padding-bottom: 3rem; max-width: 1300px;
        }}

        h1, h2, h3, h4, h5, h6, p, span, label, div {{
            color: {TEXT_PRIMARY};
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
            border-color: rgba(99,102,241,0.45);
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
            font-size: 1.55rem; font-weight: 800; margin-top: 0.15rem; line-height: 1.15;
            color: {TEXT_PRIMARY};
        }}

        .kpi-hero {{
            border-radius: 22px;
            padding: 2.4rem 1.5rem;
            text-align: center;
            background: radial-gradient(120% 160% at 50% 0%, rgba(99,102,241,0.28) 0%, rgba(11,12,17,0) 60%), {BG_SURFACE};
            border: 1px solid {BORDER};
            box-shadow: 0 8px 30px rgba(0,0,0,0.4);
            margin-bottom: 1.3rem;
        }}
        .kpi-hero .kpi-hero-label {{
            font-size: 0.95rem; font-weight: 600; color: {TEXT_SECONDARY};
            text-transform: uppercase; letter-spacing: 0.08em;
        }}
        .kpi-hero .kpi-hero-value {{
            font-size: 3.4rem; font-weight: 800; margin-top: 0.35rem;
            background: linear-gradient(135deg, {ACCENT} 0%, {ACCENT_2} 100%);
            -webkit-background-clip: text; background-clip: text; color: transparent;
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
            background: linear-gradient(135deg, rgba(99,102,241,0.18) 0%, rgba(139,92,246,0.10) 100%), {BG_SURFACE};
            border: 1px solid {BORDER};
            margin-bottom: 1.2rem;
        }}
        .fiche-header h2 {{margin: 0; color: {TEXT_PRIMARY};}}
        .fiche-header p {{margin: 0.3rem 0 0 0; color: {TEXT_SECONDARY};}}

        /* ---- Sidebar ---- */
        section[data-testid="stSidebar"] {{
            background-color: {BG_SURFACE}; border-right: 1px solid {BORDER};
        }}
        section[data-testid="stSidebar"] * {{color: {TEXT_PRIMARY} !important;}}
        section[data-testid="stSidebar"] .stCaption, section[data-testid="stSidebar"] small {{
            color: {TEXT_SECONDARY} !important;
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

        /* ---- Boutons ---- */
        .stButton button, .stDownloadButton button, [data-testid="stFormSubmitButton"] button {{
            border-radius: 11px !important;
            border: 1px solid {BORDER} !important;
            background: {BG_SURFACE_2} !important;
            color: {TEXT_PRIMARY} !important;
            font-weight: 600 !important;
            transition: transform 0.12s ease, box-shadow 0.12s ease, border-color 0.12s ease, background 0.12s ease;
        }}
        .stButton button:hover, .stDownloadButton button:hover, [data-testid="stFormSubmitButton"] button:hover {{
            transform: translateY(-1px);
            border-color: {ACCENT} !important;
            box-shadow: 0 6px 16px rgba(99,102,241,0.28);
            background: linear-gradient(135deg, rgba(99,102,241,0.18), rgba(139,92,246,0.14)) !important;
        }}
        .stButton button[kind="primary"], [data-testid="stFormSubmitButton"] button[kind="primary"] {{
            background: linear-gradient(135deg, {ACCENT} 0%, {ACCENT_2} 100%) !important;
            border: none !important; color: white !important;
        }}
        .stButton button[kind="primary"]:hover {{box-shadow: 0 8px 22px rgba(99,102,241,0.45);}}

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

        /* ---- Responsive ---- */
        @media (max-width: 768px) {{
            .kpi-hero {{padding: 1.6rem 1rem;}}
            .kpi-hero .kpi-hero-value {{font-size: 2.2rem;}}
            .kpi-card {{padding: 0.9rem 1rem; min-height: 100px;}}
            .kpi-card .kpi-value {{font-size: 1.25rem;}}
            .section-title {{font-size: 1.1rem;}}
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
    statut = (statut or "").strip().lower()
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
