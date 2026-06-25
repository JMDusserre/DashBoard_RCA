"""Map rendering and detail visualization utilities for the dashboard.

DESIGN DECISIONS:

  1. Jenks Natural Breaks classification:
     Values are split into up to 5 classes using mapclassify.NaturalBreaks.
     NaN cells (~68% of the grid, caused by field insecurity) are assigned
     "No Data" and rendered in NO_DATA_COLOR (light gray). They are excluded
     from the Jenks fit so missing data never distorts class boundaries.

  2. Index-Safe classification:
     A single boolean valid_mask drives both the Jenks fit and the .loc
     assignment, guaranteeing jenks.yb[i] maps to the i-th valid row with
     zero NaN-induced positional drift.

  3. Sequential index before Plotly:
     plot_gdf is reset_index(drop=True) before figure creation so that
     locations=plot_gdf.index matches the sequential GeoJSON feature IDs that
     Plotly assigns when converting a GeoSeries.

  4. Per-trace customdata alignment:
     px.choropleth_map creates one trace per Jenks class. Plotly aligns
     customdata positionally within each trace (index 0 → first point of that
     trace). We therefore extract cd_array[locs] for each trace individually
     to avoid cross-class data leakage in hover tooltips.

  5. Semantic color routing:
     Palette chosen automatically: YlOrRd (vulnerability), Reds (conflict/
     risk), Greens (capacity/access), Blues (other). All scales are
     sequential (light = low, dark = high).

  6. Dynamic viewport:
     build_map() computes center and zoom from the GDF bounding box (log₂ formula)
     so both full-CAR and single-territory views are framed correctly regardless
     of the map container size.

World Bank PRWP 11309 Alignment:
  - Choropleth encodes a single index for analytical focus.
  - Radar chart shows 5-dimensional vulnerability trade-offs.
  - Both visualizations preserve NaN to maintain data honesty.
"""

from __future__ import annotations

import math

import plotly.express as px
import plotly.graph_objects as go
from plotly.graph_objs import Figure
import mapclassify as mc

import geopandas as gpd
import pandas as pd

from .config import (
    CAPACITY_METRICS,
    NO_DATA_COLOR,
    PERSONA_RADAR_COLUMNS,
    RISK_METRICS,
    UI_TEXTS,
)
from .formatting import MISSING_VALUE_LABEL, format_metric_value, label_for_column, safe_float


# Columns shown as mini-gauge bars in the detailed hover tooltip.
# Tuple layout: (display label, DataFrame column, is_risk_metric)
# is_risk=True  → red scale (high score = danger)
# is_risk=False → green scale (high score = good)
def _hover_zone_column(resolution: str, columns: set[str] | frozenset[str]) -> str | None:
    """Pick the finest admin label column available for the active resolution."""
    if resolution.startswith("Secteur") or resolution.startswith("Grid"):
        return "id" if "id" in columns else None
    if resolution.startswith("Commune") and "admin3name" in columns:
        return "admin3name"
    if resolution.startswith("Sous-prefecture") and "Sous-prefecture" in columns:
        return "Sous-prefecture"
    if resolution.startswith("Prefecture") and "Prefecture" in columns:
        return "Prefecture"
    if "admin3name" in columns:
        return "admin3name"
    if "Sous-prefecture" in columns:
        return "Sous-prefecture"
    if "Prefecture" in columns:
        return "Prefecture"
    return "id" if "id" in columns else None


_PILLAR_HOVER: tuple[tuple[str, str, bool], ...] = (
    ("💰 Économie",         "Index_GDP",            False),
    ("⚠️ Risques",          "Index_ExpoRisk",       True),
    ("🏗️ Infrastructures",  "Index_Infrastructure", False),
)


