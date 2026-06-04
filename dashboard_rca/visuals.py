"""Map rendering and detail visualization utilities for the dashboard.

This module handles all Plotly figure generation: the choropleth map for
geospatial analysis and the radar chart for multidimensional profiling.

DESIGN DECISIONS EXPLAINED:
  
  1. Sentinel Value (-0.01) for Missing Data:
     ~47% of cells have NaN indices due to field insecurity. Using -0.01 as a
     sentinel allows those cells to render as a distinct neutral gray color,
     avoiding fabricated data or blank spaces that confuse decision-makers.
  
  2. Custom Color Scale with Neutral Base:
     The first part of the color scale maps [-0.01, 0.009] to neutral gray (#f0f0f0).
     This ensures missing-data cells are visually distinct from low-risk cells (0.0 = red).
     The scale then shifts to the base Plotly colorscale for [0.01, 1.0].
  
  3. Hardcoded Map Center (6.6, 20.9):
     We hardcode rather than compute dynamically because:
     - Avoids CRS projection warnings in Streamlit
     - Ensures consistent startup experience
     - Prevents zoom-out distraction for decision-makers
  
  4. Opacity 0.65:
     Allows subtle visibility of labeled basemap (city names, roads) while
     keeping colored cells readable. Full opacity (1.0) hides context.
  
  5. Cell Borders Disabled:
      The grid is already visible from the polygon geometry, so the choropleth
      stroke is kept transparent to avoid white seams between adjacent cells.

World Bank PRWP 11309 Alignment:
  - Choropleth encodes single index (Security, Water, GDP) for focus
  - Radar chart shows 5-dimensional trade-offs for detailed decision-making
  - Both visualizations preserve NaN to maintain data honesty
"""

from __future__ import annotations

import plotly.express as px
from plotly.graph_objs import Figure
import mapclassify as mc

import geopandas as gpd
import pandas as pd

from .config import (
    CAPACITY_METRICS,
    CAR_BOUNDS,
    DETAIL_COLUMNS,
    NO_DATA_COLOR,
    RISK_METRICS,
)
from .formatting import label_for_column, safe_float


