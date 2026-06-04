"""Shared configuration and path constants for the dashboard."""

from __future__ import annotations
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent

ORGANIZED_DATA_ROOT = APP_ROOT / "data"
RAW_DATA_ROOT = ORGANIZED_DATA_ROOT / "raw"
GIS_DATA_ROOT = ORGANIZED_DATA_ROOT / "gis"

CSV_PATH_PREFERRED = RAW_DATA_ROOT / "RR_WLD_2025_520" / "Reproducibility-package" / "Inputs" / "Base_CAF_v1.csv"
SHP_PATH_PREFERRED = GIS_DATA_ROOT / "RR_WLD_2025_520" / "Reproducibility-package" / "Inputs" / "GIS" / "Grid_5km_CFA_v4.shp"

CSV_PATH = CSV_PATH_PREFERRED
SHP_PATH = SHP_PATH_PREFERRED

DEFAULT_MAP_SCALE = "RdYlGn"
AVAILABLE_COLOR_SCALES = ["RdYlGn", "Viridis", "Cividis", "Plasma", "Turbo", "Blues", "Greens", "Reds"]

INDEX_PREFIX = "Index_"
DEFAULT_MAP_COLUMN = "Index_NTLsum"
NO_DATA_COLOR = "#d3d3d3"

CAR_BOUNDS = {
    "west": 14.0,
    "east": 28.5,
    "south": 2.0,
    "north": 11.5,
}

DETAIL_COLUMNS = [
    "Index_Vulnerab_Final",
    "Index_NTLsum",
    "Index_NTLmean",
    "Index_population",
    "Index_share_builtup",
]

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

HUMAN_CENTRIC_METRICS = [
    "Index_Water",
    "Index_Access_to_healthcenter",
    "Index_Access_to_primary_education",
    "Index_Conflicts",
    "Index_Vulnerab_Final",
    "Index_population",
]

PERSONA_OPTIONS = [
    "Strategic (Donors/PTF)",
    "Operational (NGOs/UN)",
]

# Modifié : on garde les clés de base
SPATIAL_RESOLUTIONS = [
    "Secteur (5×5 km)",
    "Sous-prefecture (Admin 2)",
    "Prefecture (Admin 1)",
]

PERSONA_KPI_DEFINITIONS = {
    "Strategic (Donors/PTF)": [
        ("Total Economic Activity Proxy", ["Index_NTLsum"]),
        ("Aggregated Infrastructure Access Proxy", ["Index_Water", "Index_share_builtup", "Index_share_cropland"]),
        ("Aggregated Risk Exposure Proxy", ["Index_population", "Index_Deforest", "Index_Main_Mines"]),
    ],
    "Operational (NGOs/UN)": [
        ("Water Access Proxy", ["Index_Water"]),
        ("Settlement Access Proxy", ["Index_share_builtup"]),
        ("Agricultural Access Proxy", ["Index_share_cropland"]),
    ],
}

