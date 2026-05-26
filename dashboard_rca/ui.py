"""Streamlit UI composition for the dashboard."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from .config import (
    AVAILABLE_COLOR_SCALES,
    CSV_PATH,
    DEFAULT_KPI_COLUMNS,
    DEFAULT_MAP_COLUMN,
    DEFAULT_MAP_SCALE,
    SHP_PATH,
)
from .data import get_index_columns, get_prefecture_options, get_year_options, load_dashboard_data
from .formatting import label_for_column
from .visuals import build_map


st.set_page_config(layout="wide", page_title="CAR Dashboard")


def select_metric(label: str, options: list[str], default_value: str) -> str:
    """Build a sidebar metric selector with a safe fallback default."""

    default_index = options.index(default_value) if default_value in options else 0
    return st.sidebar.selectbox(
        label,
        options=options,
        index=default_index,
        format_func=label_for_column,
    )


def main() -> None:
    """Run the Streamlit application."""

    st.title("CAR Territorial Vulnerability Dashboard")
    st.caption(
        "A decision-support view of territorial vulnerability for public leaders, NGOs, and donors."
    )
    st.info(
        "Use the controls on the left to choose the year, the map color, and the indicators that matter most for your decision."
    )

    try:
        dashboard_gdf = load_dashboard_data(str(CSV_PATH), str(SHP_PATH))
    except Exception as exc:  # pragma: no cover - surfaced directly to the user
        st.error(str(exc))
        st.stop()

    index_columns = get_index_columns(dashboard_gdf)

    if not index_columns:
        st.error("No index columns were found in the dataset.")
        st.stop()

    available_years = get_year_options(dashboard_gdf)

    if available_years:
        selected_year = st.sidebar.selectbox(
            "Year",
            options=available_years,
            index=len(available_years) - 1,
        )
        year_values = pd.to_numeric(dashboard_gdf["Year"], errors="coerce")
        dashboard_gdf = dashboard_gdf[
            year_values.eq(selected_year) | year_values.isna()
        ].copy()

    prefecture_options = get_prefecture_options(dashboard_gdf)

    if not prefecture_options:
        st.error("No prefecture names were found in the dataset.")
        st.stop()

    territory_choice = st.sidebar.selectbox(
        "Filter by territory (optional)",
        options=["All territories"] + prefecture_options,
        index=0,
    )

    st.sidebar.markdown("### Visual encoding")
    selected_map_metric = select_metric(
        "Map color: what should be highlighted?",
        options=index_columns,
        default_value=DEFAULT_MAP_COLUMN,
    )
    selected_color_scale = st.sidebar.selectbox(
        "Color palette",
        options=AVAILABLE_COLOR_SCALES,
        index=AVAILABLE_COLOR_SCALES.index(DEFAULT_MAP_SCALE),
    )

    st.sidebar.markdown("### Quick summary cards")
    selected_kpi_columns = [
        select_metric(
            "Summary card 1",
            options=index_columns,
            default_value=DEFAULT_KPI_COLUMNS[0],
        ),
        select_metric(
            "Summary card 2",
            options=index_columns,
            default_value=DEFAULT_KPI_COLUMNS[1],
        ),
        select_metric(
            "Summary card 3",
            options=index_columns,
            default_value=DEFAULT_KPI_COLUMNS[2],
        ),
    ]

    if territory_choice == "All territories":
        filtered_gdf = dashboard_gdf.copy()
        display_name = "Central African Republic"
    else:
        filtered_gdf = dashboard_gdf[
            dashboard_gdf["Prefecture"].astype(str) == territory_choice
        ].copy()
        display_name = territory_choice

    if filtered_gdf.empty:
        st.warning(f"No spatial features were found for {display_name}.")
        st.stop()

    st.subheader(f"Territory: {display_name}")

    metric_columns = st.columns(3)
    metric_values = [
        (selected_kpi_columns[0], filtered_gdf[selected_kpi_columns[0]].mean(skipna=True)),
        (selected_kpi_columns[1], filtered_gdf[selected_kpi_columns[1]].mean(skipna=True)),
        (selected_kpi_columns[2], filtered_gdf[selected_kpi_columns[2]].mean(skipna=True)),
    ]

    for column, (metric_name, value) in zip(metric_columns, metric_values, strict=True):
        with column:
            metric_text = "N/A" if pd.isna(value) else f"{float(value):.2f}"
            st.metric(label_for_column(metric_name), metric_text)

    st.markdown("### Map of vulnerability")
    choropleth_figure = build_map(
        filtered_gdf,
        selected_map_metric,
        selected_color_scale,
        hover_columns=selected_kpi_columns,
    )
    st.plotly_chart(choropleth_figure, width="stretch")

    st.caption("Hover a cell to inspect its prefecture, sub-prefecture, year, and key indicators.")
