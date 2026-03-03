"""Objectif Lune theme — minimalist Tintin-inspired styling for Streamlit."""

import streamlit as st


# ── Plotly Layout Defaults ───────────────────────────────────
PLOTLY_LAYOUT = dict(
    plot_bgcolor="#FAFAF7",
    paper_bgcolor="#FAFAF7",
    font=dict(family="DM Sans, sans-serif", color="#2D3E50"),
    margin=dict(t=50, b=20, l=40, r=20),
    xaxis=dict(showgrid=True, gridcolor="#E8E4DB", gridwidth=1),
    yaxis=dict(showgrid=True, gridcolor="#E8E4DB", gridwidth=1),
)

# ── Reusable SVGs (no HTML comments — they break st.markdown) ─
_ROCKET_SVG_HEADER = '<svg width="28" height="28" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M50 8 C50 8, 65 25, 65 55 L60 70 L55 65 L50 75 L45 65 L40 70 L35 55 C35 25, 50 8, 50 8Z" fill="#FAFAF7" stroke="#2D3E50" stroke-width="2.5" stroke-linejoin="round"/><circle cx="50" cy="38" r="7" fill="#4A6FA5" stroke="#2D3E50" stroke-width="2"/><rect x="38" y="50" width="6" height="6" fill="#C45C4A"/><rect x="44" y="50" width="6" height="6" fill="#FAFAF7" stroke="#2D3E50" stroke-width="0.5"/><rect x="50" y="50" width="6" height="6" fill="#C45C4A"/><rect x="56" y="50" width="6" height="6" fill="#FAFAF7" stroke="#2D3E50" stroke-width="0.5"/><path d="M44 70 L50 88 L56 70" fill="#C78B52" opacity="0.6" stroke="none"/></svg>'

_ROCKET_SVG_SIDEBAR = '<svg width="36" height="36" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M50 8 C50 8, 65 25, 65 55 L60 70 L55 65 L50 75 L45 65 L40 70 L35 55 C35 25, 50 8, 50 8Z" fill="#F5F0E8" stroke="#B0A99A" stroke-width="2.5" stroke-linejoin="round"/><circle cx="50" cy="38" r="7" fill="#4A6FA5" stroke="#B0A99A" stroke-width="2"/><rect x="38" y="50" width="6" height="6" fill="#C45C4A"/><rect x="44" y="50" width="6" height="6" fill="#F5F0E8" stroke="#B0A99A" stroke-width="0.5"/><rect x="50" y="50" width="6" height="6" fill="#C45C4A"/><rect x="56" y="50" width="6" height="6" fill="#F5F0E8" stroke="#B0A99A" stroke-width="0.5"/><path d="M44 70 L50 88 L56 70" fill="#C78B52" opacity="0.5" stroke="none"/></svg>'

_ROCKET_SVG_LARGE = '<svg width="64" height="64" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M50 8 C50 8, 65 25, 65 55 L60 70 L55 65 L50 75 L45 65 L40 70 L35 55 C35 25, 50 8, 50 8Z" fill="#FAFAF7" stroke="#2D3E50" stroke-width="2.5" stroke-linejoin="round"/><circle cx="50" cy="38" r="7" fill="#4A6FA5" stroke="#2D3E50" stroke-width="2"/><rect x="38" y="50" width="6" height="6" fill="#C45C4A"/><rect x="44" y="50" width="6" height="6" fill="#FAFAF7" stroke="#2D3E50" stroke-width="0.5"/><rect x="50" y="50" width="6" height="6" fill="#C45C4A"/><rect x="56" y="50" width="6" height="6" fill="#FAFAF7" stroke="#2D3E50" stroke-width="0.5"/><path d="M44 70 L50 88 L56 70" fill="#C78B52" opacity="0.6" stroke="none"/></svg>'


