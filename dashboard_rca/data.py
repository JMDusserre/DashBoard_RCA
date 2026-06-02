"""Data loading and schema helpers for the dashboard.

This module handles all data pipeline operations: CSV/shapefile loading,
type casting, validation, and schema discovery. The critical constraint is
NaN handling: ~47% of indices are missing because field insecurity prevented
data collection in those grid cells. This is a feature (reflects reality),
not a bug. We preserve NaN patterns throughout to ensure honest reporting.

RR_WLD 2025-520 Data Reality:
    - The active package contains the raw CAR grid source table plus the 5 km grid.
    - The dashboard derives normalized proxy layers from the available raw columns.
    - String ID casting is critical: it prevents silent merge failures on float vs int.
"""

from __future__ import annotations

import geopandas as gpd
import pandas as pd
import numpy as np

from .config import INDEX_PREFIX, HUMAN_CENTRIC_METRICS


RAW_PROXY_COLUMNS = [
    "NTLsum",
    "NTLmean",
    "population",
    "BuiltUp",
    "Water",
    "share_forest",
    "share_cropland",
    "share_builtup",
    "share_deforest",
    "share_NDVI",
    "Main_Mines",
    "Diamond_ArtisanalMines",
    "Boutiques",
]

NORMALIZED_PROXY_MAP = {
    "Index_NTLsum": "NTLsum",
    "Index_NTLmean": "NTLmean",
    "Index_population": "population",
    "Index_BuiltUp": "BuiltUp",
    "Index_Water": "Water",
    "Index_share_forest": "share_forest",
    "Index_share_cropland": "share_cropland",
    "Index_share_builtup": "share_builtup",
    "Index_share_deforest": "share_deforest",
    "Index_share_NDVI": "share_NDVI",
    "Index_Main_Mines": "Main_Mines",
    "Index_Diamond_ArtisanalMines": "Diamond_ArtisanalMines",
    "Index_Boutiques": "Boutiques",
}


def _normalize_group(group: pd.Series) -> pd.Series:
    """Normalize a numeric series to the [0, 1] interval.

    The raw RR_WLD package contains mixed-scale variables (counts, ratios,
    and sums). Normalizing them makes the dashboard comparable across metrics.
    When all values are identical, we return 0.0 instead of dividing by zero.
    """
    numeric_group = pd.to_numeric(group, errors="coerce")
    minimum = numeric_group.min(skipna=True)
    maximum = numeric_group.max(skipna=True)

    if pd.isna(minimum) or pd.isna(maximum) or maximum == minimum:
        return pd.Series([np.nan] * len(group), index=group.index, dtype="float64")

    return (numeric_group - minimum) / (maximum - minimum)


