"""Tests for UI helper logic (no Streamlit runtime required)."""

from __future__ import annotations

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box

from dashboard_rca.ui import (
    ZONE_KEY_SEP,
    _compute_kpi_values,
    _detail_zone_column,
    _detail_zone_options,
    _filter_detail_rows,
    _format_detail_zone_key,
    _inhabited_mask,
    _is_admin_resolution,
    _kpi_source_gdf,
)


def test_inhabited_mask_falls_back_to_human_centric_columns() -> None:
    gdf = gpd.GeoDataFrame(
        {
            "Index_health": [float("nan"), 40.0],
            "Index_water_access": [float("nan"), float("nan")],
            "geometry": [box(0, 0, 1, 1), box(1, 0, 2, 1)],
        },
        crs="EPSG:4326",
    )
    mask = _inhabited_mask(gdf, pop_col=None)
    assert mask.tolist() == [False, True]


def test_detail_zone_column_by_resolution() -> None:
    assert _detail_zone_column("Secteur (5×5 km)") == "id"
    assert _detail_zone_column("Commune (Admin 3)") == "admin3name"
    assert _detail_zone_column("Prefecture (Admin 1)") == "Prefecture"
    assert _detail_zone_column("Sous-prefecture (Admin 2)") == "Sous-prefecture"


def test_detail_zone_options_prefecture_names() -> None:
    gdf = gpd.GeoDataFrame(
        {
            "Prefecture": ["Bangui", "Ouham"],
            "id": ["1", "2"],
            "geometry": [box(0, 0, 1, 1), box(1, 0, 2, 1)],
        },
        crs="EPSG:4326",
    )
    assert _detail_zone_options(gdf, "Prefecture (Admin 1)") == ["Bangui", "Ouham"]


def test_detail_zone_commune_composite_key() -> None:
    gdf = gpd.GeoDataFrame(
        {
            "admin3name": ["Boda", "Boda"],
            "Prefecture": ["Lobaye", "Ombella-M'Poko"],
            "Index_GDP": [10.0, 20.0],
            "geometry": [box(0, 0, 1, 1), box(1, 0, 2, 1)],
        },
        crs="EPSG:4326",
    )
    options = _detail_zone_options(gdf, "Commune (Admin 3)")
    assert f"Boda{ZONE_KEY_SEP}Lobaye" in options
    assert f"Boda{ZONE_KEY_SEP}Ombella-M'Poko" in options
    assert len(options) == 2


def test_filter_detail_rows_disambiguates_homonymous_communes() -> None:
    gdf = gpd.GeoDataFrame(
        {
            "admin3name": ["Boda", "Boda"],
            "Prefecture": ["Lobaye", "Ombella-M'Poko"],
            "Index_GDP": [10.0, 99.0],
            "geometry": [box(0, 0, 1, 1), box(1, 0, 2, 1)],
        },
        crs="EPSG:4326",
    )
    key = f"Boda{ZONE_KEY_SEP}Ombella-M'Poko"
    row = _filter_detail_rows(gdf, "Commune (Admin 3)", key).iloc[0]
    assert row["Index_GDP"] == pytest.approx(99.0)


def test_format_detail_zone_key_commune() -> None:
    row = pd.Series({"admin3name": "Boda", "Prefecture": "Lobaye"})
    assert _format_detail_zone_key(row, "Commune (Admin 3)") == f"Boda{ZONE_KEY_SEP}Lobaye"


def test_compute_kpi_gdp_cell_mean() -> None:
    gdf = gpd.GeoDataFrame(
        {
            "Prefecture": ["A", "A", "B"],
            "Index_GDP": [10.0, 20.0, 40.0],
            "Index_Infrastructure": [50.0, 60.0, 70.0],
            "Index_ExpoRisk": [30.0, 40.0, 50.0],
            "Index_health": [float("nan"), 80.0, 90.0],
            "geometry": [box(0, 0, 1, 1)] * 3,
        },
        crs="EPSG:4326",
    )
    kpi_rows = _compute_kpi_values(gdf, "Strategic (Donors/PTF)", pop_col=None)
    values = {label: val for label, val, _ in kpi_rows}
    assert values["Total Economic Activity Proxy"] == pytest.approx(70.0 / 3)


def test_kpi_source_uses_aggregated_gdf_at_admin_resolution() -> None:
    filtered = gpd.GeoDataFrame(
        {
            "Prefecture": ["A", "A"],
            "Index_GDP": [10.0, 30.0],
            "geometry": [box(0, 0, 1, 1)] * 2,
        },
        crs="EPSG:4326",
    )
    aggregated = gpd.GeoDataFrame(
        {
            "Prefecture": ["A"],
            "Index_GDP": [100.0],
            "geometry": [box(0, 0, 2, 2)],
        },
        crs="EPSG:4326",
    )
    assert _is_admin_resolution("Commune (Admin 3)")
    assert not _is_admin_resolution("Secteur (5×5 km)")
    assert _kpi_source_gdf(filtered, aggregated, "Commune (Admin 3)") is aggregated
    assert _kpi_source_gdf(filtered, aggregated, "Secteur (5×5 km)") is filtered
