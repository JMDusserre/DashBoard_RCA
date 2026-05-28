"""Shared configuration and path constants for the dashboard.

This module centralizes all configuration to ensure consistency across the
application and to make it easy to adjust settings (bounds, color scales,
friendly labels) without touching core logic. All paths are resolved relative
to the application root for portability.

World Bank PRWP 11309 Alignment:
    - The dashboard keeps the same decision-support framing, but the active data
        package in this workspace contains raw socioeconomic proxies rather than the
        earlier derived access/conflict layers.
    - Dashboard columns are normalized to [0, 1] so the same map and radar patterns
        remain readable across territories and years.
    - NaN handling still reflects field insecurity when cells have no usable source
        value in the package.
"""

from __future__ import annotations

from pathlib import Path


APP_ROOT = Path(__file__).resolve().parent.parent

# Preferred organized data layout. The app reads from `data/` only so the
# workspace has a single source of truth.
ORGANIZED_DATA_ROOT = APP_ROOT / "data"
RAW_DATA_ROOT = ORGANIZED_DATA_ROOT / "raw"
GIS_DATA_ROOT = ORGANIZED_DATA_ROOT / "gis"

# Preferred (organized) package locations
CSV_PATH_PREFERRED = (
    RAW_DATA_ROOT
    / "RR_WLD_2025_520"
    / "Reproducibility-package"
    / "Inputs"
    / "Base_CAF_v1.csv"
)
SHP_PATH_PREFERRED = (
    GIS_DATA_ROOT
    / "RR_WLD_2025_520"
    / "Reproducibility-package"
    / "Inputs"
    / "GIS"
    / "Grid_5km_CFA_v4.shp"
)

# Resolve final paths at import time.
CSV_PATH = CSV_PATH_PREFERRED
SHP_PATH = SHP_PATH_PREFERRED

# Color palette options for user selection in sidebar
DEFAULT_MAP_SCALE = "RdYlGn"
AVAILABLE_COLOR_SCALES = [
    "RdYlGn",
    "Viridis",
    "Cividis",
    "Plasma",
    "Turbo",
    "Blues",
    "Greens",
    "Reds",
]

# All normalized index columns follow this prefix pattern, enabling dynamic discovery
# at runtime. This design allows new indices to be added without code changes.
INDEX_PREFIX = "Index_"

# Default map color shows normalized nighttime lights, the closest available proxy
# for economic intensity in the current package.
DEFAULT_MAP_COLUMN = "Index_NTLsum"

# Overall vulnerability is the only explicitly composite risk measure in the
# active workspace snapshot.
OVERALL_VULNERABILITY_INDEX = "Index_Vulnerab_Final"

# Neutral gray used for missing data, uninhabited cells, or no-data areas.
NO_DATA_COLOR = "#d3d3d3"

# CAR_BOUNDS lock the map viewport to Central African Republic coordinates.
# This prevents zoom-out distraction and ensures decision-makers stay focused on the territory.
# Hardcoding avoids dynamic computation, CRS projection warnings, and user confusion.
CAR_BOUNDS = {
    "west": 14.0,
    "east": 28.5,
    "south": 2.0,
    "north": 11.5,
}

# FRIENDLY_LABELS map technical column names to non-technical proxy language for decision-makers.
# This ensures NGO staff, government leaders, and donors understand indicators
# without needing data science expertise.
# The active workspace uses proxy layers only; labels should not imply archived
# official vulnerability components are available here.
FRIENDLY_LABELS = {
    "Prefecture": "Prefecture",
    "Sous-prefecture": "Sub-prefecture",
    "Index_NTLsum": "Nighttime lights proxy",
    "Index_NTLmean": "Average nighttime lights proxy",
    "Index_population": "Population pressure proxy",
    "Index_BuiltUp": "Built-up proxy",
    "Index_Water": "Water access proxy",
    "Index_Grasslands": "Grassland coverage proxy",
    "Index_Deforest": "Deforestation pressure proxy",
    "Index_share_forest": "Forest share",
    "Index_share_cropland": "Cropland share",
    "Index_share_builtup": "Built-up share",
    "Index_share_deforest": "Deforestation share",
    "Index_share_NDVI": "Vegetation share",
    "Index_Main_Mines": "Main mines proxy",
    "Index_Diamond_ArtisanalMines": "Artisanal diamond mines proxy",
    "Index_Boutiques": "Market and retail density proxy",
    "Index_Vulnerab_Final": "Overall vulnerability proxy",
}

