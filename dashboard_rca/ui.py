"""Streamlit UI composition for the dashboard."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from .config import (
    APP_ROOT,
    INDICATOR_HIERARCHY,
    PERSONA_KPI_DEFINITIONS,
    PERSONA_OPTIONS,
    PERSONA_RADAR_COLUMNS,
    SPATIAL_RESOLUTIONS,
    HUMAN_CENTRIC_METRICS,
    CSV_PATH,
    DATA_YEAR,
    DEFAULT_MAP_COLUMN,
    SHP_PATH,
    UI_TEXTS,
)
from .data import (
    aggregate_by_resolution,
    get_index_columns,
    get_prefecture_options,
    is_valid_admin_label,
    load_dashboard_data,
)
from .formatting import format_metric_value, format_score_value, label_for_column
from .style import inject_custom_css
from .visuals import build_map, build_radar_chart

ZONE_KEY_SEP = " · "

st.set_page_config(layout="wide", page_title="RR_WLD 2025-520 Dashboard", initial_sidebar_state="expanded")
inject_custom_css()


def txt(key: str) -> str:
    """Fetch text from UI_TEXTS based on current language state."""
    lang = st.session_state.get("lang", "FR")
    return UI_TEXTS[lang].get(key, key)


def _current_lang() -> str:
    return st.session_state.get("lang", "FR")


@st.cache_data(ttl=3600)
def _cached_load(csv_str: str, shp_str: str, selected_year: int):
    return load_dashboard_data(csv_str, shp_str, year=selected_year)


@st.cache_data(ttl=3600)
def _cached_aggregation(
    _dashboard_gdf,
    territory: str,
    resolution: str,
    year: int,
):
    """Cache territory filter + dissolve; GDF excluded from cache key (underscore)."""
    if territory == "All territories":
        filtered = _dashboard_gdf.copy()
    else:
        filtered = _dashboard_gdf[_dashboard_gdf["Prefecture"] == territory].copy()

    if resolution.startswith("Secteur"):
        return filtered, filtered.copy()

    return filtered, aggregate_by_resolution(filtered, resolution)


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_build_map(
    _gdf,
    metric: str,
    resolution: str,
    territory: str,
    year: int,
    lang: str,
    height: int = 700,
):
    """Cache Plotly choropleth keyed on scalar filter arguments including language."""
    return build_map(
        _gdf,
        metric,
        hover_columns=[metric],
        resolution=resolution,
        lang=lang,
        height=height,
    )


def _inhabited_mask(gdf, pop_col: str | None) -> pd.Series:
    """Cells with population > 0, or — when no pop column — any human-centric data."""
    if pop_col is not None:
        return pd.to_numeric(gdf.get(pop_col, pd.Series(dtype=float)), errors="coerce") > 0

    human_cols = [c for c in HUMAN_CENTRIC_METRICS if c in gdf.columns]
    if human_cols:
        return (
            gdf[human_cols]
            .apply(lambda col: pd.to_numeric(col, errors="coerce"))
            .notna()
            .any(axis=1)
        )

    return pd.Series(True, index=gdf.index)


def _is_admin_resolution(resolution: str) -> bool:
    return not resolution.startswith("Secteur") and not resolution.startswith("Grid")


def _map_caption(resolution: str) -> str:
    return txt("map_caption_admin") if _is_admin_resolution(resolution) else txt("map_caption_secteur")


def _profile_caption(resolution: str) -> str:
    return txt("profile_caption_admin") if _is_admin_resolution(resolution) else txt("profile_caption_secteur")


def _macro_caption(resolution: str) -> str:
    if _is_admin_resolution(resolution):
        return txt("macro_caption_admin")
    return txt("macro_caption")


def _detail_zone_column(resolution: str) -> str:
    if resolution.startswith("Prefecture"):
        return "Prefecture"
    if resolution.startswith("Sous-prefecture"):
        return "Sous-prefecture"
    if resolution.startswith("Commune"):
        return "admin3name"
    return "id"


def _format_detail_zone_key(row: pd.Series, resolution: str) -> str:
    if resolution.startswith("Commune"):
        commune = str(row.get("admin3name", ""))
        prefecture = str(row.get("Prefecture", ""))
        return f"{commune}{ZONE_KEY_SEP}{prefecture}"
    zone_col = _detail_zone_column(resolution)
    return str(row.get(zone_col, ""))


def _filter_detail_rows(aggregated_gdf: pd.DataFrame, resolution: str, detail_key: str) -> pd.DataFrame:
    if resolution.startswith("Commune"):
        if ZONE_KEY_SEP not in detail_key:
            return aggregated_gdf.iloc[0:0]
        commune, prefecture = detail_key.split(ZONE_KEY_SEP, 1)
        return aggregated_gdf[
            aggregated_gdf["admin3name"].astype(str).eq(commune)
            & aggregated_gdf["Prefecture"].astype(str).eq(prefecture)
        ]
    zone_col = _detail_zone_column(resolution)
    return aggregated_gdf[aggregated_gdf[zone_col].astype(str) == detail_key]


def _detail_zone_options(aggregated_gdf, resolution: str) -> list[str]:
    if resolution.startswith("Commune"):
        valid = aggregated_gdf[aggregated_gdf["admin3name"].map(is_valid_admin_label)]
        keys = {_format_detail_zone_key(row, resolution) for _, row in valid.iterrows()}
        return sorted(keys)

    zone_col = _detail_zone_column(resolution)
    if zone_col == "id":
        return sorted(aggregated_gdf["id"].dropna().astype(str).unique().tolist())

    values = aggregated_gdf[zone_col].dropna().astype(str).unique().tolist()
    return sorted(v for v in values if is_valid_admin_label(v))


def _sidebar_lang() -> None:
    """Render the language switcher at the top of the sidebar."""
    with st.sidebar:
        st.session_state.lang = st.radio(
            "🌐 Langue / Language",
            options=["FR", "EN"],
            horizontal=True,
        )


def select_metric(label: str, options: list[str], default_value: str) -> str:
    default_index = options.index(default_value) if default_value in options else 0
    return st.sidebar.selectbox(
        label,
        options=options,
        index=default_index,
        format_func=txt,
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
        _sidebar_hr()

        _sidebar_section(txt("user_profile"))
        persona = st.radio(
            "Role",
            options=PERSONA_OPTIONS,
            index=0,
            format_func=txt,
            label_visibility="collapsed",
        )

        _sidebar_hr()

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

        _sidebar_section(txt("data_vis"))

        # Build a hierarchy-ordered list from INDICATOR_HIERARCHY; orphan columns
        # (not referenced in the dict) are appended at the bottom.
        ordered_options: list[str] = []
        is_child_map: dict[str, bool] = {}

        for parent, children in INDICATOR_HIERARCHY.items():
            if parent in index_columns:
                ordered_options.append(parent)
                is_child_map[parent] = False
            for child in children:
                if child in index_columns:
                    ordered_options.append(child)
                    is_child_map[child] = True

        for col in index_columns:
            if col not in ordered_options:
                ordered_options.append(col)
                is_child_map[col] = False

        # \u2003 (em space) preserves visual indentation in browser <select> elements
        # where regular spaces are collapsed by HTML rendering.
        def format_hierarchy(col: str) -> str:
            label = txt(col)
            return f"\u2003↳ {label}" if is_child_map.get(col, False) else label

        default_index = (
            ordered_options.index(DEFAULT_MAP_COLUMN)
            if DEFAULT_MAP_COLUMN in ordered_options
            else 0
        )
        selected_map_metric = st.sidebar.selectbox(
            txt("highlight_index"),
            options=ordered_options,
            index=default_index,
            format_func=format_hierarchy,
        )

        _sidebar_hr()
        _sidebar_section(txt("updates_section"))
        with st.sidebar.expander(txt("updates_expander")):
            _changelog_path = APP_ROOT / "CHANGELOG.md"
            if _changelog_path.exists():
                st.markdown(_changelog_path.read_text(encoding="utf-8"))
            else:
                st.caption("CHANGELOG.md not found.")

        _sidebar_hr()
        _sidebar_section(txt("feedback_section"))
        _mailto = (
            f"mailto:jmddusserre@gmail.com"
            f"?subject={txt('feedback_subject').replace(' ', '%20')}"
            f"&body={txt('feedback_body').replace(chr(10), '%0A').replace(' ', '%20')}"
        )
        st.sidebar.markdown(f"[{txt('feedback_button')}]({_mailto})")

    return persona, territory_choice, resolution_option, selected_map_metric


def _kpi_source_gdf(
    filtered_gdf: pd.DataFrame,
    aggregated_gdf: pd.DataFrame,
    resolution: str,
) -> pd.DataFrame:
    """Use the same spatial grain as the map for macro KPI cards."""
    return aggregated_gdf if _is_admin_resolution(resolution) else filtered_gdf


def _compute_kpi_values(
    gdf,
    persona: str,
    pop_col: str | None = None,
    *,
    use_inhabited_mask: bool = True,
) -> list[tuple[str, float | None, str | None]]:
    persona_metrics = PERSONA_KPI_DEFINITIONS[persona]
    inhabited = _inhabited_mask(gdf, pop_col) if use_inhabited_mask else pd.Series(True, index=gdf.index)
    metric_values = []
    for metric_label, candidate_columns in persona_metrics:
        available_columns = [col for col in candidate_columns if col in gdf.columns]
        if not available_columns:
            metric_values.append((metric_label, pd.NA, None))
            continue
        col_means = []
        for col in available_columns:
            if use_inhabited_mask and col in HUMAN_CENTRIC_METRICS:
                valid = gdf[inhabited]
                val = (
                    pd.to_numeric(valid[col], errors="coerce").mean(skipna=True)
                    if not valid.empty
                    else pd.NA
                )
            else:
                val = pd.to_numeric(gdf[col], errors="coerce").mean(skipna=True)
            col_means.append(val)
        metric_value = pd.Series(col_means, dtype="float64").mean(skipna=True)
        source_col = available_columns[0] if len(available_columns) == 1 else None
        metric_values.append((metric_label, metric_value, source_col))
    return metric_values


def _render_kpi_cards(metric_values: list[tuple[str, float | None, str | None]]) -> None:
    lang = _current_lang()
    metric_columns = st.columns(3)
    for column, (metric_name, value, source_col) in zip(metric_columns, metric_values):
        with column:
            metric_text = (
                format_metric_value(source_col or "", value, lang=lang)
                if source_col
                else format_score_value(value, lang=lang)
            )
            st.metric(txt(metric_name), metric_text)


def _zone_location_caption(row: pd.Series, unknown: str) -> str:
    """Build a compact location string for one zone row."""
    prefecture_str = (
        str(row.get("Prefecture", unknown))
        if is_valid_admin_label(row.get("Prefecture"))
        else unknown
    )
    sous_pref_str = (
        str(row.get("Sous-prefecture", unknown))
        if is_valid_admin_label(row.get("Sous-prefecture"))
        else unknown
    )
    commune_str = (
        str(row.get("admin3name", unknown))
        if is_valid_admin_label(row.get("admin3name"))
        else unknown
    )
    year_val = int(row.get("Year", 0)) if pd.notna(row.get("Year")) else 0
    id_str = str(row.get("id", "—"))
    return (
        f"**{txt('Prefecture')}:** {prefecture_str} | "
        f"**{txt('Sous-prefecture')}:** {sous_pref_str} | "
        f"**{txt('admin3name')}:** {commune_str} | "
        f"**{txt('Year')}:** {year_val} | **ID:** {id_str}"
    )


def _render_detail_panel(aggregated_gdf, resolution: str, persona: str = "Strategic (Donors/PTF)") -> None:
    st.markdown(f"### {txt('profile_title')}")
    st.caption(_profile_caption(resolution))

    zone_col = _detail_zone_column(resolution)
    zone_options = _detail_zone_options(aggregated_gdf, resolution)
    select_label = txt("select_cell") if zone_col == "id" else txt("select_zone")

    col_main, col_compare = st.columns(2)
    with col_main:
        detail_zone = st.selectbox(
            select_label,
            options=[""] + zone_options,
            index=0,
            key="zone_main",
        )
    with col_compare:
        compare_zone = st.selectbox(
            txt("compare_zone"),
            options=[""] + zone_options,
            index=0,
            key="zone_compare",
        )

    if not detail_zone:
        return

    detail = _filter_detail_rows(aggregated_gdf, resolution, detail_zone)
    if detail.empty:
        st.warning(txt("profile_unavailable").format(zone=detail_zone))
        return

    row = detail.iloc[0]
    lang = _current_lang()
    unknown = txt("unknown_location")

    # Resolve optional comparison zone (must differ from main zone)
    row_compare: pd.Series | None = None
    if compare_zone and compare_zone != detail_zone:
        detail_cmp = _filter_detail_rows(aggregated_gdf, resolution, compare_zone)
        if not detail_cmp.empty:
            row_compare = detail_cmp.iloc[0]

    # Location context block — show both zones when comparing
    st.markdown(f"#### {txt('location_context')}")
    st.caption(f"**{txt('zone_selected')}** — {_zone_location_caption(row, unknown)}")
    if row_compare is not None:
        st.caption(f"**{txt('zone_comparison')}** — {_zone_location_caption(row_compare, unknown)}")

    st.markdown(f"#### {txt('radar_title')}")
    st.caption(txt("radar_caption"))
    radar_fig = build_radar_chart(
        row,
        lang=lang,
        persona=persona,
        row_compare=row_compare,
        name_main=detail_zone,
        name_compare=compare_zone if row_compare is not None else "",
    )
    st.plotly_chart(radar_fig, width="stretch")


def main() -> None:
    selected_year = DATA_YEAR
    try:
        _sidebar_lang()
        dashboard_gdf = _cached_load(str(CSV_PATH), str(SHP_PATH), selected_year)
    except FileNotFoundError as exc:
        st.error(str(exc))
        st.stop()
    except (ValueError, KeyError, pd.errors.ParserError) as exc:
        st.error(txt("load_error").format(error=exc))
        st.stop()

    all_index_columns = get_index_columns(dashboard_gdf)
    persona, territory_choice, resolution_option, selected_map_metric = _build_sidebar(
        dashboard_gdf, all_index_columns
    )

    filtered_gdf, aggregated_gdf = _cached_aggregation(
        dashboard_gdf, territory_choice, resolution_option, selected_year
    )
    display_name = (
        txt("all_territories") if territory_choice == "All territories" else territory_choice
    )
    if filtered_gdf.empty:
        st.warning(txt("no_territory_data").format(territory=territory_choice))
        st.stop()

    aggregated_index_columns = get_index_columns(aggregated_gdf)
    original_map_metric = selected_map_metric
    lang = _current_lang()
    if selected_map_metric not in aggregated_index_columns and aggregated_index_columns:
        selected_map_metric = aggregated_index_columns[0]
        st.info(
            txt("metric_fallback_info").format(
                original=label_for_column(original_map_metric, lang=lang),
                fallback=label_for_column(selected_map_metric, lang=lang),
            )
        )

    st.title(txt("title"))
    st.markdown(txt("view").format(txt(persona)))
    st.divider()

    st.subheader(txt("macro_indicators").format(display_name))
    st.caption(_macro_caption(resolution_option))

    pop_col = "population" if "population" in filtered_gdf.columns else (
        "Index_population" if "Index_population" in filtered_gdf.columns else None
    )
    kpi_gdf = _kpi_source_gdf(filtered_gdf, aggregated_gdf, resolution_option)
    metric_values = _compute_kpi_values(
        kpi_gdf,
        persona,
        pop_col,
        use_inhabited_mask=not _is_admin_resolution(resolution_option),
    )
    _render_kpi_cards(metric_values)

    st.divider()
    st.markdown(f"### {txt('overall_vuln')}")
    st.caption(txt("overall_caption"))

    if "Index_Vulnerab_Final" in filtered_gdf.columns:
        vuln_score = pd.to_numeric(
            filtered_gdf["Index_Vulnerab_Final"], errors="coerce"
        ).mean(skipna=True)
        vuln_text = format_score_value(vuln_score, lang=lang)
        st.caption(txt("territory_vuln_caption"))
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            st.metric(txt("territory_score"), vuln_text)

    st.markdown(f"### {txt('geospatial_map')}")
    st.caption(_map_caption(resolution_option))
    map_height = 800 if territory_choice == "All territories" else 650
    with st.spinner(txt("map_generating")):
        choropleth_figure = _cached_build_map(
            aggregated_gdf,
            selected_map_metric,
            resolution_option,
            territory_choice,
            selected_year,
            lang,
            height=map_height,
        )
    st.plotly_chart(choropleth_figure, width="stretch")

    _render_detail_panel(aggregated_gdf, resolution_option, persona=persona)


if __name__ == "__main__":
    main()