def _gauge(score: float | None, *, is_risk: bool = False, blocks: int = 5) -> str:
    """Convert a 0-100 score into a 5-block emoji progress bar.

    Color logic:
    - Capacity metric (is_risk=False): green = high score (good access / safe)
    - Risk metric     (is_risk=True) : red   = high score (dangerous)

    Examples (capacity):
      20/100 → 🟧⬜⬜⬜⬜  20/100
      60/100 → 🟨🟨🟨⬜⬜  60/100
      90/100 → 🟩🟩🟩🟩⬜  90/100
    """
    if score is None or not isinstance(score, (int, float)) or pd.isna(score):
        return f"⬜⬜⬜⬜⬜  {MISSING_VALUE_LABEL}"

    clamped = max(0.0, min(100.0, float(score)))
    filled = round(clamped / 100.0 * blocks)

    if is_risk:
        color = "🟩" if clamped < 20 else ("🟨" if clamped < 40 else ("🟧" if clamped < 70 else "🟥"))
    else:
        color = "🟥" if clamped < 20 else ("🟧" if clamped < 40 else ("🟨" if clamped < 70 else "🟩"))

    bar = "".join([color] * filled + ["⬜"] * (blocks - filled))
    return f"{bar}  {clamped:.0f}"



def build_map(
    filtered_gdf: gpd.GeoDataFrame,
    color_column: str,
    hover_columns: list[str] | None = None,
    resolution: str = "",
    lang: str = "FR",
    height: int = 700,
) -> Figure:
    """Create a Jenks-classified choropleth map for the currently selected territory.

    Missing values are preserved as a distinct "No Data" category and excluded
    from Jenks classification so they do not distort the class break calculation.
    The color palette is determined automatically via semantic routing based on
    the metric type (vulnerability → YlOrRd, risks → Reds, capacity → Greens,
    others → Blues). All scales are sequential (light=low, dark=high).

    When `resolution` is Prefecture or Sous-prefecture, the hover tooltip is
    enriched with 5-block emoji gauges for the three structural pillars (Economy,
    Water, Infrastructure). At grid-cell resolution the simple tooltip is kept
    for performance reasons (20k+ cells).

    Args:
        filtered_gdf: GeoDataFrame filtered to specific prefecture or all CAR
        color_column: Index column to encode (e.g., "Index_conflicts")
        hover_columns: Optional list of columns to display in hover tooltip
        resolution: Current spatial resolution string from config.SPATIAL_RESOLUTIONS.
            Used to decide between simple and detailed hover tooltips.
        lang: UI language code (``FR`` or ``EN``) for hover labels and formatted values.
        height: Figure height in pixels. Defaults to 700. Pass a larger value on
            wide-screen deployments to fill the available vertical space.

    Returns:
        Plotly Figure (choropleth_map) ready for st.plotly_chart()
    """
    plot_gdf = filtered_gdf.copy()
    plot_column = "__jenks_class__"
    hover_columns = hover_columns or []

    # Detailed hover for admin resolutions (Commune, Sous-prefecture, Prefecture).
    is_detailed_hover = bool(resolution) and not (
        resolution.startswith("Secteur") or resolution.startswith("Grid")
    )

    # Include pillar columns so gauge computation can reference them after slicing.
    pillar_cols = {col for _, col, _ in _PILLAR_HOVER}

    # Keep only the columns needed for map rendering to reduce the JSON payload
    # sent to the browser. The full GeoDataFrame can be large even when the
    # geometry itself is simple, so dropping unused fields improves startup time.
    required_columns = {
        "id",
        color_column,
        plot_column,
        "geometry",
        "Prefecture",
        "Sous-prefecture",
        "Year",
        *hover_columns,
        *(pillar_cols if is_detailed_hover else set()),
        *({"admin3name"} if is_detailed_hover else set()),
    }
    existing_columns = [column for column in plot_gdf.columns if column in required_columns]
    plot_gdf = plot_gdf[existing_columns].copy()

    # CRITICAL: reset to a 0-based sequential index BEFORE any computation.
    # After territory filtering, the pandas index may be non-contiguous (e.g.,
    # [5000, 5001, ..., 5099]). Plotly converts the GeoSeries to GeoJSON with
    # feature IDs equal to the sequential POSITION (0, 1, 2, …), not the pandas
    # index value. If locations=plot_gdf.index still contains [5000, …], Plotly
    # looks for feature ID 5000 which doesn't exist → random/wrong colour mapping.
    plot_gdf = plot_gdf.reset_index(drop=True)

    # Convert to numeric once; write back so the column is a clean float series.
    raw_values = pd.to_numeric(plot_gdf[color_column], errors="coerce")
    plot_gdf[color_column] = raw_values

    # --- INDEX-SAFE JENKS CLASSIFICATION ---
    # valid_mask is the single source-of-truth for "has data". It is used
    # identically for fitting Jenks AND for the .loc assignment, so NaN rows
    # can never shift the yb array relative to the DataFrame index.
    #
    # Why this matters: jenks.yb is a positional array (yb[i] belongs to
    # the i-th element passed to NaturalBreaks). Using the same boolean mask
    # for both the fit and the assignment guarantees that yb[i] is written
    # to exactly the i-th row that satisfies valid_mask — no intermediate
    # Series or index reconstruction needed.
    # NaN label is context-sensitive: GDP metrics can have genuine missing data
    # (mining/agriculture in uninhabited areas), while all other satellite-derived
    # indices simply reflect uninhabited land (forests, savannas, etc.).
    if "GDP" in color_column:
        nan_label = "Données manquantes" if lang == "FR" else "Missing data"
    else:
        nan_label = "Zone inhabitée" if lang == "FR" else "Uninhabited area"

    valid_mask = raw_values.notna()
    plot_gdf[plot_column] = nan_label

    if valid_mask.any():
        class_count = min(5, raw_values.loc[valid_mask].nunique())
        jenks = mc.NaturalBreaks(raw_values.loc[valid_mask].to_numpy(), k=class_count)
        class_labels = [
            "Class 1 (Low)",
            "Class 2",
            "Class 3",
            "Class 4",
            "Class 5 (High)",
        ][:class_count]

        # Direct .loc[valid_mask] assignment: jenks.yb[i] goes to the i-th
        # True position of valid_mask — zero NaN-induced drift possible.
        plot_gdf.loc[valid_mask, plot_column] = [class_labels[int(c)] for c in jenks.yb]
    else:
        class_labels = []
    # --- END INDEX-SAFE JENKS ---

    # Build a human-readable hover column on the 0–100 display scale.
    plot_gdf["__hover_metric__"] = raw_values.apply(
        lambda v: (
            MISSING_VALUE_LABEL
            if pd.isna(v)
            else format_metric_value(color_column, float(v), lang=lang)
        )
    )

    # Semantic routing: palette chosen automatically based on metric type.
    if color_column == "Index_Vulnerab_Final":
        chosen_scale = "YlOrRd"   # Overall vulnerability: warm gradient
    elif color_column in RISK_METRICS:
        chosen_scale = "Reds"     # Risk/negative metrics: danger gradient
    elif color_column in CAPACITY_METRICS:
        chosen_scale = "Greens"  # Capacity/access metrics: scientific gradient
    else:
        chosen_scale = "Blues"    # Neutral/descriptive metrics: neutral gradient

    # Build a discrete palette for Jenks classes from the selected scale.
    if class_labels:
        sampled_positions = [0.1, 0.3, 0.5, 0.7, 0.9][: len(class_labels)]
        sampled_colors = px.colors.sample_colorscale(chosen_scale, sampled_positions)
        jenks_color_map = {
            label: color for label, color in zip(class_labels, sampled_colors)
        }
    else:
        jenks_color_map = {}

    jenks_color_map[nan_label] = NO_DATA_COLOR

    hover_name_col = _hover_zone_column(resolution, set(plot_gdf.columns))

    # Build native Plotly hover dictionaries so labels stay aligned with the data slice.
    # __hover_metric__ carries the pre-formatted string (value or "N/A") for the tooltip;
    # the raw color_column is excluded from hover to prevent a duplicate "0.00" entry.
    hover_data_dict: dict[str, object] = {plot_column: False, color_column: False}
    labels_dict: dict[str, str] = {plot_column: label_for_column(color_column, lang=lang)}

    hover_data_dict["__hover_metric__"] = True
    labels_dict["__hover_metric__"] = f"🎯 {label_for_column(color_column, lang=lang)}"

    if is_detailed_hover:
        if "Year" in plot_gdf.columns:
            hover_data_dict["Year"] = True
            labels_dict["Year"] = label_for_column("Year", lang=lang)
        if "Prefecture" in plot_gdf.columns:
            hover_data_dict["Prefecture"] = True
            labels_dict["Prefecture"] = label_for_column("Prefecture", lang=lang)
        if "Sous-prefecture" in plot_gdf.columns:
            hover_data_dict["Sous-prefecture"] = True
            labels_dict["Sous-prefecture"] = label_for_column("Sous-prefecture", lang=lang)
        if "admin3name" in plot_gdf.columns:
            hover_data_dict["admin3name"] = True
            labels_dict["admin3name"] = label_for_column("admin3name", lang=lang)

    for column in hover_columns:
        if column != color_column and column in plot_gdf.columns:
            hover_data_dict[column] = ":.2f"
            labels_dict[column] = label_for_column(column, lang=lang)

    # Create choropleth with modern Plotly API (not deprecated choropleth_mapbox)
    fig = px.choropleth_map(
        plot_gdf,
        geojson=plot_gdf.geometry,
        locations=plot_gdf.index,
        featureidkey="id",
        color=plot_column,
        color_discrete_map=jenks_color_map,
        category_orders={plot_column: class_labels + [nan_label]},
        hover_name=hover_name_col,
        hover_data=hover_data_dict,
        labels=labels_dict,
        opacity=0.78,  # Slightly higher opacity reduces visible seams between cells
        map_style="carto-positron",  # Labeled basemap provides context
        height=height,
    )

    fig.update_layout(
        autosize=True,
        margin={"l": 0, "r": 0, "t": 0, "b": 0},  # Remove all white margins around the map
        legend=dict(
            title_text="",  # Drop redundant legend title (color column is in the hover)
            orientation="v",
            yanchor="top",
            y=0.98,
            xanchor="left",
            x=1.01,  # Push legend fully to the right (outside the map canvas)
            bgcolor="rgba(255,255,255,0.6)",  # Slightly transparent legend background
        )
    )

    # Add a simple north-arrow annotation for cartographic convention
    fig.update_layout(
        annotations=[
            dict(
                text="⬆ N",
                x=0.97,
                y=0.97,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(size=14),
            ),
            dict(
                text=f"Gray = {nan_label} ({NO_DATA_COLOR})",
                x=0.5,
                y=-0.2,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(size=11, color="#666666"),
            )
        ]
    )

    # Remove polygon borders unconditionally. update_traces() is more robust than
    # a per-trace type check and survives Plotly internal API changes.
    fig.update_traces(marker_line_width=0, selector={"type": "choroplethmap"})

    # --- DETAILED HOVER (Prefecture / Sous-prefecture resolutions) ----------------
    # Build emoji gauge strings for each pillar and inject them into customdata
    # so the hovertemplate can reference them with %{customdata[i]}.
    if is_detailed_hover:
        for _pillar_label, col_key, col_is_risk in _PILLAR_HOVER:
            if col_key in plot_gdf.columns:
                vals = pd.to_numeric(plot_gdf[col_key], errors="coerce")
                plot_gdf[f"__pg_{col_key}__"] = vals.apply(
                    lambda v, r=col_is_risk: _gauge(v, is_risk=r)
                )
            else:
                plot_gdf[f"__pg_{col_key}__"] = f"⬜⬜⬜⬜⬜  {MISSING_VALUE_LABEL}"

        gauge_cols = [f"__pg_{col_key}__" for _, col_key, _ in _PILLAR_HOVER]
        # customdata layout: [0]=main metric, [1]=economy, [2]=risk, [3]=infra
        cd_cols = ["__hover_metric__"] + gauge_cols
        cd_array = plot_gdf[cd_cols].values.tolist()

        metric_label = label_for_column(color_column, lang=lang)
        pillar_lines = "".join(
            f"{label}: " + "%{customdata[" + str(i + 1) + "]}<br>"
            for i, (label, _, _) in enumerate(_PILLAR_HOVER)
        )
        # Plain text only — HTML tags with "/" break Streamlit's Plotly JSON parser.
        hovertemplate = (
            "%{hovertext}<br>"
            + f"🎯 {metric_label}: " + "%{customdata[0]}<br>"
            + "──────────────────<br>"
            + pillar_lines
        )

        zone_col = _hover_zone_column(resolution, set(plot_gdf.columns)) or "id"
        hovertext = plot_gdf[zone_col].fillna("—").tolist()

        for trace in fig.data:
            # Each trace covers only a subset of locations (one Jenks class).
            # Plotly aligns customdata positionally within the trace (index 0 of
            # customdata → first point of the trace), NOT by location value.
            # We must therefore extract the slice of cd_array / hovertext that
            # corresponds to this trace's locations, preserving their order.
            locs = list(trace.locations) if trace.locations is not None else []
            trace.customdata = [cd_array[i] for i in locs]
            trace.hovertext = [hovertext[i] for i in locs]
            trace.hovertemplate = hovertemplate
            trace.hoverlabel = dict(namelength=0)
    # ------------------------------------------------------------------------------

    # Fit the camera to the visible polygons using center + zoom derived from
    # the bounding box. map.bounds is a navigation constraint, not a fit
    # command — center/zoom is the only reliable way to set the initial view.
    try:
        geo = plot_gdf.geometry.dropna()
        if geo.empty:
            raise ValueError("empty geometry")
        bounds = geo.to_crs("EPSG:4326").total_bounds  # [minlon, minlat, maxlon, maxlat]
        minlon, minlat, maxlon, maxlat = bounds
        center = {"lat": (minlat + maxlat) / 2.0, "lon": (minlon + maxlon) / 2.0}
        max_range = max(maxlon - minlon, maxlat - minlat)
        zoom = math.log2(360.0 / (max_range * 1.1)) if max_range > 0 else 10.0
        zoom = max(1.0, min(15.0, zoom))
    except Exception:
        center = {"lat": 6.6, "lon": 20.9}
        zoom = 4.8
    fig.update_layout(map=dict(center=center, zoom=round(zoom, 2)))

    return fig


