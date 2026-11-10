# Central African Republic Vulnerability Dashboard

**An interactive geospatial dashboard designed to make complex vulnerability data more accessible to decision-makers.**

[**Live Demo**](https://rca-vulnerability-viewer.streamlit.app/)

## Why this project?

The project started from discussions with economists and data scientists working with vulnerability data in the Central African Republic.

The challenge was not simply to display indicators on a map, but to make complex datasets understandable and useful to people who are not data specialists, including humanitarian organizations, institutional stakeholders and operational decision-makers.

The resulting prototype allows users to explore geographic disparities, compare territories and examine vulnerability indicators at different administrative levels.

## My contribution

I worked with economists and data scientists to translate their analytical requirements into an interactive application.

My contribution focused on:

- Understanding and reformulating user needs.
- Selecting relevant data representations and defining dashboard functionality.
- Designing the application's overall structure with maintainability and future development in mind.
- Prototyping and implementing the solution with substantial AI assistance.

The project gave me the opportunity to connect my previous experience in understanding business needs with the technical skills developed during my transition into software development.

**Tech stack:** Python, Streamlit, GeoPandas, Plotly, Pandas.

## Application preview

*Screenshot of the interactive dashboard.*

<img width="2560" height="4556" alt="screencapture-rca-vulnerability-viewer-streamlit-app-2026-11-10-14_32_43" src="https://github.com/user-attachments/assets/04795e50-ea8c-4aa9-89bb-53347c2e6d83" />


---

## Key Features

- **Interactive Geospatial Mapping** — Choropleth maps powered by GeoPandas and Jenks Natural Breaks classification, with semantic color palettes (risk, capacity, vulnerability) and context-aware basemaps.
- **Multidimensional Profiling** — Five-axis radar charts with optional spatial comparison: overlay two zones (communes, sub-prefectures, prefectures, or grid cells) on a single profile.
- **Dynamic Personas** — KPI cards and radar axes adapt to the selected user role: macro-economic indicators for the Strategic profile (donors / partners), and basic-services access for the Operational profile (NGOs / UN agencies).
- **Spatial Aggregation** — Navigate from 5 × 5 km grid cells up through commune (Admin 3), sub-prefecture (Admin 2), and prefecture (Admin 1) administrative levels.
- **Bilingual Interface** — French / English UI with localized indicator names and administrative labels.
- **Feedback & Changelog** — A sidebar section reads `CHANGELOG.md` at runtime, alongside a feedback link for suggestions and issue reporting.

---

## Architecture & Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3 |
| Frontend & Reactive UI | Streamlit |
| Data Processing | Pandas and NumPy |
| GIS & Spatial Joins | GeoPandas |
| Data Visualization | Plotly (choropleth maps and radar charts) |
| Classification | mapclassify (Jenks Natural Breaks) |

### Project Structure

The application is organized into separate modules for configuration, data processing, visualization, and UI:

```text
DashBoard_RCA/
├── app.py
├── CHANGELOG.md
├── requirements.txt
├── dashboard_rca/
│   ├── config.py
│   ├── data.py
│   ├── visuals.py
│   ├── ui.py
│   ├── formatting.py
│   └── style.py
├── data/
│   ├── raw/
│   └── gis/
├── tests/
├── docs/
└── scripts/
```

| Module | Responsibility |
|---|---|
| `dashboard_rca/config.py` | Data paths, labels, spatial resolutions, user profiles and indicator hierarchy |
| `dashboard_rca/data.py` | Loading and joining source data, administrative aggregation, geometry handling |
| `dashboard_rca/visuals.py` | Interactive map generation and radar comparisons |
| `dashboard_rca/ui.py` | Filters, KPI cards, maps, detail panels and language selection |
| `dashboard_rca/formatting.py` | Indicator labels and missing-value formatting |
| `dashboard_rca/style.py` | Interface styling |

---

## Setup & Installation

### 1. Clone the repository

Some data files are tracked with **Git LFS (Large File Storage)**. Install Git LFS before cloning, then run:

```bash
git lfs install
git clone https://github.com/JMDusserre/DashBoard_RCA.git
cd DashBoard_RCA
git lfs pull
```

### 2. Create a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Check the data files

The application expects a CSV dataset and a shapefile at paths defined in `dashboard_rca/config.py`:

```text
data/
├── raw/RR_WLD_2025_520/Reproducibility-package/Inputs/
│   └── Base_CAF_AllIndexes_ForPlatform.csv
└── gis/RR_WLD_2025_520/Reproducibility-package/Inputs/GIS/
    ├── Grid_5km_CFA_v4.shp
    ├── Grid_5km_CFA_v4.shx
    ├── Grid_5km_CFA_v4.dbf
    ├── Grid_5km_CFA_v4.prj
    └── Grid_5km_CFA_v4.cpg
```

The repository contains Git LFS pointers for several CSV and geographic files. A normal clone with Git LFS configured should retrieve the corresponding file contents, provided the LFS objects are accessible.

Without the required data files, the dashboard cannot load successfully.

### 5. Run the application

```bash
streamlit run app.py
```

The application should open at `http://localhost:8501`.

### 6. Run the tests

```bash
pytest -q
```

Tests cover data handling, formatting, visualizations, and UI helper functions. Some data-dependent tests may be skipped if the required source files are unavailable.

---

## Data & Methodology

- **Spatial unit:** 5 × 5 km grid cells (approximately 20,800 polygons) covering the Central African Republic.
- **Data year:** 2021 in the current production configuration.
- **Indicators:** Pre-normalized proxy indices on a 0–100 scale, generally identified by the `Index_*` prefix.
- **Missing values:** Missing data are preserved rather than replaced with fabricated scores; map cells without usable values may appear gray.
- **Aggregation:** Administrative-level views aggregate cell-level data; GDP-related indices are re-scaled to base 100 within the displayed view.
- **Interpretation:** The meaning and direction of each indicator matter. Higher scores do not necessarily have the same interpretation across risk and capacity measures.

This application is a prototype for exploration and visualization; users should consult the underlying data documentation and methodology before drawing operational conclusions.

---

## Target Audience

| Profile | Typical use case |
|---|---|
| **Strategic (Donors / Partners)** | Explore macroeconomic vulnerability, infrastructure indicators and risk exposure across territories |
| **Operational (NGOs / UN agencies)** | Explore access-to-services indicators, including water, health and education, at finer spatial levels |

---

## Contributing

Contributions and feedback are welcome.

1. Follow the existing module boundaries (`config` → `data` → `visuals` → `ui`).
2. Add new interface strings in both French and English via `UI_TEXTS` in `dashboard_rca/config.py`.
3. Document meaningful changes in `CHANGELOG.md`.
4. Run the relevant tests and report issues through GitHub or the application's feedback link.

---

## Data Sources & Attribution

The prototype draws on the vulnerability analysis context and the **RR_WLD 2025-520 reproducibility package**, including tabular indicators and geographic data used for exploration and visualization.

The dashboard is presented as a demonstration and decision-support prototype. Mention of institutions or potential users does not imply official endorsement of this repository or its interpretations.

No software license is declared in this repository at present. Reuse rights for third-party datasets and supporting materials should be checked separately.
