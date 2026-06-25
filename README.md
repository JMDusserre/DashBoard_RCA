# Central African Republic (CAR) Vulnerability Dashboard

An interactive geospatial decision-support tool designed to analyze risk exposure and access to basic services across the Central African Republic. Built for humanitarian and development partners, the dashboard combines satellite-derived proxies, administrative boundaries, and multidimensional vulnerability indices on a unified 0–100 scale—enabling strategic donors and field operators to compare territories, drill down to local grid cells, and overlay zone profiles side by side.

---

## Key Features

- **Interactive Geospatial Mapping** — Choropleth maps powered by GeoPandas and Jenks Natural Breaks classification, with semantic color palettes (risk, capacity, vulnerability) and context-aware basemaps.
- **Multidimensional Profiling** — Five-axis radar charts with optional spatial comparison: overlay two zones (communes, sub-prefectures, prefectures, or grid cells) on a single profile.
- **Dynamic Personas** — KPI cards and radar axes adapt to the selected user role: macro-economic indicators for the Strategic profile (donors / partners), and basic-services access for the Operational profile (NGOs / UN agencies).
- **Spatial Aggregation** — Navigate seamlessly from 5×5 km grid cells up through commune (Admin 3), sub-prefecture (Admin 2), and prefecture (Admin 1) administrative levels.
- **Native Bilingual Interface** — Full French / English UI with OCHA-aligned administrative labels and localized indicator names.
- **Built-in Feedback & Dynamic Changelog** — Sidebar expander reads `CHANGELOG.md` at runtime; one-click mailto feedback link for issue reporting and improvement suggestions.

---

## Architecture & Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3 |
| Frontend & Reactive UI | [Streamlit](https://streamlit.io/) |
| GIS & Spatial Joins | [GeoPandas](https://geopandas.org/) |
| Data Visualization | [Plotly](https://plotly.com/python/) (MapLibre choropleth + polar charts) |
| Classification | [mapclassify](https://pysal.org/mapclassify/) (Jenks Natural Breaks) |

---

## Project Structure

Separation of concerns across a single Python package:

```
DashBoard_RCA/
├── app.py                      # Streamlit entrypoint (recommended launch command)
├── CHANGELOG.md                # Release notes (displayed in the sidebar expander)
├── requirements.txt            # Pinned dependencies
├── data/                       # Local data directory (not versioned — see Setup)
│   ├── raw/                    # CSV panel tables
│   └── gis/                    # Shapefiles & geometries
└── dashboard_rca/
    ├── config.py               # Single source of truth: paths, UI texts (FR/EN), personas, hierarchies
    ├── data.py                 # ETL pipeline, spatial joins, aggregation, geometry handling
    ├── visuals.py              # Plotly rendering engine (choropleth map, radar chart)
    ├── ui.py                   # Streamlit frontend: sidebar, KPIs, detail panel, i18n
    ├── formatting.py           # Metric labels, NaN handling, display formatting
    └── style.py                # Custom CSS (responsive layout, sidebar)
```

| Module | Responsibility |
|---|---|
| `dashboard_rca/config.py` | Single source of truth — paths, UI texts, spatial resolutions, persona definitions, indicator hierarchy |
| `dashboard_rca/data.py` | ETL pipeline, spatial joins, administrative aggregation, geometry simplification |
| `dashboard_rca/visuals.py` | Plotly rendering engine — Jenks choropleth, dynamic basemap, radar comparison |
| `dashboard_rca/ui.py` | Streamlit frontend construction — filters, KPI cards, map, detail panel, changelog |

---

## Setup & Installation

### 1. Clone the repository

```bash
git clone https://github.com/JMDusserre/DashBoard_RCA.git
cd DashBoard_RCA
```

### 2. Create a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate        # macOS / Linux
# venv\Scripts\activate         # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Place the data files

Raw datasets (shapefiles and CSV) are **not versioned** in this repository due to file size and data-access constraints. Place them under the `data/` directory following the paths defined in `dashboard_rca/config.py`:

```
data/
├── raw/RR_WLD_2025_520/Reproducibility-package/Inputs/
│   └── Base_CAF_AllIndexes_ForPlatform.csv
└── gis/RR_WLD_2025_520/Reproducibility-package/Inputs/GIS/
    └── Grid_5km_CFA_v4.shp   (+ associated .shx, .dbf, .prj, .cpg files)
```

> **Note:** Without these files the application will raise a `FileNotFoundError` at startup. Contact the project maintainer for data access instructions.

### 5. Run the application

```bash
streamlit run app.py
```

Alternative entrypoint:

```bash
streamlit run dashboard_rca/ui.py
```

The dashboard opens at `http://localhost:8501` in your default browser.

---

## Data & Methodology

- **Spatial unit:** 5×5 km grid cells (~20,800 polygons) covering CAR (14.0°–28.5°E, 2.0°–11.5°N).
- **Panel year:** 2021 (fixed in the current production dataset).
- **Indices:** Pre-normalized proxy layers on a 0–100 scale (`Index_*` prefix).
- **Missing values:** Gray cells represent either uninhabited land (forests, savannas) or genuinely missing data for economic indicators—never fabricated.
- **Aggregation:** Administrative views use cell-mean aggregation; GDP columns are re-scaled to base 100 within the current view.

---

## Target Audience

| Profile | Use case |
|---|---|
| **Strategic (Donors / Partners)** | Macro-economic vulnerability, infrastructure scores, risk exposure at prefecture level |
| **Operational (NGOs / UN)** | Water, health, and education access proxies at commune or grid-cell level |

---

## Contributing

1. Follow the existing module boundaries (`config` → `data` → `visuals` → `ui`).
2. All new UI strings must be added to `UI_TEXTS` in `config.py` (FR + EN).
3. Document notable changes in `CHANGELOG.md` (English, [Keep a Changelog](https://keepachangelog.com/) format).
4. Report issues via the sidebar feedback link or open a GitHub issue.

---

## License & Attribution

Developed in the context of the World Bank vulnerability framing and the RR_WLD 2025-520 reproducibility package. Intended for demonstration and decision-support purposes with international partners (World Bank, UN agencies, ICASEES).
