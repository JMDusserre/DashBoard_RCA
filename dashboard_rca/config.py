"""Shared configuration and path constants for the dashboard."""

from __future__ import annotations
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent

ORGANIZED_DATA_ROOT = APP_ROOT / "data"
RAW_DATA_ROOT = ORGANIZED_DATA_ROOT / "raw"
GIS_DATA_ROOT = ORGANIZED_DATA_ROOT / "gis"

CSV_PATH_PREFERRED = RAW_DATA_ROOT / "RR_WLD_2025_520" / "Reproducibility-package" / "Inputs" / "Base_CAF_AllIndexes_ForPlatform.csv"
SHP_PATH_PREFERRED = GIS_DATA_ROOT / "RR_WLD_2025_520" / "Reproducibility-package" / "Inputs" / "GIS" / "Grid_5km_CFA_v4.shp"

CSV_PATH = CSV_PATH_PREFERRED
SHP_PATH = SHP_PATH_PREFERRED

INDEX_PREFIX = "Index_"
DEFAULT_MAP_COLUMN = "Index_Vulnerab_Final"
NO_DATA_COLOR = "#d3d3d3"

# Sole panel year bundled in the production dataset (no year selector in the UI).
DATA_YEAR = 2021

CAR_BOUNDS = {
    "west": 14.0,
    "east": 28.5,
    "south": 2.0,
    "north": 11.5,
}

# 5 dimensions shown in the radar chart (one per axis).
PERSONA_RADAR_COLUMNS: dict[str, list[str]] = {
    "Strategic (Donors/PTF)": [
        "Index_Vulnerab_Final",
        "Index_ExpoRisk",
        "Index_Infrastructure",
        "Index_GDP_prim",
        "Index_GDP_sec_ter",
    ],
    "Operational (NGOs/UN)": [
        "Index_water_access",
        "Index_health",
        "Index_educ_prim",
        "Index_conflicts",
        "Index_floods",
    ],
}

# Capacity/access metrics — mapped to the "Greens" palette in visuals.py.
CAPACITY_METRICS = [
    "Index_Infrastructure",
    "Index_water_access",
    "Index_health",
    "Index_educ_prim",
    "Index_GDP",
    "Index_GDP_prim",
    "Index_GDP_sec_ter",
]

# Risk/negative metrics — mapped to the "Reds" palette in visuals.py
# and inverted on the radar chart (1 - value = higher risk → lower on axis).
# As signaled by the data scientist: Idx_floods, Idx_conflicts, Idx_ExpoRisk,
# Idx_Vulnerab_Final are the "negative" variables requiring a reversed color convention.
RISK_METRICS = [
    "Index_floods",
    "Index_conflicts",
    "Index_ExpoRisk",
    "Index_Vulnerab_Final",
]

# Human-centric metrics use population masking during aggregation:
# only grid cells with population > 0 contribute to the mean.
HUMAN_CENTRIC_METRICS = [
    "Index_water_access",
    "Index_health",
    "Index_educ_prim",
    "Index_conflicts",
    "Index_Vulnerab_Final",
]

# Logical grouping for the UI indicator dropdown (parent → children).
# Parents with an empty list are standalone top-level indicators.
# Any index column absent from this dict is appended as an orphan at the bottom.
INDICATOR_HIERARCHY: dict[str, list[str]] = {
    "Index_Vulnerab_Final": [],
    "Index_ExpoRisk": [
        "Index_conflicts",
        "Index_floods",
    ],
    "Index_Infrastructure": [
        "Index_water_access",
        "Index_health",
        "Index_educ_prim",
    ],
    "Index_GDP": [
        "Index_GDP_prim",
        "Index_GDP_sec_ter",
    ],
}

PERSONA_OPTIONS = [
    "Strategic (Donors/PTF)",
    "Operational (NGOs/UN)",
]

SPATIAL_RESOLUTIONS = [
    "Secteur (5×5 km)",
    "Commune (Admin 3)",
    "Sous-prefecture (Admin 2)",
    "Prefecture (Admin 1)",
]

# Each persona gets exactly 3 KPI cards (ui.py uses st.columns(3) with strict=True).
# Strategic uses the pre-calculated composite indices (Index_Infrastructure, Index_ExpoRisk).
# Operational uses the individual access sub-indices for ground-level decision-making.
PERSONA_KPI_DEFINITIONS = {
    "Strategic (Donors/PTF)": [
        ("Total Economic Activity Proxy", ["Index_GDP"]),
        ("Aggregated Infrastructure Access Proxy", ["Index_Infrastructure"]),
        ("Aggregated Risk Exposure Proxy", ["Index_ExpoRisk"]),
    ],
    "Operational (NGOs/UN)": [
        ("Water Access Proxy", ["Index_water_access"]),
        ("Health Access Proxy", ["Index_health"]),
        ("Education Access Proxy", ["Index_educ_prim"]),
    ],
}

