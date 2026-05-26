"""Shared configuration and path constants for the dashboard."""

from __future__ import annotations

from pathlib import Path


APP_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = APP_ROOT / "Sample_RCA.csv"
SHP_PATH = APP_ROOT / "Grid_5km_CFA_v3" / "Grid_5km_CFA_v3.shp"

INDEX_PREFIX = "Index_"
DEFAULT_KPI_COLUMNS = [
    "Index_Absence_of_conflicts",
    "Index_Access_to_water",
    "Index_GDP",
]
DEFAULT_MAP_COLUMN = "Index_Absence_of_conflicts"
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
CAR_BOUNDS = {
    "west": 14.0,
    "east": 28.5,
    "south": 2.0,
    "north": 11.5,
}
FRIENDLY_LABELS = {
    "Index_GDP_primary": "Agriculture and primary economy",
    "Index_GDP_secondary&tertiary": "Services and secondary economy",
    "Index_GDP": "Overall economic activity",
    "Index_Access_to_healthcenter": "Access to health centers",
    "Index_Access_to_water": "Access to water",
    "Index_Access_to_primary_education": "Access to primary education",
    "Index_Absence_of_floods": "Flood safety",
    "Index_Absence_of_conflicts": "Security and stability",
}
