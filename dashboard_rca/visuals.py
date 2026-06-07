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
     risk), Viridis (capacity/access), Blues (other). All scales are
     sequential (light = low, dark = high).

  6. Dynamic viewport:
     _compute_viewport() derives center and zoom from the GDF bounding box so
     both full-CAR and single-territory views are handled automatically without
     any caller-side computation.

World Bank PRWP 11309 Alignment:
  - Choropleth encodes a single index for analytical focus.
  - Radar chart shows 5-dimensional vulnerability trade-offs.
  - Both visualizations preserve NaN to maintain data honesty.
"""

from __future__ import annotations

import math

import plotly.express as px
from plotly.graph_objs import Figure
import mapclassify as mc

import geopandas as gpd
import pandas as pd

from .config import (
    CAPACITY_METRICS,
    DETAIL_COLUMNS,
    NO_DATA_COLOR,
    RISK_METRICS,
)
from .formatting import label_for_column, safe_float


# Columns shown as mini-gauge bars in the detailed hover tooltip.
# Tuple layout: (display label, DataFrame column, is_risk_metric)
# is_risk=True  → red scale (high score = danger)
# is_risk=False → green scale (high score = good)
_PILLAR_HOVER: tuple[tuple[str, str, bool], ...] = (
    ("💰 Économie",         "Index_GDP",            False),
    ("💧 Accès Eau",        "Index_water_access",   False),
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
        return "⬜⬜⬜⬜⬜  N/A"

    clamped = max(0.0, min(100.0, float(score)))
    filled = round(clamped / 100.0 * blocks)

    if is_risk:
        color = "🟩" if clamped < 20 else ("🟨" if clamped < 40 else ("🟧" if clamped < 70 else "🟥"))
    else:
        color = "🟥" if clamped < 20 else ("🟧" if clamped < 40 else ("🟨" if clamped < 70 else "🟩"))

    bar = "".join([color] * filled + ["⬜"] * (blocks - filled))
    return f"{bar}  {clamped:.0f}/100"


def _compute_viewport(gdf: gpd.GeoDataFrame) -> dict:
    """Derive map center and zoom from the bounding box of the GDF geometries.

    Reprojects to EPSG:4326 (safe no-op if already geographic) to guarantee
    lat/lon output regardless of the source CRS. Uses a log₂ formula so that
    each halving of the geographic extent increases zoom by 1 level, matching
    the Plotly/Maplibre tile scheme. A 10 % margin keeps polygons away from
    the very edge of the viewport.

    Falls back to the CAR default centre (6.6 N, 20.9 E, zoom 4.8) if the
    geometry is empty or reprojection fails.
    """
    try:
        geo = gdf.geometry.dropna()
        if geo.empty:
            raise ValueError("empty geometry")
        bounds = geo.to_crs("EPSG:4326").total_bounds  # [minlon, minlat, maxlon, maxlat]
        minlon, minlat, maxlon, maxlat = bounds
        center = {"lat": (minlat + maxlat) / 2.0, "lon": (minlon + maxlon) / 2.0}
        max_range = max(maxlon - minlon, maxlat - minlat)
        zoom = math.log2(360.0 / (max_range * 1.1)) if max_range > 0 else 10.0
        zoom = max(1.0, min(15.0, zoom))
        return {"center": center, "zoom": round(zoom, 2)}
    except Exception:
        return {"center": {"lat": 6.6, "lon": 20.9}, "zoom": 4.8}


def build_map(
    filtered_gdf: gpd.GeoDataFrame,
    color_column: str,
    hover_columns: list[str] | None = None,
    resolution: str = "",
) -> Figure:
    """Create a Jenks-classified choropleth map for the currently selected territory.

    Missing values are preserved as a distinct "No Data" category and excluded
    from Jenks classification so they do not distort the class break calculation.
    The color palette is determined automatically via semantic routing based on
    the metric type (vulnerability → YlOrRd, risks → Reds, capacity → Viridis,
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

    Returns:
        Plotly Figure (choropleth_map) ready for st.plotly_chart()
    """
    plot_gdf = filtered_gdf.copy()
    plot_column = "__jenks_class__"
    hover_columns = hover_columns or []

    # Detailed hover active for Prefecture / Sous-prefecture only; not for grid cells.
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
    valid_mask = raw_values.notna()
    plot_gdf[plot_column] = "No Data"

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

    # Build a human-readable hover column: formatted score or "N/A" for missing data.
    plot_gdf["__hover_metric__"] = raw_values.apply(
        lambda v: "N/A" if pd.isna(v) else f"{v:.1f} / 100"
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

    jenks_color_map["No Data"] = NO_DATA_COLOR

    hover_name_col = (
        "Prefecture"
        if "Prefecture" in plot_gdf.columns
        else ("Sous-prefecture" if "Sous-prefecture" in plot_gdf.columns else None)
    )

    # Build native Plotly hover dictionaries so labels stay aligned with the data slice.
    # __hover_metric__ carries the pre-formatted string (value or "N/A") for the tooltip;
    # the raw color_column is excluded from hover to prevent a duplicate "0.00" entry.
    hover_data_dict: dict[str, object] = {plot_column: False, color_column: False}
    labels_dict: dict[str, str] = {plot_column: label_for_column(color_column)}

    hover_data_dict["__hover_metric__"] = True
    labels_dict["__hover_metric__"] = f"🎯 {label_for_column(color_column)}"

    if "Year" in plot_gdf.columns:
        hover_data_dict["Year"] = True
        labels_dict["Year"] = label_for_column("Year")

    if "Sous-prefecture" in plot_gdf.columns:
        hover_data_dict["Sous-prefecture"] = True
        labels_dict["Sous-prefecture"] = label_for_column("Sous-prefecture")

    for column in hover_columns:
        if column != color_column and column in plot_gdf.columns:
            hover_data_dict[column] = ":.2f"
            labels_dict[column] = label_for_column(column)

    # Create choropleth with modern Plotly API (not deprecated choropleth_mapbox)
    fig = px.choropleth_map(
        plot_gdf,
        geojson=plot_gdf.geometry,
        locations=plot_gdf.index,
        featureidkey="id",
        color=plot_column,
        color_discrete_map=jenks_color_map,
        category_orders={plot_column: class_labels + ["No Data"]},
        hover_name=hover_name_col,
        hover_data=hover_data_dict,
        labels=labels_dict,
        opacity=0.78,  # Slightly higher opacity reduces visible seams between cells
        map_style="carto-positron",  # Labeled basemap provides context
        height=700,
    )

    fig.update_layout(
        autosize=True,
        margin={"l": 0, "r": 0, "t": 0, "b": 0}, # On enlève toutes les marges blanches
        legend=dict(
            title_text="",          # On enlève le titre redondant de la légende
            orientation="v",        # Verticale
            yanchor="top",
            y=0.98,                 # Collée en haut
            xanchor="left",
            x=1.01,                 # <-- POUSSE LA LÉGENDE TOTALEMENT SUR LA DROITE (hors de la carte)
            bgcolor="rgba(255,255,255,0.6)" # Fond légèrement transparent pour faire respirer
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
                text=f"Gray = no data / uninhabited ({NO_DATA_COLOR})",
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
                plot_gdf[f"__pg_{col_key}__"] = "⬜⬜⬜⬜⬜  N/A"

        gauge_cols = [f"__pg_{col_key}__" for _, col_key, _ in _PILLAR_HOVER]
        # customdata layout: [0]=main metric, [1]=economy, [2]=water, [3]=infra
        cd_cols = ["__hover_metric__"] + gauge_cols
        cd_array = plot_gdf[cd_cols].values.tolist()

        metric_label = label_for_column(color_column)
        pillar_lines = "".join(
            f"{label}: " + "%{customdata[" + str(i + 1) + "]}<br>"
            for i, (label, _, _) in enumerate(_PILLAR_HOVER)
        )
        hovertemplate = (
            "<b>%{hovertext}</b><br>"
            + f"🎯 {metric_label}: " + "%{customdata[0]}<br>"
            + "<span style='color:#aaa'>──────────────────</span><br>"
            + pillar_lines
            + "<extra></extra>"
        )

        zone_col = (
            "Prefecture" if "Prefecture" in plot_gdf.columns
            else ("Sous-prefecture" if "Sous-prefecture" in plot_gdf.columns else "id")
        )
        hovertext = plot_gdf[zone_col].fillna("—").tolist()

        for trace in fig.data:
            # Each trace covers only a subset of locations (one Jenks class).
            # Plotly aligns customdata positionally within the trace (index 0 of
            # customdata → first point of the trace), NOT by location value.
            # We must therefore extract the slice of cd_array / hovertext that
            # corresponds to this trace's locations, preserving their order.
            locs = list(trace.locations) if trace.locations is not None else []
            trace.customdata    = [cd_array[i] for i in locs]
            trace.hovertext     = [hovertext[i] for i in locs]
            trace.hovertemplate = hovertemplate
    # ------------------------------------------------------------------------------

    # Fit viewport to the visible polygons: center and zoom derived from the
    # bounding box of plot_gdf, so both full-CAR and territory views are handled
    # automatically without any caller-side computation.
    viewport = _compute_viewport(plot_gdf)
    fig.update_layout(map=dict(center=viewport["center"], zoom=viewport["zoom"]))

    return fig


def build_radar_chart(
    row: pd.Series,
) -> Figure:
    """Create a radar chart showing 5-dimensional multidimensional profile.
    
    WORLD BANK PRWP 11309 ALIGNMENT:
      The radar chart displays the 5-dimensional vulnerability framework:
      1. Primary Economy (agriculture)
      2. Overall Economy (GDP)
      3. Health Access
      4. Water Access
      5. Education Access
      
      Each dimension is scaled to [0, 100] where 100 = high safety/access,
      0 = high risk/no access. The radar visualization makes trade-offs visible:
      e.g., "High security but poor water access".
    
    DESIGN - NaN Handling:
      Missing values (from field insecurity) are set to -10 (below 0) and
      labeled "N/A" in hover text. This prevents fabrication while keeping
      the chart readable. Viewers can instantly see which dimensions lack data.
    
    Args:
        row: Single-row Series from GeoDataFrame (one grid cell)
    
    Returns:
        Plotly Figure (scatterpolar) ready for st.plotly_chart()
    """
    # Extract values for the 5 dimensions, using -10 for NaN (off-scale as "N/A")
    values = []
    labels = []
    for column in DETAIL_COLUMNS:
        label = label_for_column(column)
        labels.append(label)
        numeric_value = safe_float(row.get(column, pd.NA))

        # Invert risk metrics so high risk appears as low on the 0-100 safety axis.
        if column in RISK_METRICS and numeric_value is not None:
            numeric_value = 100.0 - numeric_value

        values.append(numeric_value if numeric_value is not None else -10.0)

    # Build radar trace with custom styling
    fig = px.line_polar(
        r=values,
        theta=labels,
        line_close=True,
        title="Multidimensional Vulnerability Profile (0=High Risk, 100=High Safety)",
    )

    # Update to filled radar (more readable than lines)
    fig.update_traces(
        fill="toself",
        fillcolor="rgba(100, 150, 255, 0.4)",  # Semi-transparent blue fill
        line_color="rgb(100, 150, 255)",
        marker_size=8,
    )

    # Set radial axis to [0, 100] plus some padding for -10 markers
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
        height=450,
        margin=dict(l=80, r=80, t=80, b=80),
        font=dict(size=11),
    )

    return fig
