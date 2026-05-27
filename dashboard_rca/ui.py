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
    AVAILABLE_COLOR_SCALES,
    PERSONA_KPI_DEFINITIONS,
    PERSONA_OPTIONS,
    SPATIAL_RESOLUTIONS,
    DESCRIPTIVE_METRICS,
    CSV_PATH,
    DEFAULT_KPI_COLUMNS,
    DEFAULT_MAP_COLUMN,
    DEFAULT_MAP_SCALE,
    DETAIL_COLUMNS,
    SHP_PATH,
)
from .data import (
    aggregate_by_resolution,
    build_risk_ranking,
    compute_overall_vulnerability,
    get_csv_year_options,
    get_index_columns,
    get_prefecture_options,
    load_dashboard_data,
)
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
    with st.sidebar:
        # GROUP 1: User Profile
        st.subheader("👤 User Profile")
        persona = st.radio("Select your role/view", options=PERSONA_OPTIONS, index=0)
        st.divider()

        # GROUP 2: Spatial Filters
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

        # GROUP 3: Data Visualization
        st.subheader("📊 Data Visualization")
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
        st.divider()

        # GROUP 4: Ranking & KPI Configuration
        st.subheader("🎯 Ranking & Summary")
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

    # Aggregate if a higher administrative level is selected
    aggregated_gdf = aggregate_by_resolution(filtered_gdf, resolution_option)

    # Active-data-only path: keep the vulnerability hook as a safe no-op.
    aggregated_gdf = compute_overall_vulnerability(aggregated_gdf)

    # Refresh index columns after potential computation
    index_columns = get_index_columns(aggregated_gdf)
    # Ensure the previously selected map metric is still available after aggregation
    try:
        if selected_map_metric not in index_columns and index_columns:
            selected_map_metric = index_columns[0]
    except NameError:
        # selected_map_metric may not be defined in some execution paths; ignore
        pass

    # === MACRO-INDICATORS (TOP THREE CARDS) ===
    st.title("🇨🇫 CAR Vulnerability Dashboard")
    st.markdown(f"### 🎯 View: *{persona}*")
    st.divider()

    st.subheader(f"Proxy-Based Macro Indicators: {display_name}")
    st.caption("These summary cards are computed from the active proxy layers bundled in this workspace.")
    metric_columns = st.columns(3)

    # Persona-driven KPI selection using only the active proxy bundle.
    persona_metrics = PERSONA_KPI_DEFINITIONS[persona]
    metric_values = []
    for metric_label, candidate_columns in persona_metrics:
        available_columns = [column for column in candidate_columns if column in aggregated_gdf.columns]
        if available_columns:
            metric_value = aggregated_gdf[available_columns].mean(axis=1, skipna=True).mean(skipna=True)
        else:
            metric_value = pd.NA
        metric_values.append((metric_label, metric_value))

    for column, (metric_name, value) in zip(metric_columns, metric_values, strict=True):
        with column:
            metric_text = "N/A" if pd.isna(value) else f"{float(value):.2f}"
            st.metric(metric_name, metric_text)

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

    ranking_level = "subprefecture" if ranking_level_label == "Sub-prefectures" else "cell"
    ranking_gdf = build_risk_ranking(aggregated_gdf, selected_map_metric, level=ranking_level, top_n=int(top_n))

    # === ADVANCED GEOSPATIAL MAP ===
    st.markdown("### Advanced Geospatial Map")
    st.caption(
        "5×5 km grid cells colored by the selected normalized proxy. Light gray indicates missing data. "
        "Red markers show the most at-risk locations for the selected factor."
    )
    choropleth_figure = build_map(
        aggregated_gdf,
        selected_map_metric,
        selected_color_scale,
        hover_columns=selected_kpi_columns,
        highlight_gdf=ranking_gdf,
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

    # === SIDE-BY-SIDE LAYOUT: Ranking + Detail Panel ===
    left_col, right_col = st.columns([1, 1])

    # LEFT COLUMN: Top-Risk-Locations Ranking
    with left_col:
        if selected_map_metric in DESCRIPTIVE_METRICS:
            st.info(
                "Ranking is disabled for purely informational/descriptive metrics "
                "to avoid implying a hierarchy of vulnerability. "
                "Use the map's color scale to explore the spatial distribution of this measure."
            )
        else:
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

    # RIGHT COLUMN: Multidimensional Profile
    with right_col:
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

                    # Location & Context
                    st.markdown("#### Location & Context")
                    prefecture_value = row.get("Prefecture", pd.NA)
                    sous_pref_value = row.get("Sous-prefecture", pd.NA)
                    prefecture_str = str(prefecture_value) if pd.notna(prefecture_value) else "Unknown"
                    sous_pref_str = str(sous_pref_value) if pd.notna(sous_pref_value) else "Unknown"
                    year_val = int(row.get("Year", 0)) if pd.notna(row.get("Year")) else 0

                    st.caption(f"**Prefecture:** {prefecture_str} | **Sous-prefecture:** {sous_pref_str} | **Year:** {year_val}")

                    # Radar Chart
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

    st.divider()

    # === METHODOLOGY & DATA SOURCES (EXPANDER - moved to bottom) ===
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


if __name__ == "__main__":
    main()