def _radar_hover_text(column: str, numeric_value: float, lang: str) -> str:
    """Build hover label: score aligned with map; risk axes add a 2-line radar reading."""
    label = label_for_column(column, lang=lang)
    score = format_metric_value(column, numeric_value, lang=lang)
    line1 = f"{label} : {score}"
    if column not in RISK_METRICS:
        return line1

    texts = UI_TEXTS.get(lang, UI_TEXTS["FR"])
    clamped = max(0.0, min(100.0, numeric_value))
    if clamped >= 70:
        line2 = texts["radar_hover_risk_high"]
    elif clamped < 40:
        line2 = texts["radar_hover_risk_low"]
    else:
        line2 = texts["radar_hover_risk_mid"]
    return f"{line1}<br>{line2}"


def _extract_radar_values(
    row: pd.Series,
    columns: list[str],
    lang: str,
) -> tuple[list[float], list[str]]:
    """Extract radar plot and hover values for one zone row.

    Returns ``plot_values`` (inverted for RISK_METRICS so the polygon reads as
    safety) and ``raw_values`` (hover strings: map score; risk axes include a
    second line explaining outward vs inward spokes).
    Missing data → plot at -10 (off-scale sentinel); hover shows MISSING_VALUE_LABEL.
    Each list is closed by repeating the first value for go.Scatterpolar.
    """
    plot_values: list[float] = []
    raw_values: list[str] = []
    for column in columns:
        numeric_value = safe_float(row.get(column, pd.NA))
        if numeric_value is not None:
            raw_values.append(_radar_hover_text(column, numeric_value, lang))
            plot_values.append(
                100.0 - numeric_value if column in RISK_METRICS else numeric_value
            )
        else:
            raw_values.append(
                f"{label_for_column(column, lang=lang)} : {MISSING_VALUE_LABEL}"
            )
            plot_values.append(-10.0)
    return plot_values + [plot_values[0]], raw_values + [raw_values[0]]