def _add_proxy_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Add normalized proxy columns that drive the Streamlit dashboard.

    We keep the raw variables intact and create `Index_*` proxy columns so the
    rest of the application can remain label-driven and easy to extend.
    Normalization is performed within each year when the `Year` column exists.
    """
    result = frame.copy()

    if "Year" in result.columns:
        for target_column, source_column in NORMALIZED_PROXY_MAP.items():
            if source_column not in result.columns:
                continue
            result[target_column] = result.groupby("Year", dropna=False)[source_column].transform(_normalize_group)
    else:
        for target_column, source_column in NORMALIZED_PROXY_MAP.items():
            if source_column not in result.columns:
                continue
            result[target_column] = _normalize_group(result[source_column])

    return result


def load_dashboard_data(
    csv_path: str,
    shp_path: str,
    year: int | None = None,
) -> gpd.GeoDataFrame:
    """Load, normalize, and merge CSV and shapefile into a GeoDataFrame.
    
    CRITICAL DESIGN DECISION - String ID Casting:
      CSV `id` column is int; shapefile `id` column is float. Numeric joins on
      mixed float/int types fail silently, producing incorrect merge results.
      We explicitly cast both to str BEFORE merging to catch mismatches early
      and ensure 1:1 validation passes with correct row counts.
    
    CRITICAL DESIGN DECISION - NaN Handling:
      ~47% of access/conflict indices are NaN due to field insecurity, not data entry
      errors. We preserve NaN values throughout the pipeline (never drop, never impute)
      to keep the dashboard honest about field realities. Missing data is explained
      in UI as "unreachable due to field insecurity", not "unknown".
    
    Args:
        csv_path: Path to the RR_WLD panel CSV (tabular source data)
        shp_path: Path to the 5x5 km grid shapefile
        year: Optional year filter. The RR_WLD CSV is a panel, so filtering
            before the merge keeps the join one-to-one.
    
    Returns:
        GeoDataFrame with spatial geometries and left-joined CSV fields.
        Rows without CSV data have NaN for all index columns.
        
    Raises:
        FileNotFoundError: If CSV or SHP files are missing.
    """
    try:
        csv_frame = pd.read_csv(csv_path, na_values=["NA", "NaN", ""])
        spatial_frame = gpd.read_file(shp_path)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            "The dashboard data files could not be found. Check the RR_WLD_2025_520 "
            "Inputs/Base_CAF_v1.csv and Inputs/GIS/Grid_5km_CFA_v4.shp files."
        ) from exc

    # DESIGN: Cast id to string BEFORE merge to prevent silent float vs int join failure.
    # This ensures validate="1:1" will reliably catch any key mismatches.
    csv_frame["id"] = csv_frame["id"].astype(str)
    spatial_frame["id"] = spatial_frame["id"].apply(
        lambda value: str(int(value)) if pd.notna(value) else np.nan
    )

    # The RR_WLD package uses raw territorial names; rename them into the dashboard
    # vocabulary so the UI can keep using "Prefecture" and "Sous-prefecture".
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

    csv_frame = _add_proxy_columns(csv_frame)

    # Left join keeps all 20,817 spatial features; NaN for cells without CSV data.
    # validate="1:1" ensures no duplicate keys (data integrity check).
    merged = spatial_frame.merge(csv_frame, on="id", how="left", validate="1:1")

    if "Prefecture" not in merged.columns and "NEW_NAME_1" in merged.columns:
        merged = merged.rename(columns={"NEW_NAME_1": "Prefecture"})
    if "Sous-prefecture" not in merged.columns and "ADM2_FR" in merged.columns:
        merged = merged.rename(columns={"ADM2_FR": "Sous-prefecture"})

    return merged


def get_csv_year_options(csv_path: str) -> list[int]:
    """Read the raw CSV and return available years before the spatial merge.

    The RR_WLD panel table stores one row per grid cell and year, so the year
    selector must be populated before we merge against the shapefile. Reading
    only the `Year` column keeps this cheap and avoids loading the full table twice.
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


def get_year_options(gdf: gpd.GeoDataFrame) -> list[int]:
    """Return the available years in ascending order.
    
    Filters NaN years (unmatched spatial features) and returns unique years.
    Sorted for UI selectbox to show oldest data first.
    
    Args:
        gdf: Merged GeoDataFrame from load_dashboard_data()
    
    Returns:
        Sorted list of unique years (int) in ascending order.
    """
    return gdf["Year"].dropna().astype(int).sort_values().unique().tolist()


