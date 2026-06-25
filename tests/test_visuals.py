"""Tests for map and radar rendering."""

from __future__ import annotations

import json
import re

import geopandas as gpd
import pandas as pd
import pytest
from plotly.graph_objs import Figure
from shapely.geometry import box

from dashboard_rca.config import CSV_PATH, SHP_PATH
from dashboard_rca.data import load_dashboard_data
from dashboard_rca.visuals import _hover_zone_column, build_map, build_radar_chart


@pytest.fixture(scope="module")
def dashboard_gdf() -> gpd.GeoDataFrame:
    if not CSV_PATH.exists() or not SHP_PATH.exists():
        pytest.skip("Dashboard data files not available")
    return load_dashboard_data(str(CSV_PATH), str(SHP_PATH), year=2021)


def test_hover_zone_column_secteur_uses_id() -> None:
    cols = {"id", "Prefecture", "Sous-prefecture", "admin3name"}
    assert _hover_zone_column("Secteur (5×5 km)", cols) == "id"


def test_hover_zone_column_commune_uses_admin3name() -> None:
    cols = {"id", "Prefecture", "admin3name"}
    assert _hover_zone_column("Commune (Admin 3)", cols) == "admin3name"


def test_build_map_returns_figure(dashboard_gdf: gpd.GeoDataFrame) -> None:
    sample = dashboard_gdf.head(200).copy()
    fig = build_map(sample, "Index_Vulnerab_Final", resolution="Secteur (5×5 km)", lang="FR")
    assert isinstance(fig, Figure)
    assert len(fig.data) > 0


def test_build_map_jenks_assigns_all_rows(dashboard_gdf: gpd.GeoDataFrame) -> None:
    sample = dashboard_gdf.head(500).copy()
    fig = build_map(sample, "Index_Vulnerab_Final", resolution="Secteur (5×5 km)", lang="EN")
    total_locations = sum(len(trace.locations) for trace in fig.data if trace.locations is not None)
    assert total_locations == len(sample)


def test_plotly_json_parseable_without_user_slashes(dashboard_gdf: gpd.GeoDataFrame) -> None:
    sample = dashboard_gdf.head(1000).copy()
    fig = build_map(sample, "Index_Vulnerab_Final", resolution="Secteur (5×5 km)", lang="FR")
    payload = fig.to_json()
    json.loads(payload)
    assert "N\\u002fA" not in payload
    assert "/ 100" not in payload

    obj = json.loads(payload)
    for trace in obj["data"]:
        for row in trace.get("customdata") or []:
            cells = row if isinstance(row, list) else [row]
            for cell in cells:
                if isinstance(cell, str):
                    assert "/" not in cell


def test_build_map_lang_affects_hover_suffix(dashboard_gdf: gpd.GeoDataFrame) -> None:
    sample = dashboard_gdf.dropna(subset=["Index_Vulnerab_Final"]).head(50).copy()
    fr_json = build_map(sample, "Index_Vulnerab_Final", resolution="Secteur (5×5 km)", lang="FR").to_json()
    en_json = build_map(sample, "Index_Vulnerab_Final", resolution="Secteur (5×5 km)", lang="EN").to_json()
    assert "sur 100" in fr_json
    assert "of 100" in en_json


def test_build_radar_chart_inverts_risk_metrics() -> None:
    row = pd.Series(
        {
            "Index_Vulnerab_Final": 80.0,
            "Index_Infrastructure": 50.0,
            "Index_ExpoRisk": 20.0,
            "Index_GDP_prim": 60.0,
            "Index_GDP_sec_ter": 40.0,
        }
    )
    fig = build_radar_chart(row, lang="EN")
    r_vals = fig.data[0].r
    hover = fig.data[0].hovertext
    assert r_vals[0] == pytest.approx(20.0)   # Index_Vulnerab_Final: 100 - 80
    assert r_vals[1] == pytest.approx(80.0)   # Index_ExpoRisk: 100 - 20
    assert r_vals[2] == pytest.approx(50.0)   # Index_Infrastructure: not inverted
    assert "20.0 of 100" in hover[1]
    assert "outward spoke" in hover[1]
    assert "80.0 of 100" in hover[0]
    assert "inward spoke" in hover[0]