def build_radar_chart(
    row: pd.Series,
    lang: str = "FR",
    persona: str = "Strategic (Donors/PTF)",
    row_compare: pd.Series | None = None,
    name_main: str = "",
    name_compare: str = "",
) -> Figure:
    """Create a radar chart showing the 5-dimensional vulnerability profile.

    Axes are driven by ``config.PERSONA_RADAR_COLUMNS[persona]``, so each user
    profile sees the 5 dimensions most relevant to their decision-making.
    Risk metrics are inverted so the radial axis always reads as a safety scale.

    DESIGN - NaN Handling:
      Missing values (from field insecurity) are set to -10 (below 0) and
      labeled with MISSING_VALUE_LABEL in hover text.

    DESIGN - Hover clarity:
      Hover shows the map score (with locale suffix). Risk metrics add a second
      line explaining how the spoke direction relates to the raw score.

    DESIGN - Comparison mode:
      When ``row_compare`` is provided a second Scatterpolar trace is added in
      orange. The legend is shown horizontally at the bottom only in that case.

    Args:
        row: Primary zone row (pd.Series from GeoDataFrame).
        lang: UI language code (``"FR"`` or ``"EN"``).
        persona: Active persona key from ``config.PERSONA_OPTIONS``.
        row_compare: Optional secondary zone row for overlay comparison.
        name_main: Legend label for the primary zone.
        name_compare: Legend label for the comparison zone.

    Returns:
        Plotly Figure (scatterpolar) ready for st.plotly_chart()
    """
    # Fall back to first persona if key is missing (defensive)
    columns = PERSONA_RADAR_COLUMNS.get(
        persona, next(iter(PERSONA_RADAR_COLUMNS.values()))
    )
    labels = []
    for col in columns:
        base_label = label_for_column(col, lang=lang)
        if col in RISK_METRICS:
            # On inverse le sens du mot pour coller à l'inversion géométrique
            if lang == "FR":
                if "vulnérabilité" in base_label.lower():
                    labels.append("Résilience Globale")
                else:
                    labels.append("Sécurité (Protection risques)")
            else:
                if "vulnerability" in base_label.lower():
                    labels.append("Overall Resilience")
                else:
                    labels.append("Safety (Risk Protection)")
        else:
            labels.append(base_label)
    # Closed labels list (repeat first to match closed values)
    theta = labels + [labels[0]]

    values_main, raw_values_main = _extract_radar_values(row, columns, lang)

    fig = go.Figure()

    fig.add_trace(go.Scatterpolar(
        r=values_main,
        theta=theta,
        hovertext=raw_values_main,
        hovertemplate="%{hovertext}<extra></extra>",
        fill="toself",
        fillcolor="rgba(100, 150, 255, 0.35)",
        line=dict(color="rgb(100, 150, 255)", width=2),
        marker=dict(size=7),
        name=name_main or (labels[0] if not row_compare else ""),
        showlegend=row_compare is not None,
    ))

    if row_compare is not None:
        values_compare, raw_values_compare = _extract_radar_values(row_compare, columns, lang)
        fig.add_trace(go.Scatterpolar(
            r=values_compare,
            theta=theta,
            hovertext=raw_values_compare,
            hovertemplate="%{hovertext}<extra></extra>",
            fill="toself",
            fillcolor="rgba(255, 140, 60, 0.30)",
            line=dict(color="rgb(220, 90, 20)", width=2),
            marker=dict(size=7),
            name=name_compare,
            showlegend=True,
        ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[-20.0, 100.0],
                tickfont=dict(size=10),
                gridcolor="lightgray",
            ),
            angularaxis=dict(
                tickfont=dict(size=11),
            ),
        ),
        showlegend=row_compare is not None,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.25,
            xanchor="center",
            x=0.5,
        ) if row_compare is not None else {},
        height=450,
        margin=dict(l=80, r=80, t=60, b=80 if row_compare is None else 110),
        font=dict(size=11),
    )

    return fig
