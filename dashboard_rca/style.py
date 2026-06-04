import streamlit as st

def inject_custom_css():
    st.markdown("""
    <style>
    /* 1. Largeur sidebar */
    [data-testid="stSidebar"] {
        width: 250px !important; 
    }

    /* 2. Suppression de l'espace entre le bouton de réduction et le reste */
    [data-testid="stSidebar"] section > div {
        padding-top: 0px !important; /* Enlève le padding interne de la section */
    }

    /* 3. Cible spécifiquement le bloc du bouton de langue pour réduire son espace */
    [data-testid="stSidebar"] div[data-testid="stRadio"] {
        margin-bottom: 0px !important;
        padding-bottom: 0px !important;
    }

    /* 4. Titres : on remonte tout */
    [data-testid="stSidebar"] h2, 
    [data-testid="stSidebar"] h3 {
        margin-top: 2px !important; /* Réduit l'espace au-dessus du titre */
        margin-bottom: 2px !important;
        font-size: 0.85rem !important;
    }

    /* 5. Densité générale */
    [data-testid="stSidebar"] div[data-testid="stVerticalBlock"] {
        gap: 0.1rem !important;
    }
    
    [data-testid="stSidebar"] * {
        font-size: 0.8rem !important;
    }
    
    .block-container {
        padding-top: 1rem !important;
        max-width: 95% !important;
    }
    </style>
    """, unsafe_allow_html=True)