# --- TRADUCTION DE L'INTERFACE (UI) ET DES DONNÉES ---
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
        "palette": "Palette de couleurs",
        "macro_indicators": "Macro-indicateurs pour : {}",
        "macro_caption": "Ces cartes de synthèse sont calculées à partir des couches de données actives de cet espace de travail.",
        "overall_vuln": "Score global de vulnérabilité",
        "overall_caption": "Indicateur composite combinant l'accès, l'activité et l'exposition (0 = Risque Faible, 1 = Risque Élevé).",
        "territory_score": "Vulnérabilité du territoire",
        "geospatial_map": "Carte géospatiale avancée",
        "map_caption": "Cellules de 5×5 km colorées selon l'indicateur normalisé choisi. Le gris clair indique une absence de données.",
        "timeline": "Chronologie par année",
        "timeline_caption": "Curseur temporel pour observer l'évolution de la situation sur le terrain.",
        "profile_title": "Profil multidimensionnel",
        "profile_caption": "Inspectez une cellule de la grille pour voir son profil détaillé sur 5 dimensions.",
        "select_cell": "Sélectionner l'ID d'une cellule à analyser (optionnel)",
        "location_context": "Contexte & Localisation",
        "radar_title": "Graphique radar de vulnérabilité à 5 dimensions",
        "radar_caption": "Chaque dimension va de 0 (risque élevé) à 1 (sécurité élevée). Les données manquantes apparaissent à -0,1.",
        
        # Options des menus (Clés anglaises -> Affichage français sans jargon)
        "Strategic (Donors/PTF)": "Stratégique (Bailleurs / Partenaires)",
        "Operational (NGOs/UN)": "Opérationnel (ONG / Nations Unies)",
        "Secteur (5×5 km)": "Secteur ultra-local (Grille 5x5 km)",
        "Sous-prefecture (Admin 2)": "Sous-préfecture (Zone locale)",
        "Prefecture (Admin 1)": "Préfecture (Région)",
        
        # KPIs
        "Total Economic Activity Proxy": "Activité Économique Globale",
        "Aggregated Infrastructure Access Proxy": "Accès aux Infrastructures",
        "Aggregated Risk Exposure Proxy": "Exposition aux Risques",
        "Water Access Proxy": "Accès à l'Eau",
        "Settlement Access Proxy": "Accès aux Zones Habitées",
        "Agricultural Access Proxy": "Accès aux Zones Agricoles",
        
        # Labels de colonnes
        "Prefecture": "Préfecture",
        "Sous-prefecture": "Sous-préfecture",
        "Year": "Année",
        "Index_NTLsum": "Accès à l'électricité (Lumières nocturnes)",
        "Index_NTLmean": "Accès moyen à l'électricité",
        "Index_population": "Densité de population",
        "Index_BuiltUp": "Densité des infrastructures",
        "Index_Water": "Accès à l'eau",
        "Index_Grasslands": "Couverture herbacée",
        "Index_Deforest": "Risque de déforestation",
        "Index_share_forest": "Proportion de forêt",
        "Index_share_cropland": "Activité agricole",
        "Index_share_builtup": "Proportion de zones habitées",
        "Index_share_deforest": "Proportion déforestée",
        "Index_share_NDVI": "Proportion de végétation",
        "Index_Main_Mines": "Proximité des mines principales",
        "Index_Diamond_ArtisanalMines": "Proximité des mines artisanales",
        "Index_Boutiques": "Présence de marchés et commerces",
        "Index_Vulnerab_Final": "Score global de vulnérabilité",
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
        "palette": "Color palette",
        "macro_indicators": "Proxy-Based Macro Indicators: {}",
        "macro_caption": "These summary cards are computed from the active proxy layers bundled in this workspace.",
        "overall_vuln": "Overall Vulnerability Score",
        "overall_caption": "Composite proxy index combining access, activity, and exposure layers (0=Low Risk, 1=High Risk).",
        "territory_score": "Territory Vulnerability",
        "geospatial_map": "Advanced Geospatial Map",
        "map_caption": "5×5 km grid cells colored by the selected normalized proxy. Light gray indicates missing data.",
        "timeline": "Year timeline",
        "timeline_caption": "Use the horizontal timeline to move through the panel years and watch the map update.",
        "profile_title": "Multidimensional Profile",
        "profile_caption": "Inspect a grid cell to see its 5-dimensional proxy profile.",
        "select_cell": "Select a grid cell ID to analyze (optional)",
        "location_context": "Location & Context",
        "radar_title": "5-Dimensional Proxy Radar Chart",
        "radar_caption": "Each dimension extends from 0 (high risk) to 1 (high safety). Missing data shown as -0.1.",
        
        "Strategic (Donors/PTF)": "Strategic (Donors/PTF)",
        "Operational (NGOs/UN)": "Operational (NGOs/UN)",
        "Secteur (5×5 km)": "Grid cell (5×5 km)",
        "Sous-prefecture (Admin 2)": "Sub-prefecture (Admin 2)",
        "Prefecture (Admin 1)": "Prefecture (Admin 1)",
        
        # KPIs
        "Total Economic Activity Proxy": "Total Economic Activity Proxy",
        "Aggregated Infrastructure Access Proxy": "Aggregated Infrastructure Access Proxy",
        "Aggregated Risk Exposure Proxy": "Aggregated Risk Exposure Proxy",
        "Water Access Proxy": "Water Access Proxy",
        "Settlement Access Proxy": "Settlement Access Proxy",
        "Agricultural Access Proxy": "Agricultural Access Proxy",

        # Labels de colonnes
        "Prefecture": "Prefecture",
        "Sous-prefecture": "Sub-prefecture",
        "Year": "Year",
        "Index_NTLsum": "Electricity access (Night lights)",
        "Index_NTLmean": "Average electricity access",
        "Index_population": "Population density",
        "Index_BuiltUp": "Infrastructure density",
        "Index_Water": "Water access",
        "Index_Grasslands": "Grassland coverage",
        "Index_Deforest": "Deforestation risk",
        "Index_share_forest": "Forest share",
        "Index_share_cropland": "Agricultural activity",
        "Index_share_builtup": "Settlement share",
        "Index_share_deforest": "Deforested share",
        "Index_share_NDVI": "Vegetation share",
        "Index_Main_Mines": "Main mines proximity",
        "Index_Diamond_ArtisanalMines": "Artisanal mines proximity",
        "Index_Boutiques": "Market & retail presence",
        "Index_Vulnerab_Final": "Overall vulnerability score",
    }
}