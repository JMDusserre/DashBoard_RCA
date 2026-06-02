"""Streamlit UI composition for the dashboard.

This is the main entry point orchestrating all UI elements. The layout follows
World Bank PRWP 11309 structure:
    1. Header: Project title and reference to World Bank research
    2. Macro-Indicators: Three proxy-based summary metrics
    3. Advanced Geospatial Map: Choropleth of selected index across CAR
    4. Multidimensional Profile: Radar chart for detailed cell analysis
    5. Methodology Expander: Explanation of proxy sources and index definitions

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
    PERSONA_KPI_DEFINITIONS,
    PERSONA_OPTIONS,
    SPATIAL_RESOLUTIONS,
    HUMAN_CENTRIC_METRICS,
    CSV_PATH,
    DEFAULT_MAP_COLUMN,
    DEFAULT_MAP_SCALE,
    AVAILABLE_COLOR_SCALES,
    SHP_PATH,
)
from .data import (
    aggregate_by_resolution,
    compute_overall_vulnerability,
    get_csv_year_options,
    get_index_columns,
    get_prefecture_options,
    load_dashboard_data,
)
from .formatting import label_for_column
from .style import inject_custom_css
from .visuals import build_map, build_radar_chart


st.set_page_config(layout="wide", page_title="RR_WLD 2025-520 Dashboard")
inject_custom_css()


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


def _build_sidebar(
    dashboard_gdf,
    index_columns: list[str],
) -> tuple[str, str, str, str, str]:
    """Build sidebar controls and return user selections.
    
    Returns:
        Tuple of (persona, territory_choice, resolution_option, selected_map_metric, selected_color_scale)
    """
    with st.sidebar:
        st.subheader("👤 User Profile")
        persona = st.radio("Select your role/view", options=PERSONA_OPTIONS, index=0)
        st.divider()

        st.subheader("🗺️ Spatial Filters")
        prefecture_options = get_prefecture_options(dashboard_gdf)
        if not prefecture_options:
            st.error("No prefecture names were found in the dataset.")
            st.stop()

        territory_choice = st.selectbox(
            "Select territory (optional)",
            options=["All territories"] + prefecture_options,
            index=0,
            help="Filter by prefecture or view the entire country.",
        )

        resolution_option = st.selectbox(
            "Spatial Resolution",
            options=SPATIAL_RESOLUTIONS,
            index=0,
            help="Choose map aggregation level: grid cell, city, sub-prefecture, or prefecture.",
        )
        st.divider()

        st.subheader("📊 Data Visualization")
        selected_map_metric = select_metric(
            "Which index to highlight?",
            options=index_columns,
            default_value=DEFAULT_MAP_COLUMN,
        )
        
        # Color palette selector
        selected_color_scale = st.selectbox(
            "Color palette",
            options=AVAILABLE_COLOR_SCALES,
            index=AVAILABLE_COLOR_SCALES.index(DEFAULT_MAP_SCALE),
            help="Choose a color palette for the map visualization.",
        )
    return persona, territory_choice, resolution_option, selected_map_metric, selected_color_scale


def _compute_kpi_values(
    gdf,
    persona: str,
    pop_col: str | None = None,
) -> list[tuple[str, float | None]]:
    """Compute persona-driven KPI values with population masking.
    
    Returns:
        List of (metric_label, value) tuples.
    """
    persona_metrics = PERSONA_KPI_DEFINITIONS[persona]
    metric_values = []

    for metric_label, candidate_columns in persona_metrics:
        available_columns = [col for col in candidate_columns if col in gdf.columns]
        if not available_columns:
            metric_values.append((metric_label, pd.NA))
            continue

        col_means = []
        for col in available_columns:
            if col in HUMAN_CENTRIC_METRICS:
                if pop_col is not None:
                    mask = pd.to_numeric(gdf.get(pop_col, pd.Series()), errors="coerce") > 0
                    valid = gdf[mask]
                    val = pd.to_numeric(valid[col], errors="coerce").mean(skipna=True) if not valid.empty else pd.NA
                else:
                    val = pd.to_numeric(gdf[col], errors="coerce").mean(skipna=True)
            else:
                val = pd.to_numeric(gdf[col], errors="coerce").mean(skipna=True)
            col_means.append(val)

        metric_value = pd.Series(col_means, dtype="float64").mean(skipna=True)
        metric_values.append((metric_label, metric_value))

    return metric_values


def _render_kpi_cards(metric_values: list[tuple[str, float | None]]) -> None:
    """Render three macro-indicator KPI cards."""
    metric_columns = st.columns(3)
    for column, (metric_name, value) in zip(metric_columns, metric_values, strict=True):
        with column:
            metric_text = "N/A" if pd.isna(value) else f"{float(value):.2f}"
            st.metric(metric_name, metric_text)


def _render_detail_panel(aggregated_gdf) -> None:
    """Render the multidimensional profile detail panel."""
    st.markdown("### Multidimensional Profile")
    st.caption("Inspect a grid cell to see its 5-dimensional proxy profile.")

    detail_cell_id = st.selectbox(
        "Select a grid cell ID to analyze (optional)",
        options=[""] + sorted(aggregated_gdf["id"].dropna().astype(str).unique().tolist()),
        index=0,
        help="Shows detailed radar chart and location info for the selected cell.",
    )

    if detail_cell_id and detail_cell_id != "":
        try:
            detail = aggregated_gdf[aggregated_gdf["id"].astype(str) == detail_cell_id]
            if not detail.empty:
                row = detail.iloc[0]
                st.markdown("#### Location & Context")
                prefecture_str = str(row.get("Prefecture", "Unknown")) if pd.notna(row.get("Prefecture")) else "Unknown"
                sous_pref_str = str(row.get("Sous-prefecture", "Unknown")) if pd.notna(row.get("Sous-prefecture")) else "Unknown"
                year_val = int(row.get("Year", 0)) if pd.notna(row.get("Year")) else 0
                st.caption(f"**Prefecture:** {prefecture_str} | **Sous-prefecture:** {sous_pref_str} | **Year:** {year_val}")

                st.markdown("#### 5-Dimensional Proxy Radar Chart")
                st.caption(
                    "Each dimension extends from 0 (high risk) to 1 (high safety). "
                    "Missing data (field insecurity) shown as -0.1 (off-scale)."
                )
                radar_fig = build_radar_chart(row)
                st.plotly_chart(radar_fig, use_container_width=True)
            else:
                st.warning(f"Grid cell ID {detail_cell_id} not found in filtered dataset.")
        except (ValueError, KeyError, IndexError):
            st.error(f"Could not load details for cell ID {detail_cell_id}.")


def _render_methodology_section() -> None:
    """Render the methodology and data sources expandable sections."""
    with st.expander("📖 Read Methodology, Context & How to Use this Dashboard", expanded=False):
        st.markdown("#### 📍 Dashboard Context")
        st.markdown(
            "Interactive dashboard built from the RR_WLD 2025-520 reproducibility package "
            "for the Central African Republic. The workspace leverages alternative data sources "
            "(satellite imagery, nighttime lights, geocoded infrastructure) to bridge gaps in traditional census data."
        )
        st.info(
            "📍 Alternative data sources (satellite imagery, nighttime lights, geocoded infrastructure) "
            "are explicitly leveraged to bridge gaps caused by conflict and institutional fragility."
        )

    with st.expander("📚 Data Sources & Technical Details", expanded=False):
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

Data can be explored at multiple spatial resolutions. Use the "Spatial Resolution" selector in the sidebar
to dynamically aggregate grid cells into City (Admin 3), Sous-prefecture (Admin 2), or Prefecture (Admin 1) levels.

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


def main() -> None:
    """Run the Streamlit application.
    
    Orchestrates all UI sections: sidebar filters, macro-indicator cards,
    choropleth map, detail panel (radar chart), and methodology reference.
    Split into focused helper functions for maintainability.
    """
    # === DATA LOADING (Before UI so we can use persona in title) ===
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

    # === SIDEBAR - Organize into logical groups ===
    persona, territory_choice, resolution_option, selected_map_metric, selected_color_scale = _build_sidebar(
        dashboard_gdf, index_columns
    )

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

    # Aggregate if a higher administrative level is selected
    aggregated_gdf = aggregate_by_resolution(filtered_gdf, resolution_option)
    aggregated_gdf = compute_overall_vulnerability(aggregated_gdf)

    # Refresh index columns after potential computation
    index_columns = get_index_columns(aggregated_gdf)
    if selected_map_metric not in index_columns and index_columns:
        selected_map_metric = index_columns[0]

    # === TITLE & HEADER ===
    st.title("🇨🇫 CAR Vulnerability Dashboard")
    st.markdown(f"### 🎯 View: *{persona}*")
    st.divider()

    # === MACRO-INDICATORS (TOP THREE CARDS) ===
    st.subheader(f"Proxy-Based Macro Indicators: {display_name}")
    st.caption("These summary cards are computed from the active proxy layers bundled in this workspace.")

    pop_col = "population" if "population" in filtered_gdf.columns else (
        "Index_population" if "Index_population" in filtered_gdf.columns else None
    )
    metric_values = _compute_kpi_values(filtered_gdf, persona, pop_col)
    _render_kpi_cards(metric_values)

    # === OVERALL VULNERABILITY SCORE ===
    st.divider()
    st.markdown("### Overall Vulnerability Score")
    st.caption("Composite proxy index combining access, activity, and exposure layers (0=Low Risk, 1=High Risk).")
    
    if "Index_Vulnerab_Final" in aggregated_gdf.columns:
        vuln_score = aggregated_gdf["Index_Vulnerab_Final"].mean(skipna=True)
        vuln_text = "N/A" if pd.isna(vuln_score) else f"{float(vuln_score):.2f}"
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            st.metric("Territory Vulnerability", vuln_text)
    else:
        st.info("Overall vulnerability score not available in the current dataset.")

    # === ADVANCED GEOSPATIAL MAP ===
    st.markdown("### Advanced Geospatial Map")
    st.caption(
        "5×5 km grid cells colored by the selected normalized proxy. Light gray indicates missing data. "
    )
    choropleth_figure = build_map(
        aggregated_gdf,
        selected_map_metric,
        hover_columns=[selected_map_metric],
        color_scale=selected_color_scale,
    )
    st.plotly_chart(choropleth_figure, width="stretch")

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

    # === DETAIL PANEL ===
    _render_detail_panel(aggregated_gdf)

    st.divider()

    # === METHODOLOGY & DATA SOURCES ===
    _render_methodology_section()


if __name__ == "__main__":
    main()