def inject_objectif_lune_css():
    """Inject custom CSS for the Objectif Lune theme. Call once per page."""
    st.html("""<style>
/* ── Objectif Lune — Ligne Claire Theme ──────────────── */
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}

h1 {
    font-weight: 700 !important;
    letter-spacing: -0.5px !important;
    color: #2D3E50 !important;
}

h2, h3 {
    font-weight: 600 !important;
    color: #2D3E50 !important;
}

[data-testid="stMetric"] {
    background: #FAFAF7;
    border: 1px solid #E8E4DB;
    border-radius: 8px;
    padding: 12px 16px;
    border-left: 3px solid #4A6FA5;
}

[data-testid="stMetricLabel"] {
    font-size: 0.78rem !important;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #7A7A72 !important;
}

[data-testid="stMetricValue"] {
    font-weight: 700 !important;
    color: #2D3E50 !important;
}

/* Sidebar — deep space background */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1C2A3A 0%, #2D3E50 100%) !important;
}

/* Sidebar nav links — bright and readable */
[data-testid="stSidebar"] [data-testid="stSidebarNav"] span {
    color: #F0EDE6 !important;
    font-weight: 500 !important;
}

/* Sidebar headings */
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    color: #F5F0E8 !important;
}

/* Sidebar body text, captions, markdown */
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stMarkdown {
    color: #D0C9BC !important;
}

/* Sidebar labels — slightly dimmer for hierarchy */
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stFileUploader label,
[data-testid="stSidebar"] .stSubheader {
    color: #B0A99A !important;
    font-size: 0.82rem !important;
    text-transform: uppercase;
    letter-spacing: 0.3px;
}

/* Sidebar dividers */
[data-testid="stSidebar"] hr {
    border-color: rgba(240, 237, 230, 0.15) !important;
}

/* Sidebar success/warning/info — keep their own colors readable */
[data-testid="stSidebar"] [data-testid="stAlert"] p {
    color: inherit !important;
}

.stSuccess {
    background-color: rgba(107, 143, 113, 0.08) !important;
    border-color: #6B8F71 !important;
}

.stWarning {
    background-color: rgba(199, 139, 82, 0.08) !important;
    border-color: #C78B52 !important;
}

.stInfo {
    background-color: rgba(74, 111, 165, 0.08) !important;
    border-color: #4A6FA5 !important;
}

.stButton > button[kind="primary"] {
    background-color: #4A6FA5 !important;
    border: none !important;
    border-radius: 6px !important;
    font-weight: 500 !important;
    letter-spacing: 0.3px;
    transition: all 0.2s ease;
}

.stButton > button[kind="primary"]:hover {
    background-color: #3D5D8A !important;
    box-shadow: 0 2px 8px rgba(74, 111, 165, 0.25) !important;
}

.stButton > button[kind="secondary"] {
    border: 1px solid #E8E4DB !important;
    border-radius: 6px !important;
    color: #7A7A72 !important;
    background: transparent !important;
}

[data-testid="stDataFrame"] {
    border: 1px solid #E8E4DB !important;
    border-radius: 6px !important;
}

.stTabs [data-baseweb="tab-list"] {
    gap: 0;
    border-bottom: 2px solid #E8E4DB;
}

.stTabs [data-baseweb="tab"] {
    border-radius: 6px 6px 0 0;
    padding: 8px 20px;
    font-weight: 500;
}

.streamlit-expanderHeader {
    background: #FAFAF7 !important;
    border-radius: 6px !important;
    border: 1px solid #E8E4DB !important;
}

hr {
    border-color: #E8E4DB !important;
    opacity: 0.6;
}

[data-baseweb="select"] {
    border-radius: 6px !important;
}

.js-plotly-plot {
    border-radius: 8px;
}

::-webkit-scrollbar {
    width: 6px;
}
::-webkit-scrollbar-thumb {
    background: #C8C3B8;
    border-radius: 3px;
}
::-webkit-scrollbar-track {
    background: transparent;
}

</style>""")


def render_header(title: str, subtitle: str = ""):
    """Render a themed page header with the Objectif Lune rocket motif."""
    st.html(f'''<div style="display:flex;align-items:center;gap:12px;margin-bottom:4px;padding-bottom:12px;border-bottom:2px solid #E8E4DB;">
{_ROCKET_SVG_HEADER}
<div>
<div style="font-size:1.6rem;font-weight:700;color:#2D3E50;letter-spacing:-0.5px;line-height:1.2;font-family:'DM Sans',sans-serif;">{title}</div>
<div style="font-size:0.82rem;color:#7A7A72;letter-spacing:0.3px;margin-top:2px;font-family:'DM Sans',sans-serif;">{subtitle}</div>
</div>
</div>''')


def render_sidebar_brand():
    """Render the Objectif Lune branding in the sidebar."""
    st.html(f'''<div style="text-align:center;padding:16px 0 8px 0;">
{_ROCKET_SVG_SIDEBAR}
<div style="font-size:0.7rem;text-transform:uppercase;letter-spacing:2px;color:#B0A99A;margin-top:6px;font-family:'DM Sans',sans-serif;">Objectif Lune</div>
</div>''')


def render_welcome_rocket():
    """Render the large centered rocket for the welcome/empty state page."""
    st.html(f'''<div style="text-align:center;padding:40px 20px 20px 20px;">
{_ROCKET_SVG_LARGE}
<div style="font-size:1.1rem;color:#7A7A72;margin-top:16px;font-family:'DM Sans',sans-serif;letter-spacing:0.3px;">Upload CSV exports to begin your mission</div>
</div>''')
