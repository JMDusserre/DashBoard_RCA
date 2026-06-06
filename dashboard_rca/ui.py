"""Streamlit UI composition for the dashboard."""

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
    SHP_PATH,
    UI_TEXTS,
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

def txt(key: str) -> str:
    """Fetch text from UI_TEXTS based on current language state."""
    lang = st.session_state.get("lang", "FR")
    return UI_TEXTS[lang].get(key, key)

@st.cache_data
def _cached_load(csv_str: str, shp_str: str, selected_year: int):
    return load_dashboard_data(csv_str, shp_str, year=selected_year)

def select_metric(label: str, options: list[str], default_value: str) -> str:
    default_index = options.index(default_value) if default_value in options else 0
    return st.sidebar.selectbox(
        label,
        options=options,
        index=default_index,
        format_func=txt, # On utilise la traduction !
    )

def _sidebar_hr():
    """Thin separator that bypasses Streamlit's padded st.divider()."""
    st.markdown(
        "<hr style='margin:0.35rem 0; border:none; border-top:1px solid #e0e0e0'>",
        unsafe_allow_html=True,
    )

def _sidebar_section(label: str) -> None:
    """Compact uppercase section header replacing st.subheader."""
    st.markdown(f"**{label}**", unsafe_allow_html=False)

def _build_sidebar(dashboard_gdf, index_columns: list[str]) -> tuple[str, str, str, str]:
    with st.sidebar:
        # 🌐 LANGUE — label inline du radio, horizontal
        st.session_state.lang = st.radio(
            "🌐 Langue / Language",
            options=["FR", "EN"],
            horizontal=True,
        )

        _sidebar_hr()

        # 👤 PROFIL
        _sidebar_section(txt("user_profile"))
        persona = st.radio(
            "Role",
            options=PERSONA_OPTIONS,
            index=0,
            format_func=txt,
            label_visibility="collapsed",
        )

        _sidebar_hr()

        # 🗺️ FILTRES SPATIAUX
        _sidebar_section(txt("spatial_filters"))
        prefecture_options = get_prefecture_options(dashboard_gdf)
        territory_choice = st.selectbox(
            txt("select_territory"),
            options=["All territories"] + prefecture_options,
            index=0,
            format_func=lambda x: txt("all_territories") if x == "All territories" else x,
        )
        resolution_option = st.selectbox(
            txt("spatial_res"),
            options=SPATIAL_RESOLUTIONS,
            index=0,
            format_func=txt,
        )

        _sidebar_hr()

        # 📊 VISUALISATION
        _sidebar_section(txt("data_vis"))
        selected_map_metric = select_metric(
            txt("highlight_index"),
            options=index_columns,
            default_value=DEFAULT_MAP_COLUMN,
        )

    return persona, territory_choice, resolution_option, selected_map_metric

def _compute_kpi_values(gdf, persona: str, pop_col: str | None = None) -> list[tuple[str, float | None]]:
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
    metric_columns = st.columns(3)
    for column, (metric_name, value) in zip(metric_columns, metric_values, strict=True):
        with column:
            metric_text = "N/A" if pd.isna(value) else f"{float(value):.1f} / 100"
            st.metric(txt(metric_name), metric_text)

def _render_detail_panel(aggregated_gdf) -> None:
    st.markdown(f"### {txt('profile_title')}")
    st.caption(txt("profile_caption"))

    detail_cell_id = st.selectbox(
        txt("select_cell"),
        options=[""] + sorted(aggregated_gdf["id"].dropna().astype(str).unique().tolist()),
        index=0,
    )

    if detail_cell_id and detail_cell_id != "":
        try:
            detail = aggregated_gdf[aggregated_gdf["id"].astype(str) == detail_cell_id]
            if not detail.empty:
                row = detail.iloc[0]
                st.markdown(f"#### {txt('location_context')}")
                prefecture_str = str(row.get("Prefecture", "Unknown")) if pd.notna(row.get("Prefecture")) else "Unknown"
                sous_pref_str = str(row.get("Sous-prefecture", "Unknown")) if pd.notna(row.get("Sous-prefecture")) else "Unknown"
                year_val = int(row.get("Year", 0)) if pd.notna(row.get("Year")) else 0
                st.caption(f"**Prefecture:** {prefecture_str} | **Sous-prefecture:** {sous_pref_str} | **Year:** {year_val}")

                st.markdown(f"#### {txt('radar_title')}")
                st.caption(txt("radar_caption"))
                radar_fig = build_radar_chart(row)
                st.plotly_chart(radar_fig, use_container_width="stretch")
        except Exception:
            pass

