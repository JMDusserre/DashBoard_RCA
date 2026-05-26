"""Formatting helpers and small UI utilities."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from .config import FRIENDLY_LABELS


def label_for_column(column_name: str) -> str:
    """Turn a technical column name into a readable dashboard label."""

    if column_name in FRIENDLY_LABELS:
        return FRIENDLY_LABELS[column_name]

    return (
        column_name.replace("Index_", "")
        .replace("_", " ")
        .replace("&", "and")
        .title()
    )


def safe_float(value: object) -> float | None:
    """Convert a value to float and return None when the value is missing."""

    if pd.isna(value):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def render_progress_indicator(label: str, value: object) -> None:
    """Render a normalized progress bar or a clear warning when data is missing."""

    numeric_value = safe_float(value)

    if numeric_value is None:
        st.warning(f"{label} is not available for this grid cell.")
        return

    clipped_value = max(0.0, min(1.0, numeric_value))
    st.write(f"{label}: {clipped_value:.2f}")
    st.progress(int(round(clipped_value * 100)))