def get_index_columns(gdf: gpd.GeoDataFrame) -> list[str]:
    """Find all normalized index columns from the merged dataset.
    
    DESIGN: Dynamic discovery allows new indices to be added to Sample_RCA.csv
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
    """Compute an active-data proxy for overall vulnerability.

    The workspace does not include the archived official PRWP component layers,
    so this function builds a transparent proxy index from the normalized active
    `Index_*` layers that are available in the bundle.

    The proxy is scaled so that higher values mean higher vulnerability.
    """
    result = gdf.copy()

    component_groups = {
        # Lower access or lower activity implies higher vulnerability, so these are inverted.
        "access_proxy": [
            "Index_NTLsum",
            "Index_NTLmean",
            "Index_Water",
            "Index_BuiltUp",
            "Index_share_builtup",
            "Index_share_cropland",
        ],
        # Higher pressure/exposure implies higher vulnerability, so these are used directly.
        "pressure_proxy": [
            "Index_population",
            "Index_Deforest",
            "Index_Main_Mines",
            "Index_Diamond_ArtisanalMines",
            "Index_Boutiques",
        ],
    }

    access_values: list[pd.Series] = []
    for column in component_groups["access_proxy"]:
        if column in result.columns:
            access_values.append(1 - pd.to_numeric(result[column], errors="coerce"))

    pressure_values: list[pd.Series] = []
    for column in component_groups["pressure_proxy"]:
        if column in result.columns:
            pressure_values.append(pd.to_numeric(result[column], errors="coerce"))

    all_components = access_values + pressure_values
    if not all_components:
        result["Index_Vulnerab_Final"] = np.nan
        return result

    component_frame = pd.concat(all_components, axis=1)
    result["Index_Vulnerab_Final"] = component_frame.mean(axis=1, skipna=True)

    return result


def _resolve_grouping_column(gdf: gpd.GeoDataFrame, resolution: str) -> str | None:
    """Resolve the grouping column based on resolution string.
    
    Args:
        gdf: GeoDataFrame to check for available columns
        resolution: Resolution option (e.g., "Prefecture", "Sous-prefecture", "City")
    
    Returns:
        Column name or None if not found or Grid cell resolution selected.
    """
    if resolution.startswith("Grid cell"):
        return None
    
    if resolution.startswith("Prefecture"):
        return "Prefecture" if "Prefecture" in gdf.columns else None
    elif resolution.startswith("Sous-prefecture"):
        return "Sous-prefecture" if "Sous-prefecture" in gdf.columns else None
    elif resolution.startswith("City"):
        return next((c for c in ["City", "ADM3", "ADMIN3"] if c in gdf.columns), None)
    
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

    Args:
        gdf: input GeoDataFrame at grid-cell resolution
        resolution: one of the human-facing options defined in config.SPATIAL_RESOLUTIONS

    Returns:
        Aggregated GeoDataFrame where geometries are dissolved by the chosen
        administrative unit and numeric metrics are averaged (mean).
    """
    gdf = gdf.copy()

    # Resolve grouping column based on resolution
    group_col = _resolve_grouping_column(gdf, resolution)
    
    if group_col is None:
        return gdf

    # Prepare CRS for geometry operations
    target_crs = gdf.estimate_utm_crs() if gdf.crs and gdf.crs.is_geographic else gdf.crs
    working_gdf = gdf.to_crs(target_crs) if target_crs and target_crs != gdf.crs else gdf.copy()
    buffer_distance = 10.0
    working_gdf[working_gdf.geometry.name] = working_gdf.geometry.buffer(buffer_distance)

    # Compute numeric aggregations with population masking
    numeric_columns = [c for c in working_gdf.columns if c.startswith("Index_") or c in ["population", "NTLsum"]]
    pop_col = "population" if "population" in working_gdf.columns else (
        "Index_population" if "Index_population" in working_gdf.columns else None
    )
    
    numeric_df = _compute_numeric_aggregations(working_gdf, group_col, numeric_columns, pop_col)

    # Force cast to float to prevent 'object' dtype breaking Plotly continuous scales
    for col in numeric_columns:
        if col in numeric_df.columns:
            numeric_df[col] = pd.to_numeric(numeric_df[col], errors="coerce")

    # Merge with dissolved geometries
    dissolved = working_gdf.dissolve(by=group_col)
    dissolved = dissolved.reset_index()
    
    # SOLUTION: Drop old numeric columns from dissolved to prevent _x and _y suffix collision
    cols_to_drop = [c for c in numeric_columns if c in dissolved.columns and c != group_col]
    dissolved = dissolved.drop(columns=cols_to_drop)

    dissolved[dissolved.geometry.name] = dissolved.geometry.buffer(-buffer_distance)
    merged = dissolved.merge(numeric_df, on=group_col, how="left")

    # Finalize CRS and geometry
    if target_crs and gdf.crs and target_crs != gdf.crs:
        merged = merged.to_crs(gdf.crs)
    if "geometry" in merged.columns:
        merged["geometry"] = merged["geometry"].buffer(0)
    merged = gpd.GeoDataFrame(merged, geometry="geometry", crs=gdf.crs)

    return merged


