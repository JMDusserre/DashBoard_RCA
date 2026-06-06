import streamlit as st

def inject_custom_css():
    st.markdown("""
    <style>
    /* ── SIDEBAR : padding du conteneur racine ──────────────────────────── */
    [data-testid="stSidebar"] > div:first-child {
        padding-top: 1rem !important;
        padding-bottom: 1rem !important;
    }

    /* ── SIDEBAR : espacement vertical entre blocs ──────────────────────── */
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
        gap: 0.5rem !important;
    }

    /* ── SIDEBAR : radio et selectbox — juste supprimer le surplus bas ──── */
    [data-testid="stSidebar"] .stRadio,
    [data-testid="stSidebar"] .stSelectbox {
        margin-bottom: 0.15rem !important;
    }

    /* ── SIDEBAR : titres de section (markdown **...**) ─────────────────── */
    [data-testid="stSidebar"] strong {
        font-size: 0.85rem !important;
        color: #555 !important;
    }

    /* ── SIDEBAR : séparateurs hr inline ────────────────────────────────── */
    [data-testid="stSidebar"] hr {
        margin-top: 0.5rem !important;
        margin-bottom: 0.5rem !important;
        border-color: #e0e0e0 !important;
    }

    /* ── SIDEBAR : police générale légèrement réduite ───────────────────── */
    [data-testid="stSidebar"] * {
        font-size: 0.9rem !important;
    }

    /* ── CONTENU PRINCIPAL ───────────────────────────────────────────────── */
    .block-container {
        padding-top: 1rem !important;
        max-width: 95% !important;
    }
    </style>
    """, unsafe_allow_html=True)
