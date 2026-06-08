"""Data loading and schema helpers for the dashboard.

This module handles all data pipeline operations: CSV/shapefile loading,
type casting, validation, and schema discovery.

RR_WLD 2025-520 Data Reality:
    - Source: Base_CAF_AllIndexes_ForPlatform.csv (pre-normalized by data scientist).
    - Raw Idx_* columns are normalized [0, 1] in the CSV; scaled to [0, 100] at load time.
    - NORMALIZED_PROXY_MAP renames Idx_* CSV columns to the application's Index_* convention.
    - String ID casting is critical: it prevents silent merge failures on float vs int.
    - ~68% of index values are NaN due to field insecurity preventing data collection
      in those grid cells. This is a feature, not a bug. NaN is preserved throughout.
"""

from __future__ import annotations

import geopandas as gpd
import pandas as pd
import numpy as np

from .config import INDEX_PREFIX

INVALID_ADMIN_LABELS: frozenset[str] = frozenset({"nan", "None", ""})


def is_valid_admin_label(value: object) -> bool:
    """Return True when *value* is a usable administrative place name."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    return str(value).strip() not in INVALID_ADMIN_LABELS


# GDP columns re-scaled to base 100 after territorial mean aggregation.
GDP_COLUMNS: frozenset[str] = frozenset({
    "Index_GDP",
    "Index_GDP_prim",
    "Index_GDP_sec_ter",
})

# Maps source CSV Idx_* column names to the application's Index_* column names.
# All source values are pre-normalized [0, 1] by the data scientist.
# Key = CSV column name, Value = application column name.
NORMALIZED_PROXY_MAP = {
    "Idx_GDP":            "Index_GDP",
    "Idx_GDP_prim":       "Index_GDP_prim",
    "Idx_GDP_sec_ter":    "Index_GDP_sec_ter",
    "Idx_educ_prim":      "Index_educ_prim",
    "Idx_health":         "Index_health",
    "Idx_water_access":   "Index_water_access",
    "Idx_Vulnerab_Final": "Index_Vulnerab_Final",
    "Idx_floods":         "Index_floods",
    "Idx_conflicts":      "Index_conflicts",
    "Idx_Infrastructure": "Index_Infrastructure",
    "Idx_ExpoRisk":       "Index_ExpoRisk",
}


def _scale_index_columns_to_hundred(frame: pd.DataFrame) -> pd.DataFrame:
    """Convert normalized [0, 1] index columns to intuitive [0, 100] scores."""
    result = frame.copy()
    for column in result.columns:
        if column.startswith(INDEX_PREFIX):
            result[column] = pd.to_numeric(result[column], errors="coerce") * 100
    return result


def load_dashboard_data(
    csv_path: str,
    shp_path: str,
    year: int | None = None,
) -> gpd.GeoDataFrame:
    """Load and merge the pre-normalized CSV and shapefile into a GeoDataFrame.

    CRITICAL DESIGN DECISION - String ID Casting:
      CSV `id` column is int; shapefile `id` column is float. Numeric joins on
      mixed float/int types fail silently, producing incorrect merge results.
      We explicitly cast both to str BEFORE merging to catch mismatches early
      and ensure 1:1 validation passes with correct row counts.

    CRITICAL DESIGN DECISION - NaN Handling:
      ~68% of access/conflict indices are NaN due to field insecurity, not data entry
      errors. We preserve NaN values throughout the pipeline (never drop, never impute)
      to keep the dashboard honest about field realities.

    CRITICAL DESIGN DECISION - Column Rename + Score Scaling:
      Source data is normalized [0, 1] by the data scientist. NORMALIZED_PROXY_MAP
      renames Idx_* → Index_*, then values are multiplied by 100 for UI readability.

    Args:
        csv_path: Path to the AllIndexes CSV (pre-normalized tabular source data)
        shp_path: Path to the 5x5 km grid shapefile
        year: Optional year filter. The CSV is a panel; filtering before the merge
            keeps the join one-to-one.

    Returns:
        GeoDataFrame with spatial geometries and left-joined CSV fields.
        Rows without CSV data have NaN for all index columns.

    Raises:
        FileNotFoundError: If CSV or SHP files are missing.
    """
    try:
        # index_col=0 drops the unnamed row-index column present in the source CSV.
        csv_frame = pd.read_csv(csv_path, index_col=0, na_values=["NA", "NaN", ""])
        spatial_frame = gpd.read_file(shp_path)
        if "admin3Name" in spatial_frame.columns:
            spatial_frame = spatial_frame.rename(columns={"admin3Name": "admin3name"})
        spatial_frame['geometry'] = spatial_frame['geometry'].simplify(tolerance=0.005, preserve_topology=True)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            "The dashboard data files could not be found. Check the RR_WLD_2025_520 "
            "Inputs/Base_CAF_AllIndexes_ForPlatform.csv and Inputs/GIS/Grid_5km_CFA_v4.shp files."
        ) from exc

    # DESIGN: Cast id to string BEFORE merge to prevent silent float vs int join failure.
    csv_frame["id"] = csv_frame["id"].astype(str)
    spatial_frame["id"] = spatial_frame["id"].apply(
        lambda value: str(int(value)) if pd.notna(value) else np.nan
    )

    # Rename administrative columns to dashboard vocabulary.
    rename_map: dict[str, str] = {}
    if "Prefecture" not in csv_frame.columns and "NEW_NAME_1" in csv_frame.columns:
        rename_map["NEW_NAME_1"] = "Prefecture"
    if "Sous-prefecture" not in csv_frame.columns and "ADM2_FR" in csv_frame.columns:
        rename_map["ADM2_FR"] = "Sous-prefecture"
    if rename_map:
        csv_frame = csv_frame.rename(columns=rename_map)
    if "admin3Name" in csv_frame.columns:
        csv_frame = csv_frame.rename(columns={"admin3Name": "admin3name"})

    if "Year" in csv_frame.columns:
        csv_frame["Year"] = pd.to_numeric(csv_frame["Year"], errors="coerce")
        if year is not None:
            csv_frame = csv_frame[csv_frame["Year"].eq(year)].copy()

    # Rename Idx_* to Index_*, then scale [0, 1] → [0, 100] for display.
    rename_idx = {src: dst for src, dst in NORMALIZED_PROXY_MAP.items() if src in csv_frame.columns}
    if rename_idx:
        csv_frame = csv_frame.rename(columns=rename_idx)
    csv_frame = _scale_index_columns_to_hundred(csv_frame)

    # Prefer the CSV commune label when both frames carry admin3name.
    if "admin3name" in spatial_frame.columns and "admin3name" in csv_frame.columns:
        spatial_frame = spatial_frame.drop(columns=["admin3name"])

    # Left join keeps all spatial features; NaN for cells without CSV data.
    # validate="1:1" ensures no duplicate keys (data integrity check).
    merged = spatial_frame.merge(csv_frame, on="id", how="left", validate="1:1")

    if "admin3name_x" in merged.columns or "admin3name_y" in merged.columns:
        left = merged.get("admin3name_x")
        right = merged.get("admin3name_y")
        merged["admin3name"] = right if left is None else (right.fillna(left) if right is not None else left)
        drop_cols = [c for c in ("admin3name_x", "admin3name_y") if c in merged.columns]
        merged = merged.drop(columns=drop_cols)

    # Pre-cast administrative columns to str once at load time so ui.py never
    # calls .astype(str) at interaction time. NaN becomes the "nan" string,
    # which is filtered out downstream by get_prefecture_options().
    if "Prefecture" in merged.columns:
        merged["Prefecture"] = merged["Prefecture"].astype(str)
    if "Sous-prefecture" in merged.columns:
        merged["Sous-prefecture"] = merged["Sous-prefecture"].astype(str)
    if "admin3name" in merged.columns:
        merged["admin3name"] = merged["admin3name"].astype(str)

    return merged


def get_csv_year_options(csv_path: str) -> list[int]:
    """Read the raw CSV and return available years before the spatial merge.

    Reads only the `Year` column to keep this cheap and avoid loading the full table twice.
    """
    csv_frame = pd.read_csv(csv_path, usecols=["Year"], na_values=["NA", "NaN", ""])
    return pd.to_numeric(csv_frame["Year"], errors="coerce").dropna().astype(int).sort_values().unique().tolist()


def get_prefecture_options(gdf: gpd.GeoDataFrame) -> list[str]:
    """Return a clean, deterministic list of prefecture names.

    Filters out NaN (some grid cells lack prefecture assignment) and sorts
    alphabetically for consistent UI presentation across app restarts.

    Args:
        gdf: Merged GeoDataFrame from load_dashboard_data()

    Returns:
        Sorted list of unique prefecture names (str).
    """
    if "Prefecture" in gdf.columns:
        # After load_dashboard_data(), Prefecture is already str; NaN becomes "nan".
        return sorted(v for v in gdf["Prefecture"].unique() if v not in ("nan", "None", ""))

    if "NEW_NAME_1" in gdf.columns:
        return gdf["NEW_NAME_1"].dropna().astype(str).sort_values().unique().tolist()

    return []


def get_index_columns(gdf: gpd.GeoDataFrame) -> list[str]:
    """Find all normalized index columns from the merged dataset.

    DESIGN: Dynamic discovery allows new indices to be added to the source CSV
    without code changes. This is future-proof for World Bank PRWP 11309 updates.

    Args:
        gdf: Merged GeoDataFrame from load_dashboard_data()

    Returns:
        List of all columns starting with INDEX_PREFIX (e.g., "Index_GDP").
    """
    return [
        column
        for column in gdf.columns
        if column.startswith(INDEX_PREFIX)
    ]


def _resolve_grouping_column(gdf: gpd.GeoDataFrame, resolution: str) -> str | None:
    """Resolve the grouping column based on the canonical resolution key.

    Args:
        gdf: GeoDataFrame to check for available columns
        resolution: One of config.SPATIAL_RESOLUTIONS (e.g. "Prefecture (Admin 1)")

    Returns:
        Column name or None if not found or grid-cell resolution selected.
    """
    if resolution == "Secteur (5×5 km)":
        return None
    if resolution == "Commune (Admin 3)":
        return "admin3name" if "admin3name" in gdf.columns else None
    if resolution == "Prefecture (Admin 1)":
        return "Prefecture" if "Prefecture" in gdf.columns else None
    if resolution == "Sous-prefecture (Admin 2)":
        return "Sous-prefecture" if "Sous-prefecture" in gdf.columns else None

    return None


def _compute_numeric_aggregations(
    working_gdf: gpd.GeoDataFrame,
    group_col: str,
    numeric_columns: list[str],
) -> pd.DataFrame:
    """Vectorized numeric aggregation using a single pandas groupby pass.

    All Index_* columns are averaged (``.mean()``) when dissolving to an admin unit.
    GDP columns are then re-normalised to base 100 within the current view:
    ``(col / col.max()) * 100`` so the strongest unit scores 100.

    Args:
        working_gdf: GeoDataFrame to aggregate.
        group_col: Column name to group by (e.g. "Prefecture").
        numeric_columns: Index_* columns to aggregate.

    Returns:
        DataFrame with one row per group and one column per numeric metric.
    """
    available = [c for c in numeric_columns if c in working_gdf.columns]
    if not available:
        return pd.DataFrame({group_col: working_gdf[group_col].unique()})

    # Coerce all target columns to numeric up-front.
    num_df = working_gdf[[group_col] + available].copy()
    for col in available:
        num_df[col] = pd.to_numeric(num_df[col], errors="coerce")

    agg_dict: dict[str, str] = {c: "mean" for c in available}
    result = num_df.groupby(group_col, dropna=False).agg(agg_dict).reset_index()

    for col in available:
        if col not in GDP_COLUMNS:
            continue
        series = pd.to_numeric(result[col], errors="coerce")
        vmax = series.max(skipna=True)
        if pd.notna(vmax) and vmax > 0:
            result[col] = series / vmax * 100.0

    return result


def aggregate_by_resolution(gdf: gpd.GeoDataFrame, resolution: str) -> gpd.GeoDataFrame:
    """Aggregate the GeoDataFrame to the selected spatial resolution.

    Caching is handled in ``ui._cached_aggregation`` with an explicit territory
    key so GeoDataFrames are never hashed directly.

    Buffers removed: the previous expand/shrink buffer trick (+10 m / -10 m) was
    used to merge nearly-touching polygons before dissolve. It added two O(N)
    geometry operations on 20k+ polygons. A zero-width buffer after dissolve is
    sufficient to repair any invalid geometries without the performance cost.

    Args:
        gdf: GeoDataFrame at grid-cell resolution, already territory-filtered.
        resolution: one of the human-facing options defined in config.SPATIAL_RESOLUTIONS.

    Returns:
        Aggregated GeoDataFrame dissolved by the chosen administrative unit.
        All indices are averaged; GDP columns are then scaled to base 100 (max = 100).
        Returns gdf unchanged for Secteur (grid-cell) resolution.
    """
    # No defensive copy here: the caller (ui.py) already passes .copy() slices.
    # We mutate geometry in-place for the buffer, then dissolve, keeping only
    # one working instance in memory instead of the previous two copies.
    group_col = _resolve_grouping_column(gdf, resolution)
    if group_col is None:
        return gdf

    working = gdf
    if group_col == "admin3name":
        working = gdf[gdf[group_col].map(is_valid_admin_label)].copy()
        if working.empty:
            return working

    numeric_columns = [c for c in gdf.columns if c.startswith(INDEX_PREFIX)]
    numeric_df = _compute_numeric_aggregations(working, group_col, numeric_columns)

    # Micro-buffer in a projected CRS (metres) closes sub-pixel gaps between
    # adjacent grid cells before dissolve. Geographic degree buffers are unreliable.
    _BUF_M = 150.0
    _WORK_CRS = "EPSG:3857"
    source_crs = working.crs

    gdf = working.copy()
    gdf_proj = gdf.to_crs(_WORK_CRS)
    gdf_proj["geometry"] = gdf_proj.geometry.buffer(_BUF_M)

    dissolved = gdf_proj.dissolve(by=group_col).reset_index()

    cols_to_drop = [c for c in numeric_columns if c in dissolved.columns and c != group_col]
    dissolved = dissolved.drop(columns=cols_to_drop)

    if "geometry" in dissolved.columns:
        dissolved["geometry"] = dissolved["geometry"].buffer(-_BUF_M).buffer(0)

    dissolved = dissolved.to_crs(source_crs)

    merged = dissolved.merge(numeric_df, on=group_col, how="left")
    merged = gpd.GeoDataFrame(merged, geometry="geometry", crs=source_crs)

    return merged