# Detail panel uses the five most interpretable normalized proxies available in
# the active RR_WLD package snapshot, plus the overall vulnerability composite.
DETAIL_COLUMNS = [
    "Index_Vulnerab_Final",
    "Index_NTLsum",
    "Index_NTLmean",
    "Index_population",
    "Index_share_builtup",
]

# DESIGN NOTE - DETAIL_COLUMNS & Radar Polarity:
# DETAIL_COLUMNS should ONLY include non-risk metrics (descriptive or capacity).
# If RISK_METRICS are added to DETAIL_COLUMNS, build_radar_chart() will automatically
# invert them (1.0 - value) to maintain the radar polarity: 0=high risk, 1=high safety.
# Do not add RISK_METRICS to DETAIL_COLUMNS without understanding this rule.

# Metric categorization for neutral UX treatment.
# Descriptive metrics are purely informational (no ranking, no progress bars).
# Capacity metrics show access/availability (can have progress bars).
# Risk metrics show vulnerability/pressure (can be ranked and have progress bars).
CAPACITY_METRICS = [
    "Index_Water",
    "Index_share_builtup",
    "Index_share_cropland",
    "Index_GDP",
    "Index_Access_to_healthcenter",
    "Index_Access_to_primary_education",
]

RISK_METRICS = [
    "Index_Deforest",
    "Index_share_deforest",
    "Index_Main_Mines",
    "Index_Diamond_ArtisanalMines",
    "Index_Conflicts",
    "Index_Absence_of_floods",
]

DESCRIPTIVE_METRICS = [
    "Index_NTLsum",
    "Index_NTLmean",
    "Index_population",
    "Index_BuiltUp",
    "Index_share_NDVI",
    "Index_Grasslands",
    "Index_Boutiques",
]

# Human-centric metrics: these are only meaningful where people live.
# When aggregating or averaging, ignore cells with population == 0 or NaN
# for these metrics. Geographic/economic metrics (NTL, GDP, forests, mines)
# should be averaged across the full geography.
HUMAN_CENTRIC_METRICS = [
    "Index_Water",
    "Index_Access_to_healthcenter",
    "Index_Access_to_primary_education",
    "Index_Conflicts",
    "Index_Vulnerab_Final",
    "Index_population",
]

# Persona options for role-based UI
PERSONA_OPTIONS = [
    "Strategic (Donors/PTF)",
    "Operational (NGOs/UN)",
]

# Spatial resolution options for dynamic aggregation
SPATIAL_RESOLUTIONS = [
    "Grid cell (5×5 km)",
    "City (Admin 3)",
    "Sous-prefecture (Admin 2)",
    "Prefecture (Admin 1)",
]

# Persona KPI definitions use only the active proxy bundle.
# Each entry is (display label, list of candidate columns to average).
PERSONA_KPI_DEFINITIONS = {
    "Strategic (Donors/PTF)": [
        ("Total Economic Activity Proxy", ["Index_NTLsum"]),
        (
            "Aggregated Infrastructure Access Proxy",
            ["Index_Water", "Index_share_builtup", "Index_share_cropland"],
        ),
        (
            "Aggregated Risk Exposure Proxy",
            ["Index_population", "Index_Deforest", "Index_Main_Mines"],
        ),
    ],
    "Operational (NGOs/UN)": [
        ("Water Access Proxy", ["Index_Water"]),
        ("Settlement Access Proxy", ["Index_share_builtup"]),
        ("Agricultural Access Proxy", ["Index_share_cropland"]),
    ],
}