def main() -> None:
    try:
        available_years = get_csv_year_options(str(CSV_PATH))
        if not available_years:
            st.error("No year data found.")
            st.stop()

        selected_year = available_years[-1]
        dashboard_gdf = _cached_load(str(CSV_PATH), str(SHP_PATH), selected_year)
    except Exception as exc:
        st.error(str(exc))
        st.stop()

    # Collect ALL Index_* columns from the full (unfiltered) GDF so the sidebar
    # selectbox always proposes every indicator regardless of the current territory
    # or resolution filter. Never reassign this variable afterwards.
    all_index_columns = get_index_columns(dashboard_gdf)
    persona, territory_choice, resolution_option, selected_map_metric = _build_sidebar(
        dashboard_gdf, all_index_columns
    )

    if territory_choice == "All territories":
        filtered_gdf = dashboard_gdf.copy()
        display_name = txt("all_territories")
    else:
        filtered_gdf = dashboard_gdf[dashboard_gdf["Prefecture"].astype(str) == territory_choice].copy()
        display_name = territory_choice

    # Grid resolution: use the territory-filtered GDF directly — no dissolve needed.
    # Prefecture/Sous-prefecture: aggregate (dissolve + mean) by administrative unit.
    if resolution_option.startswith("Secteur"):
        aggregated_gdf = filtered_gdf.copy()
    else:
        aggregated_gdf = aggregate_by_resolution(filtered_gdf, resolution_option)
    aggregated_gdf = compute_overall_vulnerability(aggregated_gdf)

    # Guard: if the metric selected in sidebar isn't in the current aggregation
    # (e.g. column dropped after dissolve), fall back to the first available.
    aggregated_index_columns = get_index_columns(aggregated_gdf)
    if selected_map_metric not in aggregated_index_columns and aggregated_index_columns:
        selected_map_metric = aggregated_index_columns[0]

    # --- TITRES ---
    st.title(txt("title"))
    st.markdown(txt("view").format(txt(persona)))
    st.divider()

    # --- MACRO-INDICATORS ---
    st.subheader(txt("macro_indicators").format(display_name))
    st.caption(txt("macro_caption"))

    pop_col = "population" if "population" in filtered_gdf.columns else (
        "Index_population" if "Index_population" in filtered_gdf.columns else None
    )
    metric_values = _compute_kpi_values(filtered_gdf, persona, pop_col)
    _render_kpi_cards(metric_values)

    # --- OVERALL VULNERABILITY ---
    st.divider()
    st.markdown(f"### {txt('overall_vuln')}")
    st.caption(txt("overall_caption"))
    
    if "Index_Vulnerab_Final" in aggregated_gdf.columns:
        vuln_score = aggregated_gdf["Index_Vulnerab_Final"].mean(skipna=True)
        vuln_text = "N/A" if pd.isna(vuln_score) else f"{float(vuln_score):.1f} / 100"
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            st.metric(txt("territory_score"), vuln_text)

    # --- MAP ---
    st.markdown(f"### {txt('geospatial_map')}")
    st.caption(txt("map_caption"))
    with st.spinner("Generating..."):
        choropleth_figure = build_map(
            aggregated_gdf,
            selected_map_metric,
            hover_columns=[selected_map_metric],
        )
    st.plotly_chart(choropleth_figure, width="stretch")

    _render_detail_panel(aggregated_gdf)

if __name__ == "__main__":
    main()