def build_map(
    filtered_gdf: gpd.GeoDataFrame,
    color_column: str,
    hover_columns: list[str] | None = None,
    color_scale: str | None = None,
) -> Figure:
    """Create a Jenks-classified choropleth map for the currently selected territory.

    Missing values are preserved as a distinct "No Data" category and excluded
    from Jenks classification so they do not distort the class break calculation.

    Args:
        filtered_gdf: GeoDataFrame filtered to specific prefecture or all CAR
        color_column: Index column to encode (e.g., "Index_Absence_of_conflicts")
        hover_columns: Optional list of columns to display in hover tooltip
        color_scale: Optional color palette name (e.g., "RdYlGn", "Viridis").
            Used as the source palette for the Jenks class colors.

    Returns:
        Plotly Figure (choropleth_map) ready for st.plotly_chart()
    """
    plot_gdf = filtered_gdf.copy()
    plot_column = "__jenks_class__"
    hover_columns = hover_columns or []

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
    }
    existing_columns = [column for column in plot_gdf.columns if column in required_columns]
    plot_gdf = plot_gdf[existing_columns].copy()

    # Simplify polygon geometries to reduce browser rendering lag.
    # Tolerance of 0.005 degrees (~500m at equator) removes minor vertex details
    # while preserving topology and overall shape for all 20,000+ grid cells.
    plot_gdf['geometry'] = plot_gdf['geometry'].simplify(tolerance=0.005, preserve_topology=True)

    # Preserve missing values as a dedicated No Data category and exclude them from Jenks.
    raw_values = pd.to_numeric(plot_gdf[color_column], errors="coerce")
    no_data_mask = raw_values.isna() | raw_values.eq(-0.01)
    valid_values = raw_values.loc[~no_data_mask].dropna()

    plot_gdf[plot_column] = "No Data"

    if not valid_values.empty:
        class_count = min(5, valid_values.nunique())
        jenks = mc.NaturalBreaks(valid_values.to_numpy(), k=class_count)
        class_labels = [
            "Class 1 (Low)",
            "Class 2",
            "Class 3",
            "Class 4",
            "Class 5 (High)",
        ][:class_count]

        class_codes = jenks.yb
        valid_index = valid_values.index
        for idx, class_code in zip(valid_index, class_codes):
            plot_gdf.at[idx, plot_column] = class_labels[int(class_code)]
    else:
        class_labels = []

    # Keep the raw metric available for hover even though color is categorical.
    plot_gdf[color_column] = raw_values

    # Determine the correct color scale: use user selection or semantic routing
    if color_scale is not None:
        # User selected a specific palette from sidebar
        chosen_scale = color_scale
    else:
        # Semantic routing based on metric type (RULE 5: Semantic Colors)
        if color_column == "Index_Vulnerab_Final":
            chosen_scale = "YlOrRd"  # Vulnerability standard
        elif color_column in RISK_METRICS:
            chosen_scale = "Reds"  # Danger/Risk standard
        elif color_column in CAPACITY_METRICS:
            chosen_scale = "Viridis"  # Scientific capacity standard
        else:
            chosen_scale = "Blues"  # Neutral descriptive standard

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
    hover_data_dict: dict[str, object] = {plot_column: False}
    labels_dict: dict[str, str] = {plot_column: label_for_column(color_column)}

    hover_data_dict[color_column] = ":.2f"
    labels_dict[color_column] = f"🎯 {label_for_column(color_column)}"

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
  # Create choropleth with modern Plotly API (not deprecated choropleth_mapbox)
    fig = px.choropleth_map(
        plot_gdf,
        geojson=plot_gdf.geometry,
        locations=plot_gdf.index,
        featureidkey="id",
        color=plot_column,
        color_discrete_map=jenks_color_map,
        category_orders={plot_column: class_labels + ["No Data"]},  # <--- AJOUTE CETTE LIGNE ICI
        hover_name=hover_name_col,
        hover_data=hover_data_dict,
        labels=labels_dict,
        opacity=0.78,  # Slightly higher opacity reduces visible seams between cells
        zoom=5.2,      # Zoom shows full CAR at startup
        center={"lat": 6.6, "lon": 20.9},  # Hardcoded to avoid CRS warnings
        map_style="carto-positron",  # Labeled basemap provides context
        height=700,
    )

    fig.update_layout(
        autosize=True,
        margin={"l": 0, "r": 0, "t": 0, "b": 56},
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

    # Disable cell borders so adjacent polygons don't show white seams.
    for trace in fig.data:
        if getattr(trace, "type", "") in {"choroplethmap", "choroplethmapbox"} and hasattr(trace, "marker"):
            trace.marker.line.width = 0
            trace.marker.line.color = "rgba(0,0,0,0)"
    
    # Lock viewport to CAR bounds to prevent zoom-out distraction
    fig.update_mapboxes(bounds=CAR_BOUNDS, center={"lat": 6.6, "lon": 20.9})

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
      
      Each dimension is normalized to [0, 1] where 1 = high safety/access,
      0 = high risk/no access. The radar visualization makes trade-offs visible:
      e.g., "High security but poor water access".
    
    DESIGN - NaN Handling:
      Missing values (from field insecurity) are set to -0.1 (below 0) and
      labeled "N/A" in hover text. This prevents fabrication while keeping
      the chart readable. Viewers can instantly see which dimensions lack data.
    
    Args:
        row: Single-row Series from GeoDataFrame (one grid cell)
    
    Returns:
        Plotly Figure (scatterpolar) ready for st.plotly_chart()
    """
    # Extract values for the 5 dimensions, using -0.1 for NaN (off-scale as "N/A")
    values = []
    labels = []
    for column in DETAIL_COLUMNS:
        label = label_for_column(column)
        labels.append(label)
        numeric_value = safe_float(row.get(column, pd.NA))
        
        # RULE 2 (Radar Polarity): Invert risk metrics so high risk appears as low on the 0-1 scale
        if column in RISK_METRICS and numeric_value is not None:
            numeric_value = 1.0 - numeric_value
        
        # Use -0.1 for NaN so it renders below zero on the radar, labeled as missing
        values.append(numeric_value if numeric_value is not None else -0.1)

    # Build radar trace with custom styling
    fig = px.line_polar(
        r=values,
        theta=labels,
        line_close=True,
        title="Multidimensional Vulnerability Profile (0=High Risk, 1=High Safety)",
    )

    # Update to filled radar (more readable than lines)
    fig.update_traces(
        fill="toself",
        fillcolor="rgba(100, 150, 255, 0.4)",  # Semi-transparent blue fill
        line_color="rgb(100, 150, 255)",
        marker_size=8,
    )

    # Set radial axis to [0, 1] plus some padding for -0.1 markers
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[-0.2, 1.0],
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
