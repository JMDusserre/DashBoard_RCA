"""Tests for data loading and spatial aggregation."""

from __future__ import annotations

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box

from dashboard_rca.config import CSV_PATH, SHP_PATH
from dashboard_rca.data import (
    aggregate_by_resolution,
    is_valid_admin_label,
    load_dashboard_data,
)


@pytest.fixture(scope="module")
def dashboard_gdf() -> gpd.GeoDataFrame:
    if not CSV_PATH.exists() or not SHP_PATH.exists():
        pytest.skip("Dashboard data files not available")
    return load_dashboard_data(str(CSV_PATH), str(SHP_PATH), year=2021)


def test_load_preserves_nan_and_merges_one_to_one(dashboard_gdf: gpd.GeoDataFrame) -> None:
    assert len(dashboard_gdf) > 0
    assert dashboard_gdf.geometry.notna().all()
    assert dashboard_gdf["id"].is_unique
    index_cols = [c for c in dashboard_gdf.columns if c.startswith("Index_")]
    assert any(dashboard_gdf[c].isna().any() for c in index_cols)


def test_load_casts_admin3name(dashboard_gdf: gpd.GeoDataFrame) -> None:
    if "admin3name" not in dashboard_gdf.columns:
        pytest.skip("admin3name not in current dataset")
    assert pd.api.types.is_string_dtype(dashboard_gdf["admin3name"])
    labels = dashboard_gdf["admin3name"].dropna().astype(str).unique()
    assert all(is_valid_admin_label(label) for label in labels)


def test_gdp_aggregation_mean_then_base100(dashboard_gdf: gpd.GeoDataFrame) -> None:
    agg = aggregate_by_resolution(dashboard_gdf.copy(), "Prefecture (Admin 1)")
    gdp = pd.to_numeric(agg["Index_GDP"], errors="coerce").dropna()
    assert not gdp.empty
    assert gdp.max() == pytest.approx(100.0, rel=1e-6)
    assert gdp.min() >= 0.0


def test_all_indices_aggregated_by_mean_with_gdp_base100() -> None:
    gdf = gpd.GeoDataFrame(
        {
            "Prefecture": ["A", "A", "B"],
            "Index_GDP": [10.0, 30.0, 50.0],
            "Index_health": [20.0, 40.0, 60.0],
            "geometry": [box(0, 0, 1, 1)] * 3,
        },
        crs="EPSG:4326",
    )
    agg = aggregate_by_resolution(gdf, "Prefecture (Admin 1)")
    row_a = agg[agg["Prefecture"] == "A"].iloc[0]
    row_b = agg[agg["Prefecture"] == "B"].iloc[0]
    assert row_a["Index_GDP"] == pytest.approx(40.0)
    assert row_b["Index_GDP"] == pytest.approx(100.0)
    assert row_a["Index_health"] == pytest.approx(30.0)


def test_commune_resolution_groups_by_admin3name() -> None:
    gdf = gpd.GeoDataFrame(
        {
            "admin3name": ["C1", "C1", "C2"],
            "Index_GDP": [20.0, 40.0, 10.0],
            "Index_health": [50.0, 70.0, 30.0],
            "geometry": [box(0, 0, 1, 1)] * 3,
        },
        crs="EPSG:4326",
    )
    agg = aggregate_by_resolution(gdf, "Commune (Admin 3)")
    assert len(agg) == 2
    c1 = agg[agg["admin3name"] == "C1"].iloc[0]
    c2 = agg[agg["admin3name"] == "C2"].iloc[0]
    assert c1["Index_GDP"] == pytest.approx(100.0)
    assert c2["Index_GDP"] == pytest.approx(100.0 / 3.0)
    assert c1["Index_health"] == pytest.approx(60.0)


def test_commune_excludes_invalid_admin3name() -> None:
    gdf = gpd.GeoDataFrame(
        {
            "admin3name": ["C1", "nan", "C2"],
            "Prefecture": ["P1", "P1", "P2"],
            "Index_GDP": [20.0, 99.0, 10.0],
            "Index_health": [50.0, 50.0, 30.0],
            "geometry": [box(0, 0, 1, 1)] * 3,
        },
        crs="EPSG:4326",
    )
    agg = aggregate_by_resolution(gdf, "Commune (Admin 3)")
    assert len(agg) == 2
    assert all(is_valid_admin_label(v) for v in agg["admin3name"])


def test_secteur_resolution_returns_unchanged() -> None:
    gdf = gpd.GeoDataFrame(
        {"Prefecture": ["A"], "Index_GDP": [1.0], "geometry": [box(0, 0, 1, 1)]},
        crs="EPSG:4326",
    )
    result = aggregate_by_resolution(gdf, "Secteur (5×5 km)")
    assert len(result) == 1
    assert result["Index_GDP"].iloc[0] == 1.0
