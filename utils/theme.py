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
    st.html("""<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&display=swap" rel="stylesheet">
<style>
/* ══ Objectif Lune — Ligne Claire Theme ══════════════════
   Tintin-inspired minimalist design system.
   Every rule uses !important to override Streamlit Cloud defaults.
   ═══════════════════════════════════════════════════════════ */

/* ── Root containers ───────────────────────────────────── */
[data-testid="stAppViewContainer"],
[data-testid="stAppViewContainer"] > section,
.stMainBlockContainer,
[data-testid="stMainBlockContainer"],
.stApp {
    background-color: #FAFAF7 !important;
    font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

/* ── Typography (narrow selector — avoids overriding Material Icons) */
html, body,
p, td, th, label,
.stMarkdown, .stText,
[data-testid="stMetricLabel"],
[data-testid="stMetricValue"],
[data-testid="stCaptionContainer"],
[data-testid="stExpander"] summary span:not(.material-symbols-rounded),
[data-testid="stSidebar"] [data-testid="stSidebarNav"] span:not(.material-symbols-rounded) {
    font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

/* ── Protect Material Icons from font override ───────── */
.material-symbols-rounded,
.material-icons,
[data-testid="stIcon"] {
    font-family: 'Material Symbols Rounded', 'Material Icons' !important;
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

h4, h5, h6 {
    font-weight: 600 !important;
    color: #2D3E50 !important;
}

/* ── Metric cards ──────────────────────────────────────── */
[data-testid="stMetric"] {
    background: #FAFAF7 !important;
    border: 1px solid #E8E4DB !important;
    border-radius: 8px !important;
    padding: 14px 18px !important;
    border-left: 4px solid #4A6FA5 !important;
    box-shadow: 0 1px 4px rgba(45, 62, 80, 0.06) !important;
    transition: all 0.2s ease !important;
}
[data-testid="stMetric"]:hover {
    box-shadow: 0 3px 12px rgba(74, 111, 165, 0.14) !important;
    transform: translateY(-1px) !important;
}

[data-testid="stMetricLabel"] {
    font-size: 0.78rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.5px !important;
    color: #636359 !important;
    white-space: normal !important;
    overflow-wrap: break-word !important;
    word-break: break-word !important;
    line-height: 1.3 !important;
}

[data-testid="stMetricValue"] {
    font-weight: 700 !important;
    color: #2D3E50 !important;
    white-space: normal !important;
    overflow-wrap: break-word !important;
    word-break: break-word !important;
    font-size: clamp(1rem, 2vw, 1.5rem) !important;
    line-height: 1.25 !important;
}

[data-testid="stMetricDelta"] {
    font-size: 0.82rem !important;
}

/* ── Sidebar — deep space gradient ─────────────────────── */
[data-testid="stSidebar"],
[data-testid="stSidebar"] > div:first-child {
    background: linear-gradient(180deg, #1C2A3A 0%, #2D3E50 100%) !important;
}

[data-testid="stSidebar"] [data-testid="stSidebarNav"] span {
    color: #F0EDE6 !important;
    font-weight: 500 !important;
}

[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    color: #F5F0E8 !important;
}

[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stMarkdown {
    color: #D0C9BC !important;
}

[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stFileUploader label,
[data-testid="stSidebar"] .stSubheader {
    color: #B0A99A !important;
    font-size: 0.82rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.3px !important;
}

[data-testid="stSidebar"] hr {
    border-color: rgba(240, 237, 230, 0.15) !important;
}

[data-testid="stSidebar"] [data-testid="stAlert"] p {
    color: inherit !important;
}

/* ── Alerts ────────────────────────────────────────────── */
.stSuccess, [data-testid="stAlert"][data-baseweb*="positive"] {
    background-color: rgba(107, 143, 113, 0.08) !important;
    border-color: #6B8F71 !important;
}

.stWarning, [data-testid="stAlert"][data-baseweb*="warning"] {
    background-color: rgba(199, 139, 82, 0.08) !important;
    border-color: #C78B52 !important;
}

.stInfo, [data-testid="stAlert"][data-baseweb*="info"] {
    background-color: rgba(74, 111, 165, 0.08) !important;
    border-color: #4A6FA5 !important;
}

.stError, [data-testid="stAlert"][data-baseweb*="negative"] {
    background-color: rgba(196, 92, 74, 0.08) !important;
    border-color: #C45C4A !important;
}

/* ── Buttons ───────────────────────────────────────────── */
.stButton > button[kind="primary"] {
    background-color: #4A6FA5 !important;
    color: #FFFFFF !important;
    border: 1.5px solid #4A6FA5 !important;
    border-radius: 6px !important;
    font-weight: 500 !important;
    letter-spacing: 0.3px !important;
    transition: all 0.2s ease !important;
}
.stButton > button[kind="primary"]:hover {
    background-color: #FAFAF7 !important;
    color: #4A6FA5 !important;
    border: 1.5px solid #4A6FA5 !important;
    box-shadow: none !important;
}

.stButton > button[kind="secondary"] {
    border: 1px solid #E8E4DB !important;
    border-radius: 6px !important;
    color: #636359 !important;
    background: transparent !important;
    transition: all 0.2s ease !important;
}
.stButton > button[kind="secondary"]:hover {
    background: #2D3E50 !important;
    color: #FAFAF7 !important;
    border-color: #2D3E50 !important;
}

/* ── Data tables ───────────────────────────────────────── */
[data-testid="stDataFrame"] {
    border: 1px solid #E8E4DB !important;
    border-radius: 6px !important;
}
[data-testid="stDataFrame"] thead tr th {
    background: #2D3E50 !important;
    color: #F0EDE6 !important;
    font-weight: 500 !important;
    text-transform: uppercase !important;
    font-size: 0.78rem !important;
    letter-spacing: 0.3px !important;
}
[data-testid="stDataFrame"] tbody tr:nth-child(even) {
    background: #F5F0E8 !important;
}
[data-testid="stDataFrame"] tbody tr:hover {
    background: #E8E4DB !important;
}

/* ── Tabs ──────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    gap: 0 !important;
    border-bottom: 2px solid #E8E4DB !important;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 6px 6px 0 0 !important;
    padding: 8px 20px !important;
    font-weight: 500 !important;
    color: #636359 !important;
}
.stTabs [data-baseweb="tab"][aria-selected="true"] {
    border-bottom: 3px solid #4A6FA5 !important;
    color: #2D3E50 !important;
    font-weight: 600 !important;
}

/* ── Expanders ─────────────────────────────────────────── */
[data-testid="stExpander"] {
    border: 1px solid #E8E4DB !important;
    border-radius: 8px !important;
    overflow: hidden !important;
}
[data-testid="stExpander"] summary,
.streamlit-expanderHeader {
    background: #FAFAF7 !important;
    font-weight: 500 !important;
    color: #2D3E50 !important;
    border-radius: 8px !important;
    border: none !important;
}
[data-testid="stExpander"] summary:hover {
    color: #4A6FA5 !important;
}

/* ── Horizontal rules ──────────────────────────────────── */
hr {
    border: none !important;
    border-top: 1.5px solid #E8E4DB !important;
    margin: 1.5rem 0 !important;
    opacity: 1 !important;
}

/* ── Form inputs ───────────────────────────────────────── */
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stTextArea"] textarea {
    border: 1px solid #E8E4DB !important;
    border-radius: 6px !important;
    font-family: 'DM Sans', -apple-system, sans-serif !important;
    color: #2D3E50 !important;
}
[data-testid="stTextInput"] input:focus,
[data-testid="stNumberInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {
    border-color: #4A6FA5 !important;
    box-shadow: 0 0 0 1px #4A6FA5 !important;
}

/* ── Selectbox / Multiselect ───────────────────────────── */
[data-baseweb="select"] {
    border-radius: 6px !important;
}
[data-baseweb="select"] > div {
    border-color: #E8E4DB !important;
}
[data-baseweb="select"] > div:focus-within {
    border-color: #4A6FA5 !important;
    box-shadow: 0 0 0 1px #4A6FA5 !important;
}
[data-baseweb="menu"] li:hover {
    background-color: #F0EDE6 !important;
}

/* ── Radio buttons ─────────────────────────────────────── */
[data-testid="stRadio"] label[data-selected="true"] {
    color: #4A6FA5 !important;
    font-weight: 600 !important;
}

/* ── Slider ────────────────────────────────────────────── */
[data-testid="stSlider"] [role="slider"] {
    background-color: #4A6FA5 !important;
}
[data-testid="stSlider"] [data-testid="stThumbValue"] {
    color: #2D3E50 !important;
    font-weight: 600 !important;
}

/* ── Plotly charts ─────────────────────────────────────── */
.js-plotly-plot {
    border-radius: 8px !important;
}

/* ── Scrollbar ─────────────────────────────────────────── */
::-webkit-scrollbar {
    width: 6px !important;
}
::-webkit-scrollbar-thumb {
    background: #C8C3B8 !important;
    border-radius: 3px !important;
}
::-webkit-scrollbar-track {
    background: transparent !important;
}

/* ── Caption text ──────────────────────────────────────── */
[data-testid="stCaptionContainer"] {
    color: #7A7A72 !important;
    font-size: 0.82rem !important;
}

/* ── Date input ────────────────────────────────────────── */
[data-testid="stDateInput"] input {
    border: 1px solid #E8E4DB !important;
    border-radius: 6px !important;
    font-family: 'DM Sans', -apple-system, sans-serif !important;
}
[data-testid="stDateInput"] input:focus {
    border-color: #4A6FA5 !important;
    box-shadow: 0 0 0 1px #4A6FA5 !important;
}

</style>
<script>
// Rename "app" sidebar nav label to "Performance Command Center"
(function renameAppLabel() {
    const observer = new MutationObserver(function() {
        const navLinks = document.querySelectorAll('[data-testid="stSidebarNav"] a span');
        navLinks.forEach(function(span) {
            if (span.textContent.trim().toLowerCase() === 'app') {
                span.textContent = 'Performance Command Center';
            }
        });
    });
    observer.observe(document.body, {childList: true, subtree: true});
    setTimeout(renameAppLabel, 500);
})();
</script>""")


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


