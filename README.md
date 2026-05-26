# DashBoard_RCA

Streamlit dashboard for territorial vulnerability analysis in the Central African Republic.

## Workspace Layout

- `app.py` - small Streamlit launcher
- `dashboard_rca/` - dashboard implementation split into focused modules
- `Sample_RCA.csv` - tabular source data
- `Grid_5km_CFA_v3/` - spatial source data
- `requirements.txt` - pinned Python dependencies

## Prerequisites

- Python 3.11 or newer
- `pip`

## Setup

After cloning the repository on a new computer:

```bash
git clone <your-repo-url>
cd DashBoard_RCA
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Run the app

```bash
streamlit run app.py
```

## Notes

- The app reads `Sample_RCA.csv` and the `Grid_5km_CFA_v3` shapefile from the repository root.
- The main code now lives in `dashboard_rca/` for easier navigation and maintenance.
- If you update dependencies, regenerate `requirements.txt` so the setup stays reproducible.