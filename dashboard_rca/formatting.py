import pandas as pd
import streamlit as st
from .config import UI_TEXTS

def label_for_column(column_name: str) -> str:
    """Translate the column name based on selected language."""
    lang = st.session_state.get("lang", "FR")
    return UI_TEXTS[lang].get(column_name, column_name)

def safe_float(val: object) -> float | None:
    """Convert a value to a float safely, returning None for NaN or invalid inputs."""
    try:
        if pd.isna(val):
            return None
        return float(val)
    except (ValueError, TypeError):
        return None