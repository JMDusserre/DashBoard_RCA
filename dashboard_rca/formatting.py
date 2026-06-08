import pandas as pd

from .config import UI_TEXTS

DEFAULT_LANG = "FR"

# No slash: Plotly JSON-escapes "/" as \u002f, which breaks Streamlit's Plotly parser.
MISSING_VALUE_LABEL = "—"


def label_for_column(column_name: str, lang: str = DEFAULT_LANG) -> str:
    """Translate the column name based on selected language."""
    return UI_TEXTS.get(lang, UI_TEXTS[DEFAULT_LANG]).get(column_name, column_name)


def format_score_value(value: float | None, lang: str = DEFAULT_LANG) -> str:
    """Format a 0–100 score without ``/`` (Plotly escapes slashes as ``\\u002f``, breaking Streamlit JSON)."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return MISSING_VALUE_LABEL
    texts = UI_TEXTS.get(lang, UI_TEXTS[DEFAULT_LANG])
    suffix = texts.get("scale_suffix", "sur 100")
    return f"{float(value):.1f} {suffix}"


def format_metric_value(column: str, value: float | None, lang: str = DEFAULT_LANG) -> str:
    """Format a normalized index value on the 0–100 display scale."""
    return format_score_value(value, lang=lang)


def safe_float(val: object) -> float | None:
    """Convert a value to a float safely, returning None for NaN or invalid inputs."""
    try:
        if pd.isna(val):
            return None
        return float(val)
    except (ValueError, TypeError):
        return None
