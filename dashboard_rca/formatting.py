"""Formatting helpers and small UI utilities.

This module handles label translation and data validation for display.
The key design principle is to make technical data accessible to non-technical
decision-makers (NGO staff, government leaders, donors) without compromising
accuracy.

All functions are defensive: they handle NaN, missing keys, and type errors
gracefully by providing fallback labels rather than crashing.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from .config import FRIENDLY_LABELS


def label_for_column(column_name: str) -> str:
    """Turn a technical column name into a readable dashboard label.
    
    DESIGN: Fallback to title-case auto-formatting if column is not in
    FRIENDLY_LABELS dict. This allows new indices to appear immediately
    in the UI (dynamic naming) without requiring config updates.
    Example: "Index_Access_to_somewhere_new" → "Access To Somewhere New"
    
    Args:
        column_name: Technical name (e.g., "Index_GDP", "Prefecture", "id")
    
    Returns:
        Human-readable label (e.g., "Overall economic activity", "GDP").
    """
    if column_name in FRIENDLY_LABELS:
        return FRIENDLY_LABELS[column_name]

    if column_name.startswith("Index_"):
        return (
            column_name.replace("Index_", "")
            .replace("-", " ")
            .replace("_", " ")
            .replace("&", "and")
            .title()
        )

    return (
        column_name.replace("Index_", "")
        .replace("-", " ")
        .replace("_", " ")
        .replace("&", "and")
        .title()
    )


def safe_float(value: object) -> float | None:
    """Convert a value to float and return None when the value is missing.
    
    DESIGN: Defensive programming ensures NaN/None/invalid types don't crash
    the detail panel. This is critical because ~47% of indices are NaN due to
    field insecurity, and the viewer should see "N/A" gracefully, not errors.
    
    Args:
        value: Any value (float, int, str, NaN, None, etc.)
    
    Returns:
        float if value is numeric, None otherwise.
    """
    if pd.isna(value):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def render_progress_indicator(label: str, value: object) -> None:
    """Render a normalized progress bar or a clear warning when data is missing.
    
    DESIGN: Always explains missing data explicitly ("not available for this grid cell")
    rather than showing blank space or zeros. This maintains trust with decision-makers
    who need to understand which areas have verified data vs. insecure/unreachable.
    
    Args:
        label: Metric name (e.g., "Security Index")
        value: Numeric value (0–1) or NaN/None
    """
    numeric_value = safe_float(value)

    if numeric_value is None:
        st.warning(f"{label} is not available for this grid cell.")
        return

    clipped_value = max(0.0, min(1.0, numeric_value))
    st.write(f"{label}: {clipped_value:.2f}")
    st.progress(int(round(clipped_value * 100)))