# --- End-user UI strings (FR default locale + EN). Do not use for code comments. ---
UI_TEXTS = {
    "FR": {
        "title": "🇨🇫 Tableau de bord de la vulnérabilité en RCA",
        "view": "🎯 Vue : *{}*",
        "user_profile": "👤 Profil Utilisateur",
        "spatial_filters": "🗺️ Filtres Spatiaux",
        "data_vis": "📊 Visualisation des Données",
        "select_territory": "Sélectionner un territoire (optionnel)",
        "all_territories": "Tous les territoires",
        "spatial_res": "Résolution spatiale",
        "highlight_index": "Quel indicateur mettre en valeur ?",
        "macro_indicators": "Macro-indicateurs pour : {}",
        "macro_caption": "Ces cartes de synthèse sont calculées à partir des couches de données actives de cet espace de travail. Tous les indicateurs sont sur une échelle 0–100.",
        "macro_caption_admin": "Moyennes par zone administrative (même logique que la carte). Le PIB est re-normalisé en base 100 dans la vue courante (100 = zone la plus forte).",
        "scale_suffix": "sur 100",
        "overall_vuln": "Score global de vulnérabilité",
        "overall_caption": "Indicateur composite combinant l'accès aux infrastructures et l'exposition aux risques (0 = Risque Faible, 100 = Risque Élevé).",
        "territory_vuln_caption": "Moyenne pondérée par cellule 5×5 km (stable quelle que soit la résolution de la carte).",
        "territory_score": "Vulnérabilité du territoire",
        "geospatial_map": "Carte géospatiale avancée",
        "map_caption_secteur": "Cellules de 5×5 km colorées selon l'indicateur choisi. Le gris clair indique une zone inhabitée (forêts, savanes) ou une donnée manquante pour les indicateurs économiques.",
        "map_caption_admin": "Zones administratives agrégées (moyenne des cellules). Le PIB est en base 100 relative à la vue (100 = maximum local).",
        "timeline": "Chronologie par année",
        "timeline_caption": "Sélectionnez l'année du panel de données.",
        "select_year": "Année",
        "profile_title": "Profil multidimensionnel",
        "profile_caption_secteur": "Inspectez une cellule de la grille pour voir son profil détaillé sur 5 dimensions.",
        "profile_caption_admin": "Sélectionnez une zone administrative pour voir son profil détaillé sur 5 dimensions.",
        "metric_fallback_info": "Indicateur « {original} » indisponible à cette résolution — affichage de « {fallback} ».",
        "profile_unavailable": "Profil indisponible pour : **{zone}**",
        "no_territory_data": "Aucune donnée trouvée pour le territoire : **{territory}**.",
        "load_error": "Erreur de chargement des données : {error}",
        "no_year_data": "Aucune année trouvée dans les données.",
        "unknown_location": "Inconnu",
        "select_cell": "Sélectionner l'ID d'une cellule à analyser (optionnel)",
        "select_zone": "Sélectionner une zone à analyser (optionnel)",
        "map_generating": "Génération de la carte…",
        "location_context": "Contexte & Localisation",
        "radar_title": "Graphique radar de vulnérabilité à 5 dimensions",
        "radar_caption": "Chaque dimension va de 0 (risque élevé) à 100 (sécurité élevée). Les données manquantes apparaissent en dessous de l'échelle.",
        "compare_zone": "Comparer avec (optionnel)",
        "zone_selected": "Zone sélectionnée",
        "zone_comparison": "Zone comparée",
        "updates_section": "📣 Mises à jour",
        "updates_expander": "Voir les nouveautés (v1.1)",

        # Menu options (FR display labels)
        "Strategic (Donors/PTF)": "Stratégique (Bailleurs / Partenaires)",
        "Operational (NGOs/UN)": "Opérationnel (ONG / Nations Unies)",
        "Secteur (5×5 km)": "Secteur (Grille 5×5 km)",
        "Commune (Admin 3)": "Commune (Admin 3)",
        "Sous-prefecture (Admin 2)": "Sous-préfecture (Admin 2)",
        "Prefecture (Admin 1)": "Préfecture (Admin 1)",

        # KPIs — Strategic persona (FR display labels)
        "Total Economic Activity Proxy": "Activité Économique Globale",
        "Aggregated Infrastructure Access Proxy": "Score d'Infrastructure",
        "Aggregated Risk Exposure Proxy": "Exposition aux Risques",
        # KPIs — Operational persona (FR display labels)
        "Water Access Proxy": "Accès à l'Eau",
        "Health Access Proxy": "Accès aux Services de Santé",
        "Education Access Proxy": "Accès à l'Éducation Primaire",

        # Column labels — pre-normalized index names (FR display labels)
        "Prefecture": "Préfecture",
        "Sous-prefecture": "Sous-préfecture",
        "admin3name": "Commune",
        "Year": "Année",
        "Index_GDP": "Activité économique (PIB)",
        "Index_GDP_prim": "PIB – Secteur primaire",
        "Index_GDP_sec_ter": "PIB – Secteurs secondaire & tertiaire",
        "Index_educ_prim": "Accès à l'éducation primaire",
        "Index_health": "Accès aux services de santé",
        "Index_water_access": "Accès à l'eau potable",
        "Index_Vulnerab_Final": "Score global de vulnérabilité",
        "Index_floods": "Risque d'inondations",
        "Index_conflicts": "Risque de conflits",
        "Index_Infrastructure": "Score d'infrastructure",
        "Index_ExpoRisk": "Exposition aux risques",
    },
    "EN": {
        "title": "🇨🇫 CAR Vulnerability Dashboard",
        "view": "🎯 View: *{}*",
        "user_profile": "👤 User Profile",
        "spatial_filters": "🗺️ Spatial Filters",
        "data_vis": "📊 Data Visualization",
        "select_territory": "Select territory (optional)",
        "all_territories": "All territories",
        "spatial_res": "Spatial Resolution",
        "highlight_index": "Which index to highlight?",
        "macro_indicators": "Proxy-Based Macro Indicators: {}",
        "macro_caption": "These summary cards are computed from the active proxy layers bundled in this workspace. All indicators use a 0–100 scale.",
        "macro_caption_admin": "Averages per administrative zone (same logic as the map). GDP is re-scaled to base 100 within the current view (100 = strongest zone).",
        "scale_suffix": "of 100",
        "overall_vuln": "Overall Vulnerability Score",
        "overall_caption": "Composite proxy index combining infrastructure access and risk exposure (0=Low Risk, 100=High Risk).",
        "territory_vuln_caption": "Mean across 5×5 km grid cells (stable regardless of map resolution).",
        "territory_score": "Territory Vulnerability",
        "geospatial_map": "Advanced Geospatial Map",
        "map_caption_secteur": "5×5 km grid cells colored by the selected proxy. Light gray indicates uninhabited land (forests, savannas) or missing data for economic indicators.",
        "map_caption_admin": "Aggregated administrative zones (cell mean). GDP uses a local base-100 scale (100 = view maximum).",
        "timeline": "Year timeline",
        "timeline_caption": "Select the panel year for all indicators and maps.",
        "select_year": "Year",
        "profile_title": "Multidimensional Profile",
        "profile_caption_secteur": "Inspect a grid cell to see its 5-dimensional proxy profile.",
        "profile_caption_admin": "Select an administrative zone to see its 5-dimensional proxy profile.",
        "metric_fallback_info": "Metric « {original} » unavailable at this resolution — showing « {fallback} ».",
        "profile_unavailable": "Profile unavailable for: **{zone}**",
        "no_territory_data": "No data found for territory: **{territory}**.",
        "load_error": "Data loading error: {error}",
        "no_year_data": "No year data found.",
        "unknown_location": "Unknown",
        "select_cell": "Select a grid cell ID to analyze (optional)",
        "select_zone": "Select a zone to analyze (optional)",
        "map_generating": "Generating map…",
        "location_context": "Location & Context",
        "radar_title": "5-Dimensional Proxy Radar Chart",
        "radar_caption": "Each dimension extends from 0 (high risk) to 100 (high safety). Missing data is shown below the scale.",
        "compare_zone": "Compare with (optional)",
        "zone_selected": "Selected zone",
        "zone_comparison": "Comparison zone",
        "updates_section": "📣 Updates",
        "updates_expander": "See what's new (v1.1)",

        # Menu options
        "Strategic (Donors/PTF)": "Strategic (Donors/PTF)",
        "Operational (NGOs/UN)": "Operational (NGOs/UN)",
        "Secteur (5×5 km)": "Grid cell (5×5 km)",
        "Commune (Admin 3)": "Commune (Admin 3)",
        "Sous-prefecture (Admin 2)": "Sub-prefecture (Admin 2)",
        "Prefecture (Admin 1)": "Prefecture (Admin 1)",

        # KPIs — Strategic persona
        "Total Economic Activity Proxy": "Total Economic Activity Proxy",
        "Aggregated Infrastructure Access Proxy": "Infrastructure Score",
        "Aggregated Risk Exposure Proxy": "Risk Exposure Proxy",
        # KPIs — Operational persona
        "Water Access Proxy": "Water Access Proxy",
        "Health Access Proxy": "Health Access Proxy",
        "Education Access Proxy": "Education Access Proxy",

        # Column labels — pre-normalized indices from the data scientist
        "Prefecture": "Prefecture",
        "Sous-prefecture": "Sub-prefecture",
        "admin3name": "Commune",
        "Year": "Year",
        "Index_GDP": "Economic Activity (GDP)",
        "Index_GDP_prim": "Primary Sector GDP",
        "Index_GDP_sec_ter": "Secondary & Tertiary GDP",
        "Index_educ_prim": "Primary Education Access",
        "Index_health": "Healthcare Access",
        "Index_water_access": "Water Access",
        "Index_Vulnerab_Final": "Overall Vulnerability Score",
        "Index_floods": "Flood Risk",
        "Index_conflicts": "Conflict Risk",
        "Index_Infrastructure": "Infrastructure Score",
        "Index_ExpoRisk": "Risk Exposure",
    },
}