def render_empty_state(message: str, icon: str = ""):
    """Render a themed empty state with optional icon."""
    st.html(f'''<div style="text-align:center;padding:40px 20px;color:#7A7A72;font-family:'DM Sans',sans-serif;">
<div style="font-size:2rem;margin-bottom:8px;">{icon}</div>
<div style="font-size:0.95rem;letter-spacing:0.3px;">{message}</div>
</div>''')


def render_card(title: str, content: str, border_color: str = "#4A6FA5"):
    """Render a themed card with left accent border."""
    st.html(f'''<div style="background:#FAFAF7;border:1px solid #E8E4DB;border-radius:8px;
padding:16px 20px;border-left:3px solid {border_color};margin-bottom:8px;">
<div style="font-weight:600;color:#2D3E50;font-size:0.95rem;margin-bottom:6px;font-family:'DM Sans',sans-serif;">{title}</div>
<div style="color:#7A7A72;font-size:0.88rem;font-family:'DM Sans',sans-serif;">{content}</div>
</div>''')


def themed_spinner_message(context: str) -> str:
    """Return a themed spinner message based on context."""
    messages = {
        "forecast": "Calculating trajectories...",
        "export": "Assembling mission report...",
        "analysis": "Running diagnostic scan...",
        "pattern": "Scanning historical records...",
        "loading": "Preparing instruments...",
    }
    return messages.get(context, "Processing...")
