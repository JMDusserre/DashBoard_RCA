"""Streamlit UI composition for the dashboard.

This is the main entry point orchestrating all UI elements. The layout follows
World Bank PRWP 11309 structure:
  1. Header: Project title and reference to World Bank research
  2. Macro-Indicators: Three key metrics (Security, Water, Economic)
  3. Advanced Geospatial Map: Choropleth of selected index across CAR
  4. Multidimensional Profile: Radar chart for detailed cell analysis
  5. Methodology Expander: Explanation of data sources and index definitions

DESIGN PHILOSOPHY:
  - Non-technical language for NGO/donor audience (no "Index_GDP_primary", use "Agriculture")
  - Graceful NaN handling: explain missing data as field insecurity, not failure
  - Caching (@st.cache_data) ensures rapid reruns and filters (critical for interactivity)
  - Detail panel only displays when a grid cell is selected (avoid overwhelming users)
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from .config import (
    AVAILABLE_COLOR_SCALES,
    CSV_PATH,
    DEFAULT_KPI_COLUMNS,
    DEFAULT_MAP_COLUMN,
    DEFAULT_MAP_SCALE,
    DETAIL_COLUMNS,
    SHP_PATH,
)
from .data import build_risk_ranking, get_csv_year_options, get_index_columns, get_prefecture_options, load_dashboard_data
from .formatting import label_for_column, safe_float
from .visuals import build_map, build_radar_chart


st.set_page_config(layout="wide", page_title="RR_WLD 2025-520 Dashboard")


@st.cache_data
def _cached_load(csv_str: str, shp_str: str, selected_year: int):
    """Cache data load to avoid IO on every rerun.
    
    DESIGN DECISION - Caching:
      Streamlit reruns the entire app on every interaction (slider, selectbox, etc.).
      Without caching, we'd reload 20,817 geometries and 1,681 CSV rows on every
      click, making the UI frozen. Caching stores this in memory, providing near-instant
      response times. The decorator key is the tuple of file paths (strings are hashable).
    """
    return load_dashboard_data(csv_str, shp_str, year=selected_year)


def select_metric(label: str, options: list[str], default_value: str) -> str:
    """Build a sidebar metric selector with a safe fallback default.
    
    DESIGN: Use index-based fallback; if default_value is missing (future-proofing
    for dataset changes), use first available option. This prevents crashes.
    """
    default_index = options.index(default_value) if default_value in options else 0
    return st.sidebar.selectbox(
        label,
        options=options,
        index=default_index,
        format_func=label_for_column,
    )


def main() -> None:
    """Run the Streamlit application.
    
    Orchestrates all UI sections: sidebar filters, macro-indicator cards,
    choropleth map, detail panel (radar chart), and methodology reference.
    """
    # === HEADER ===
    st.title("RR_WLD 2025-520 CAR Dashboard")
    st.caption(
        "Interactive dashboard built from the RR_WLD 2025-520 reproducibility package "
        "for the Central African Republic. The active workspace snapshot exposes raw "
        "socioeconomic proxies that are normalized for comparison across territories."
    )
    st.info(
        "📍 The dashboard normalizes the RR_WLD proxy layers to a 0–1 scale so you can "
        "compare grid cells consistently. Missing values remain visible as field reality, "
        "not hidden or imputed data."
    )

    # === DATA LOADING ===
    try:
        available_years = get_csv_year_options(str(CSV_PATH))
        if not available_years:
            st.error("No year data was found in the RR_WLD package CSV.")
            st.stop()

        if "timeline_year" not in st.session_state:
            st.session_state.timeline_year = available_years[-1]

        selected_year = int(st.session_state.timeline_year)
        dashboard_gdf = _cached_load(str(CSV_PATH), str(SHP_PATH), selected_year)
    except Exception as exc:  # pragma: no cover
        st.error(str(exc))
        st.stop()

    index_columns = get_index_columns(dashboard_gdf)
    if not index_columns:
        st.error("No index columns were found in the dataset.")
        st.stop()

    # === SIDEBAR - TERRITORY FILTER ===
    with st.sidebar:
        st.markdown("### Filters")
        prefecture_options = get_prefecture_options(dashboard_gdf)
        if not prefecture_options:
            st.error("No prefecture names were found in the dataset.")
            st.stop()

        # Territory selector: "All territories" shows entire CAR
        territory_choice = st.selectbox(
            "Select territory (optional)",
            options=["All territories"] + prefecture_options,
            index=0,
            help="Filter by prefecture or view the entire country.",
        )

    # === SIDEBAR - MAP VISUAL ENCODING ===
    with st.sidebar:
        st.markdown("### Map Visual Encoding")
        selected_map_metric = select_metric(
            "Which index to highlight?",
            options=index_columns,
            default_value=DEFAULT_MAP_COLUMN,
        )
        selected_color_scale = st.sidebar.selectbox(
            "Color palette",
            options=AVAILABLE_COLOR_SCALES,
            index=AVAILABLE_COLOR_SCALES.index(DEFAULT_MAP_SCALE),
            help="Choose a scale that works for your device/audience.",
        )

    # === SIDEBAR - RISK RANKING CONTROLS ===
    with st.sidebar:
        st.markdown("### Top-10 Risk Ranking")
        ranking_level_label = st.selectbox(
            "Rank by",
            options=["Grid cells (5 km squares)", "Sub-prefectures"],
            index=0,
            help="Choose whether to rank individual cells or grouped sub-prefectures.",
        )
        top_n = st.number_input(
            "How many results?",
            min_value=3,
            max_value=20,
            value=10,
            step=1,
            help="Select how many of the most at-risk locations to show.",
        )

    # === SIDEBAR - KPI CARDS CONFIGURATION ===
    with st.sidebar:
        st.markdown("### Quick Summary Cards")
        st.caption("Top 3 metrics for this territory (mean values)")
        selected_kpi_columns = [
            select_metric(
                "Metric 1",
                options=index_columns,
                default_value=DEFAULT_KPI_COLUMNS[0],
            ),
            select_metric(
                "Metric 2",
                options=index_columns,
                default_value=DEFAULT_KPI_COLUMNS[1],
            ),
            select_metric(
                "Metric 3",
                options=index_columns,
                default_value=DEFAULT_KPI_COLUMNS[2],
            ),
        ]

    # === FILTER GEODATAFRAME TO SELECTED TERRITORY ===
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

    # === MACRO-INDICATORS (TOP THREE CARDS) ===
    st.subheader(f"Macro-Indicators: {display_name}")
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

    ranking_level = "subprefecture" if ranking_level_label == "Sub-prefectures" else "cell"
    ranking_gdf = build_risk_ranking(filtered_gdf, selected_map_metric, level=ranking_level, top_n=int(top_n))

    # === ADVANCED GEOSPATIAL MAP ===
    st.markdown("### Advanced Geospatial Map")
    st.caption(
        "5×5 km grid cells colored by the selected normalized proxy. Light gray indicates missing data. "
        "Red markers show the most at-risk locations for the selected factor."
    )
    choropleth_figure = build_map(
        filtered_gdf,
        selected_map_metric,
        selected_color_scale,
        hover_columns=selected_kpi_columns,
        highlight_gdf=ranking_gdf,
    )
    st.plotly_chart(choropleth_figure, width="stretch")

    st.markdown(f"### Top {int(top_n)} most at-risk locations")
    st.caption(
        f"Lower values mean higher risk. Ranking is based on {label_for_column(selected_map_metric)} and "
        f"the current territory filter."
    )
    ranking_columns = [
        column
        for column in ["rank", "label", "value", "Prefecture", "Sous-prefecture", "id"]
        if column in ranking_gdf.columns
    ]
    if not ranking_gdf.empty:
        ranking_view = ranking_gdf[ranking_columns].copy()
        ranking_view = ranking_view.rename(columns={"value": label_for_column(selected_map_metric)})
        ranking_view[label_for_column(selected_map_metric)] = ranking_view[label_for_column(selected_map_metric)].map(
            lambda value: f"{float(value):.2f}" if pd.notna(value) else "N/A"
        )
        st.dataframe(ranking_view, use_container_width=True, hide_index=True)
    else:
        st.info("No ranked locations were available for the selected factor.")

    st.markdown("### Year timeline")
    st.caption(
        "Use the horizontal timeline to move through the panel years and watch the map update."
    )
    st.select_slider(
        "Year",
        options=available_years,
        key="timeline_year",
        help="Drag across years to update the data slice shown in the map and detail panel.",
    )

    # === MULTIDIMENSIONAL PROFILE (DETAIL PANEL) ===
    st.markdown("### Multidimensional Profile")
    st.caption(
        "Inspect a specific grid cell to see its 5-dimensional vulnerability profile: "
        "primary economy, overall economy, health access, water access, and education access."
    )

    detail_cell_id = st.selectbox(
        "Select a grid cell ID to analyze (optional)",
        options=[""] + sorted(filtered_gdf["id"].dropna().astype(str).unique().tolist()),
        index=0,
        help="Shows detailed radar chart and location info for the selected cell.",
    )

    if detail_cell_id and detail_cell_id != "":
        try:
            detail = filtered_gdf[filtered_gdf["id"].astype(str) == detail_cell_id]
            if not detail.empty:
                row = detail.iloc[0]

                col1, col2 = st.columns([2, 1])

                # LEFT: Radar Chart (5 Dimensions)
                with col1:
                    st.markdown("#### 5-Dimensional Radar Chart")
                    st.caption(
                        "Each dimension extends from 0 (high risk) to 1 (high safety). "
                        "Missing data (field insecurity) shown as -0.1 (off-scale)."
                    )
                    radar_fig = build_radar_chart(row)
                    st.plotly_chart(radar_fig, width="stretch")

                # RIGHT: Location & Context
                with col2:
                    st.markdown("#### Location & Context")
                    prefecture_value = row.get("Prefecture", pd.NA)
                    sous_pref_value = row.get("Sous-prefecture", pd.NA)
                    prefecture_str = str(prefecture_value) if pd.notna(prefecture_value) else "Unknown"
                    sous_pref_str = str(sous_pref_value) if pd.notna(sous_pref_value) else "Unknown"
                    year_val = int(row.get("Year", 0)) if pd.notna(row.get("Year")) else 0

                    st.info(f"**Prefecture:** {prefecture_str}\n\n**Sous-prefecture:** {sous_pref_str}\n\n**Year:** {year_val}")

                    st.warning(
                        "The RR_WLD package snapshot in this workspace does not include the "
                        "separate access/conflict layers used in the published methodology. "
                        "This panel therefore reports the available proxy layers only."
                    )

                    # Show all 5 dimensions in vertical list
                    st.markdown("#### Dimension Values")
                    for col in DETAIL_COLUMNS:
                        val = safe_float(row.get(col, pd.NA))
                        val_str = f"{val:.2f}" if val is not None else "N/A"
                        st.write(f"**{label_for_column(col)}:** {val_str}")

            else:
                st.warning(f"Grid cell ID {detail_cell_id} not found in filtered dataset.")
        except (ValueError, KeyError, IndexError):
            st.error(f"Could not load details for cell ID {detail_cell_id}.")

    # === METHODOLOGY & DATA SOURCES (EXPANDER) ===
    with st.expander("📚 Methodology & Data Sources", expanded=False):
        st.markdown("""
                #### RR_WLD 2025-520 Data Package
        
                This dashboard uses the CAR grid bundle included in the RR_WLD 2025-520
                reproducibility package. The active workspace snapshot contains the base grid
                table, the 5 km shapefile, and socioeconomic proxy variables that can be normalized
                for interactive exploration.
        
                **Normalization rule:** every dashboard metric is mapped to a 0–1 interval so the
                map and radar chart remain comparable across variables with different units.
        
                **Available proxy layers in this workspace snapshot:**
        
                - Nighttime lights intensity and mean brightness
                - Population pressure
                - Built-up, water, forest, cropland, deforestation, and NDVI shares
                - Mine and retail density proxies
        
                **Data reality - NaN handling:**
        
                Missing data are preserved rather than fabricated. When a raw value is not available
                in the package, the corresponding cell stays visible as neutral gray so users can see
                where the data are incomplete.
        
        **Geographic Resolution:**
        
                All data is aggregated to 5×5 km grid cells across CAR. That resolution is fine enough
                for territorial comparison while still responsive in Streamlit.
        
        **Key References:**
        
                - Nighttime lights and land cover proxies from the RR_WLD package inputs
                - CAR administrative boundary grid from `Grid_5km_CFA_v4.shp`
                - Base socioeconomic table from `Base_CAF_v1.csv`
        
        **Data Availability:**
        
                - Year selector reflects the years present in the package input table
                - Territorial names are normalized to `Prefecture` and `Sous-prefecture`
                - Proxy columns are generated at load time so the dashboard stays interactive
        
        #### Dashboard Architecture Notes
        
        This dashboard is built as a Streamlit MVP with modular Python architecture:
        - **config.py:** Centralized constants (bounds, color scales, friendly labels)
        - **data.py:** Data pipeline (CSV + shapefile merge with string ID casting)
        - **formatting.py:** UI helper functions (label translation, NaN handling)
        - **visuals.py:** Plotly rendering (choropleth map, radar chart)
        - **ui.py:** Streamlit orchestration (sidebar filters, detail panel)
        
        **Design Principles:**
        
        - **Robustness:** Graceful NaN handling ensures 47% missing data doesn't crash the app
        - **Clarity:** Non-technical labels ("Security Index" not "Index_Absence_of_conflicts")
        - **Accessibility:** Multiple color scales including colorblind-friendly options
        - **Scalability:** Dynamic index discovery allows new metrics without code changes
        - **Reproducibility:** pinned requirements.txt and containerizable structure
        """)


if __name__ == "__main__":
    main()
