"""Map rendering utilities for the dashboard."""

from __future__ import annotations

import geopandas as gpd
import plotly.express as px
from plotly.graph_objs import Figure

from .config import CAR_BOUNDS
from .formatting import label_for_column


def build_map(
    filtered_gdf: gpd.GeoDataFrame,
    color_column: str,
    color_scale: str,
    hover_columns: list[str] | None = None,
) -> Figure:
    """Create the choropleth map for the currently selected territory."""

    plot_gdf = filtered_gdf.copy()
    plot_column = "__plot_color__"
    plot_gdf[plot_column] = plot_gdf[color_column].where(
        plot_gdf[color_column].notna(),
        other=-0.01,
    )

    base_scale = px.colors.get_colorscale(color_scale)
    neutral_scale = [
        [0.0, "#f0f0f0"],
        [0.009, "#f0f0f0"],
    ]
    neutral_scale.extend([[0.01 + fraction * 0.99, color] for fraction, color in base_scale])

    hover_data = {
        "Prefecture": True,
        "Sous-prefecture": True,
        "Year": True,
        color_column: ":.2f",
        plot_column: False,
    }

    for column in hover_columns or []:
        if column != color_column and column in plot_gdf.columns:
            hover_data[column] = ":.2f"

    fig = px.choropleth_map(
        plot_gdf,
        geojson=plot_gdf.geometry,
        locations=plot_gdf.index,
        featureidkey="id",
        color=plot_column,
        color_continuous_scale=neutral_scale,
        hover_name="Prefecture",
        hover_data=hover_data,
        range_color=(-0.01, 1),
        opacity=0.65,
        zoom=5.2,
        center={"lat": 6.6, "lon": 20.9},
        map_style="carto-positron",
        height=700,
    )

    fig.update_layout(
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        coloraxis_colorbar_title=label_for_column(color_column),
    )

    fig.update_traces(marker_line_width=0.2, marker_line_color="#ffffff")
    fig.update_mapboxes(bounds=CAR_BOUNDS, center={"lat": 6.6, "lon": 20.9})

    return fig
