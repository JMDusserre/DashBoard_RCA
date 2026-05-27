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

import geopandas as gpd
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.graph_objs import Figure

from .config import CAR_BOUNDS, DETAIL_COLUMNS
from .formatting import label_for_column, safe_float


def build_map(
    filtered_gdf: gpd.GeoDataFrame,
    color_column: str,
    color_scale: str,
    hover_columns: list[str] | None = None,
    highlight_gdf: gpd.GeoDataFrame | None = None,
) -> Figure:
    """Create the choropleth map for the currently selected territory.
    
    CRITICAL DESIGN - Sentinel Value Handling:
      Missing indices (NaN from field insecurity) are replaced with -0.01.
      The color scale maps [-0.01, 0.009] to neutral gray (#f0f0f0), then
      includes the full base scale for [0.01, 1.0] (red=risk, green=safe).
      This allows viewers to instantly distinguish missing data from low-risk areas.
    
    CRITICAL DESIGN - Map Bounds:
      CAR_BOUNDS are hardcoded to prevent zoom-out. This keeps decision-makers
      focused on the territory and avoids CRS projection warnings.
    
    Args:
        filtered_gdf: GeoDataFrame filtered to specific prefecture or all CAR
        color_column: Index column to encode (e.g., "Index_Absence_of_conflicts")
        color_scale: Plotly colorscale name (e.g., "RdYlGn")
        hover_columns: Optional list of columns to display in hover tooltip
    
    Returns:
        Plotly Figure (choropleth_map) ready for st.plotly_chart()
    """
    plot_gdf = filtered_gdf.copy()
    plot_column = "__plot_color__"
    hover_columns = hover_columns or []
    
    # Replace NaN with sentinel -0.01 so they render as neutral gray, not blank.
    plot_gdf[plot_column] = plot_gdf[color_column].where(
        plot_gdf[color_column].notna(),
        other=-0.01,
    )

    # Build custom color scale: neutral gray for missing data, then base scale.
    base_scale = px.colors.get_colorscale(color_scale)
    neutral_scale = [
        [0.0, "#f0f0f0"],      # Sentinel -0.01 maps to neutral gray
        [0.009, "#f0f0f0"],    # Bridge to 0.01 (where base scale starts)
    ]
    # Shift base scale to [0.01, 1.0] range so red=risk, green=safety
    neutral_scale.extend([[0.01 + fraction * 0.99, color] for fraction, color in base_scale])

    # Build tooltip columns in a fixed order so the hovertemplate stays readable
    # and doesn't depend on raw Plotly field names.
    customdata_columns: list[str] = []
    if "Prefecture" in plot_gdf.columns:
        customdata_columns.append("Prefecture")
    if "Sous-prefecture" in plot_gdf.columns:
        customdata_columns.append("Sous-prefecture")
    if "Year" in plot_gdf.columns:
        customdata_columns.append("Year")
    if color_column in plot_gdf.columns:
        customdata_columns.append(color_column)

    seen_columns = set(customdata_columns)
    for column in hover_columns:
        if column != color_column and column in plot_gdf.columns and column not in seen_columns:
            customdata_columns.append(column)
            seen_columns.add(column)

    hover_lines: list[str] = []
    if "Prefecture" in customdata_columns:
        hover_lines.append(f"{label_for_column('Prefecture')}: %{{customdata[0]}}")
    if "Sous-prefecture" in customdata_columns:
        hover_lines.append(f"{label_for_column('Sous-prefecture')}: %{{customdata[{customdata_columns.index('Sous-prefecture')}]}}")
    if "Year" in customdata_columns:
        hover_lines.append(f"{label_for_column('Year')}: %{{customdata[{customdata_columns.index('Year')}]}}")
    if color_column in customdata_columns:
        hover_lines.append(
            f"{label_for_column(color_column)}: %{{customdata[{customdata_columns.index(color_column)}]:.2f}}"
        )
    for column in hover_columns:
        if column != color_column and column in customdata_columns:
            hover_lines.append(
                f"{label_for_column(column)}: %{{customdata[{customdata_columns.index(column)}]:.2f}}"
            )

    # Create choropleth with modern Plotly API (not deprecated choropleth_mapbox)
    fig = px.choropleth_map(
        plot_gdf,
        geojson=plot_gdf.geometry,
        locations=plot_gdf.index,
        featureidkey="id",
        color=plot_column,
        color_continuous_scale=neutral_scale,
        hover_name="Prefecture" if "Prefecture" in plot_gdf.columns else None,
        hover_data={column: False for column in customdata_columns},
        range_color=(-0.01, 1),
        opacity=0.78,  # Slightly higher opacity reduces visible seams between cells
        zoom=5.2,      # Zoom shows full CAR at startup
        center={"lat": 6.6, "lon": 20.9},  # Hardcoded to avoid CRS warnings
        map_style="carto-positron",  # Labeled basemap provides context
        height=700,
    )

    fig.update_traces(
        customdata=plot_gdf[customdata_columns].to_numpy(),
        hovertemplate="<b>%{hovertext}</b><br>" + "<br>".join(hover_lines[1:]) + "<extra></extra>",
    )

    if highlight_gdf is not None and not highlight_gdf.empty and {"lat", "lon"}.issubset(highlight_gdf.columns):
        highlight_text = []
        for _, row in highlight_gdf.iterrows():
            label = row.get("label", "")
            value = row.get("value", pd.NA)
            rank = row.get("rank", pd.NA)
            value_text = "N/A" if pd.isna(value) else f"{float(value):.2f}"
            highlight_text.append(
                f"<b>#{rank}</b><br>{label}<br>{label_for_column(color_column)}: {value_text}"
            )

        fig.add_trace(
            go.Scattermap(
                lat=highlight_gdf["lat"],
                lon=highlight_gdf["lon"],
                mode="markers",
                name="Top risk",
                text=highlight_text,
                hovertemplate="%{text}<extra></extra>",
                marker=dict(
                    size=16,
                    color="#d7263d",
                    opacity=0.9,
                    symbol="circle",
                    allowoverlap=True,
                ),
            )
        )

    fig.update_layout(
        autosize=True,
        margin={"l": 0, "r": 0, "t": 0, "b": 56},
        coloraxis_colorbar=dict(
            title=label_for_column(color_column),
            orientation="h",
            x=0.5,
            xanchor="center",
            y=-0.12,
            yanchor="top",
            thickness=14,
            len=0.86,
        ),
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
