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

# GDP indices must be SUMMED (not averaged) when aggregating cells to administrative
# units, because the data scientist has already population-weighted each value at
# cell level. Summing recovers the total economic activity for the territory.
# After summation they are renormalized to [0, 100] to preserve the UI scale.
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

    # Pre-cast administrative columns to str once at load time so ui.py never
    # calls .astype(str) at interaction time. NaN becomes the "nan" string,
    # which is filtered out downstream by get_prefecture_options().
    if "Prefecture" in merged.columns:
        merged["Prefecture"] = merged["Prefecture"].astype(str)
    if "Sous-prefecture" in merged.columns:
        merged["Sous-prefecture"] = merged["Sous-prefecture"].astype(str)

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
) -> pd.DataFrame:
    """Vectorized numeric aggregation using a single pandas groupby pass.

    Aggregation strategy:
    - GDP columns  (Index_GDP*): SUM across cells, then renormalize to [0, 100].
      Rationale: the data scientist pre-weights each cell by its population share,
      so summing cells within a territory recovers the total economic activity.
      Averaging would dilute high-GDP cells and produce a meaningless per-cell rate.
    - All other indices (access, risk, …): MEAN across cells.
      Rationale: these are rates/proportions that should be averaged over the
      territory, not summed.

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

    gdp_cols  = [c for c in available if c in GDP_COLUMNS]
    mean_cols = [c for c in available if c not in GDP_COLUMNS]

    agg_dict: dict[str, str] = {c: "sum" for c in gdp_cols}
    agg_dict.update({c: "mean" for c in mean_cols})

    result = num_df.groupby(group_col, dropna=False).agg(agg_dict).reset_index()

    return result


def aggregate_by_resolution(gdf: gpd.GeoDataFrame, resolution: str) -> gpd.GeoDataFrame:
    """Aggregate the GeoDataFrame to the selected spatial resolution.

    NOTE: @st.cache_data is intentionally NOT used here. The cache key would be
    built only from `resolution` (GeoDataFrames are unhashable), causing stale data
    to be returned when the territory filter changes between calls. The upstream
    `_cached_load` already caches the expensive data-loading step.

    Buffers removed: the previous expand/shrink buffer trick (+10 m / -10 m) was
    used to merge nearly-touching polygons before dissolve. It added two O(N)
    geometry operations on 20k+ polygons. A zero-width buffer after dissolve is
    sufficient to repair any invalid geometries without the performance cost.

    Args:
        gdf: GeoDataFrame at grid-cell resolution, already territory-filtered.
        resolution: one of the human-facing options defined in config.SPATIAL_RESOLUTIONS.

    Returns:
        Aggregated GeoDataFrame dissolved by the chosen administrative unit.
        GDP columns are summed then renormalized; all other indices are averaged.
        Returns gdf unchanged for Secteur (grid-cell) resolution.
    """
    # No defensive copy here: the caller (ui.py) already passes .copy() slices.
    # We mutate geometry in-place for the buffer, then dissolve, keeping only
    # one working instance in memory instead of the previous two copies.
    group_col = _resolve_grouping_column(gdf, resolution)
    if group_col is None:
        return gdf

    numeric_columns = [c for c in gdf.columns if c.startswith(INDEX_PREFIX)]
    numeric_df = _compute_numeric_aggregations(gdf, group_col, numeric_columns)

    # A micro-buffer of 0.001° closes sub-pixel gaps between adjacent grid cells
    # before dissolve, preventing sliver artefacts on the rendered map.
    # The negative buffer afterwards restores the original boundaries.
    # Operating in geographic CRS (degrees) keeps the operation fast — no UTM
    # reprojection needed for a purely topological fix at this scale.
    gdf = gdf.copy()  # single protective copy before geometry mutation
    gdf["geometry"] = gdf.geometry.buffer(0.001)

    dissolved = gdf.dissolve(by=group_col).reset_index()

    # Drop raw numeric columns from dissolved output; they will be re-joined
    # from numeric_df which contains the correctly aggregated values.
    cols_to_drop = [c for c in numeric_columns if c in dissolved.columns and c != group_col]
    dissolved = dissolved.drop(columns=cols_to_drop)

    # Shrink back and fix any invalid geometries left by the dissolve in one pass.
    if "geometry" in dissolved.columns:
        dissolved["geometry"] = dissolved["geometry"].buffer(-0.001).buffer(0)

    merged = dissolved.merge(numeric_df, on=group_col, how="left")
    merged = gpd.GeoDataFrame(merged, geometry="geometry", crs=gdf.crs)

    return merged
