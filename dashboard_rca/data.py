"""Data loading and schema helpers for the dashboard."""

from __future__ import annotations

import geopandas as gpd
import pandas as pd

from .config import INDEX_PREFIX


def load_dashboard_data(csv_path: str, shp_path: str) -> gpd.GeoDataFrame:
    """Load, normalize, and merge the tabular and spatial sources."""

    try:
        csv_frame = pd.read_csv(csv_path, na_values=["NA", "NaN", ""])
        spatial_frame = gpd.read_file(shp_path)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            "The dashboard data files could not be found. Check Sample_RCA.csv "
            "and Grid_5km_CFA_v3/Grid_5km_CFA_v3.shp."
        ) from exc

    csv_frame["id"] = csv_frame["id"].astype(str)
    spatial_frame["id"] = spatial_frame["id"].apply(
        lambda value: str(int(value)) if pd.notna(value) else pd.NA
    )

    return spatial_frame.merge(csv_frame, on="id", how="left", validate="1:1")


def get_prefecture_options(gdf: gpd.GeoDataFrame) -> list[str]:
    """Return a clean, deterministic list of prefecture names."""

    return gdf["Prefecture"].dropna().astype(str).sort_values().unique().tolist()


def get_year_options(gdf: gpd.GeoDataFrame) -> list[int]:
    """Return the available years in ascending order."""

    return gdf["Year"].dropna().astype(int).sort_values().unique().tolist()


def get_index_columns(gdf: gpd.GeoDataFrame) -> list[str]:
    """Find all normalized index columns from the merged dataset."""

    return [
        column
        for column in gdf.columns
        if column.startswith(INDEX_PREFIX) and column != "id"
    ]
