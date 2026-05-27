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

from .config import INDEX_PREFIX, FIELD_RISK_ORIENTATION


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
        return pd.Series([pd.NA] * len(group), index=group.index, dtype="float64")

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
        lambda value: str(int(value)) if pd.notna(value) else pd.NA
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


def build_risk_ranking(
    gdf: gpd.GeoDataFrame,
    metric_column: str,
    level: str = "cell",
    top_n: int = 10,
) -> gpd.GeoDataFrame:
    """Return the lowest-scoring locations for a selected metric.

    Lower normalized values mean higher risk, so the returned rows are sorted
    ascending on the selected metric.

    Args:
        gdf: Merged GeoDataFrame from load_dashboard_data().
        metric_column: Normalized `Index_*` column to rank.
        level: Either `cell` for 5 km squares or `subprefecture` for grouped areas.
        top_n: Number of rows to return.

    Returns:
        GeoDataFrame with rank, label, metric value, and highlight point coordinates.
    """
    if metric_column not in gdf.columns:
        return gpd.GeoDataFrame(columns=["rank", "label", "value", "lat", "lon", "geometry"])

    working = gdf.dropna(subset=[metric_column]).copy()

    if working.empty:
        return gpd.GeoDataFrame(columns=["rank", "label", "value", "lat", "lon", "geometry"])

    if level == "subprefecture":
        group_columns = [column for column in ["Prefecture", "Sous-prefecture"] if column in working.columns]
        if not group_columns:
            return gpd.GeoDataFrame(columns=["rank", "label", "value", "lat", "lon", "geometry"])

        grouped_rows = []
        for group_key, group in working.groupby(group_columns, dropna=False):
            if len(group_columns) == 1:
                prefecture = group_key if group_columns[0] == "Prefecture" else pd.NA
                sous_prefecture = group_key if group_columns[0] == "Sous-prefecture" else pd.NA
            else:
                prefecture, sous_prefecture = group_key
            geometry = group.geometry.unary_union
            representative = geometry.representative_point() if geometry is not None else None
            grouped_rows.append(
                {
                    "Prefecture": prefecture if "Prefecture" in group_columns else pd.NA,
                    "Sous-prefecture": sous_prefecture if "Sous-prefecture" in group_columns else pd.NA,
                    "value": group[metric_column].mean(skipna=True),
                    "geometry": representative,
                    "label": " | ".join([str(value) for value in [prefecture, sous_prefecture] if pd.notna(value)]),
                }
            )
        result = gpd.GeoDataFrame(grouped_rows, geometry="geometry", crs=working.crs)
    else:
        result = working.copy()
        result["label"] = result.apply(
            lambda row: " | ".join(
                [
                    str(value)
                    for value in [row.get("Prefecture", ""), row.get("Sous-prefecture", ""), row.get("id", "")]
                    if pd.notna(value)
                ]
            ),
            axis=1,
        )

    sort_column = metric_column if metric_column in result.columns else "value"
    # Determine sort direction based on field risk semantics
    # Default to ascending (lower values = more risk) if not in config
    ascending = FIELD_RISK_ORIENTATION.get(metric_column, "ascending") == "ascending"
    result = result.sort_values(sort_column, ascending=ascending).head(top_n).copy()
    result = result.reset_index(drop=True)
    result["rank"] = result.index + 1
    if metric_column in result.columns:
        result["value"] = result[metric_column]
    else:
        result["value"] = result["value"]
    result["factor_label"] = metric_column

    if "geometry" in result.columns:
        representative = result.geometry.representative_point()
        result["lon"] = representative.x
        result["lat"] = representative.y

    return result
