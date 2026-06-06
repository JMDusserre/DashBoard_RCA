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

from .config import INDEX_PREFIX, HUMAN_CENTRIC_METRICS

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

    if "Year" in csv_frame.columns:
        csv_frame["Year"] = pd.to_numeric(csv_frame["Year"], errors="coerce")
        if year is not None:
            csv_frame = csv_frame[csv_frame["Year"].eq(year)].copy()

    # Rename Idx_* to Index_*, then scale [0, 1] → [0, 100] for display.
    rename_idx = {src: dst for src, dst in NORMALIZED_PROXY_MAP.items() if src in csv_frame.columns}
    if rename_idx:
        csv_frame = csv_frame.rename(columns=rename_idx)
    csv_frame = _scale_index_columns_to_hundred(csv_frame)

    # Left join keeps all spatial features; NaN for cells without CSV data.
    # validate="1:1" ensures no duplicate keys (data integrity check).
    merged = spatial_frame.merge(csv_frame, on="id", how="left", validate="1:1")

    if "Prefecture" not in merged.columns and "NEW_NAME_1" in merged.columns:
        merged = merged.rename(columns={"NEW_NAME_1": "Prefecture"})
    if "Sous-prefecture" not in merged.columns and "ADM2_FR" in merged.columns:
        merged = merged.rename(columns={"ADM2_FR": "Sous-prefecture"})

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
        return gdf["Prefecture"].dropna().astype(str).sort_values().unique().tolist()

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
        if column.startswith(INDEX_PREFIX) and column != "id"
    ]


def compute_overall_vulnerability(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Pass-through: Index_Vulnerab_Final is pre-computed in the source CSV.

    The data scientist (Vincent) provides a fully pre-normalized Idx_Vulnerab_Final
    column, which is renamed to Index_Vulnerab_Final during load_dashboard_data().
    No recomputation is performed here.
    """
    return gdf


def _resolve_grouping_column(gdf: gpd.GeoDataFrame, resolution: str) -> str | None:
    """Resolve the grouping column based on resolution string.

    Args:
        gdf: GeoDataFrame to check for available columns
        resolution: Resolution option (e.g., "Prefecture", "Sous-prefecture")

    Returns:
        Column name or None if not found or grid-cell resolution selected.
    """
    if resolution.startswith("Grid Cell") or resolution.startswith("Secteur"):
        return None
    if resolution.startswith("Prefecture"):
        return "Prefecture" if "Prefecture" in gdf.columns else None
    elif resolution.startswith("Sous-prefecture"):
        return "Sous-prefecture" if "Sous-prefecture" in gdf.columns else None

    return None


def _compute_numeric_aggregations(
    working_gdf: gpd.GeoDataFrame,
    group_col: str,
    numeric_columns: list[str],
    pop_col: str | None = None,
) -> pd.DataFrame:
    """Compute numeric aggregations with population masking for human-centric metrics.

    Args:
        working_gdf: GeoDataFrame to aggregate
        group_col: Column to group by
        numeric_columns: List of numeric columns to aggregate
        pop_col: Optional population column for masking human-centric metrics

    Returns:
        DataFrame with aggregated numeric values, respecting population mask.
    """
    aggregated_values = []

    for group_key, group in working_gdf.groupby(group_col, dropna=False):
        row = {group_col: group_key}

        for col in numeric_columns:
            try:
                if col in HUMAN_CENTRIC_METRICS and pop_col is not None:
                    population_mask = pd.to_numeric(group[pop_col], errors="coerce") > 0
                    valid_group = group[population_mask]
                    if not valid_group.empty:
                        val = pd.to_numeric(valid_group[col], errors="coerce").mean(skipna=True)
                    else:
                        val = np.nan
                else:
                    val = pd.to_numeric(group[col], errors="coerce").mean(skipna=True)
            except Exception:
                val = np.nan

            row[col] = val

        aggregated_values.append(row)

    return pd.DataFrame(aggregated_values)


def aggregate_by_resolution(gdf: gpd.GeoDataFrame, resolution: str) -> gpd.GeoDataFrame:
    """Aggregate the GeoDataFrame to the selected spatial resolution.

    NOTE: @st.cache_data is intentionally NOT used here. The cache key would be
    built only from `resolution` (GeoDataFrames are unhashable), causing stale data
    to be returned when the territory filter changes between calls. The upstream
    `_cached_load` already caches the expensive data-loading step.

    Args:
        gdf: input GeoDataFrame at grid-cell resolution, already filtered by territory
        resolution: one of the human-facing options defined in config.SPATIAL_RESOLUTIONS

    Returns:
        Aggregated GeoDataFrame where geometries are dissolved by the chosen
        administrative unit and numeric metrics are averaged (mean).
        For grid-cell resolution, returns gdf unchanged (caller handles this case).
    """
    gdf = gdf.copy()

    group_col = _resolve_grouping_column(gdf, resolution)

    if group_col is None:
        return gdf

    target_crs = gdf.estimate_utm_crs() if gdf.crs and gdf.crs.is_geographic else gdf.crs
    working_gdf = gdf.to_crs(target_crs) if target_crs and target_crs != gdf.crs else gdf.copy()
    buffer_distance = 10.0
    working_gdf[working_gdf.geometry.name] = working_gdf.geometry.buffer(buffer_distance)

    numeric_columns = [c for c in working_gdf.columns if c.startswith(INDEX_PREFIX)]
    pop_col: str | None = None

    numeric_df = _compute_numeric_aggregations(working_gdf, group_col, numeric_columns, pop_col)

    for col in numeric_columns:
        if col in numeric_df.columns:
            numeric_df[col] = pd.to_numeric(numeric_df[col], errors="coerce")

    dissolved = working_gdf.dissolve(by=group_col)
    dissolved = dissolved.reset_index()

    cols_to_drop = [c for c in numeric_columns if c in dissolved.columns and c != group_col]
    dissolved = dissolved.drop(columns=cols_to_drop)

    dissolved[dissolved.geometry.name] = dissolved.geometry.buffer(-buffer_distance)
    merged = dissolved.merge(numeric_df, on=group_col, how="left")

    if target_crs and gdf.crs and target_crs != gdf.crs:
        merged = merged.to_crs(gdf.crs)
    if "geometry" in merged.columns:
        merged["geometry"] = merged["geometry"].buffer(0)
    merged = gpd.GeoDataFrame(merged, geometry="geometry", crs=gdf.crs)

    return merged
