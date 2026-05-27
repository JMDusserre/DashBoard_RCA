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

# All normalized index columns follow this prefix pattern, enabling dynamic discovery
# at runtime. This design allows new indices to be added without code changes.
INDEX_PREFIX = "Index_"

# Default KPI cards now summarize the raw RR_WLD proxy layers that are available
# in this workspace snapshot.
DEFAULT_KPI_COLUMNS = [
    "Index_NTLsum",
    "Index_NTLmean",
    "Index_population",
]

# Default map color shows normalized nighttime lights, the closest available proxy
# for economic intensity in the current package.
DEFAULT_MAP_COLUMN = "Index_NTLsum"

# RdYlGn (Red-Yellow-Green) is intuitive: red=danger, green=safety, yellow=transition.
# This semantic mapping improves rapid decision-making by non-technical audiences.
DEFAULT_MAP_SCALE = "RdYlGn"

# Color scales support diverse visual preferences and accessibility (e.g., Cividis for colorblind).
# RdYlGn is semantic (red=risk), while perceptually uniform scales (Viridis, Cividis)
# improve readability across different devices and print media.
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

# CAR_BOUNDS lock the map viewport to Central African Republic coordinates.
# This prevents zoom-out distraction and ensures decision-makers stay focused on the territory.
# Hardcoding avoids dynamic computation, CRS projection warnings, and user confusion.
CAR_BOUNDS = {
    "west": 14.0,
    "east": 28.5,
    "south": 2.0,
    "north": 11.5,
}

# FRIENDLY_LABELS map technical column names to non-technical language for decision-makers.
# This ensures NGO staff, government leaders, and donors understand indicators
# without needing data science expertise.
# World Bank PRWP 11309 multidimensional framework:
#   - 3 macro-indicators: Conflicts, Water, Economic activity (top cards)
#   - 5 dimensions in detail panel: Primary GDP, Overall GDP, Health, Water, Education
FRIENDLY_LABELS = {
    "Prefecture": "Prefecture",
    "Sous-prefecture": "Sub-prefecture",
    "Index_NTLsum": "Nighttime lights intensity",
    "Index_NTLmean": "Average nighttime lights",
    "Index_population": "Population pressure",
    "Index_BuiltUp": "Built-up intensity",
    "Index_Water": "Water coverage",
    "Index_Grasslands": "Grassland coverage",
    "Index_Deforest": "Deforestation pressure",
    "Index_share_forest": "Forest share",
    "Index_share_cropland": "Cropland share",
    "Index_share_builtup": "Built-up share",
    "Index_share_deforest": "Deforestation share",
    "Index_share_NDVI": "Vegetation share",
    "Index_Main_Mines": "Main mines intensity",
    "Index_Diamond_ArtisanalMines": "Artisanal diamond mines",
    "Index_Boutiques": "Market and retail density",
}

# Detail panel uses the five most interpretable normalized proxies available in
# the RR_WLD package snapshot.
DETAIL_COLUMNS = [
    "Index_NTLsum",
    "Index_NTLmean",
    "Index_population",
    "Index_share_builtup",
    "Index_share_cropland",
]
