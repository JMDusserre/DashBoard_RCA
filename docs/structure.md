Workspace layout
=================

This repository now uses a small, opinionated layout to keep raw data and
derived code separate. The changes are intentionally non-breaking: the
application will prefer files under `data/` when present and otherwise fall
back to the original locations.

New folders
-----------
- `data/raw/` — raw CSVs and original data packages (e.g. RR_WLD_2025_520)
- `data/gis/` — GIS files and shapefiles
- `scripts/` — small utilities (e.g. `organize_workspace.py`) to rearrange files
- `docs/` — workspace-level documentation

How to adopt the new layout
---------------------------
1. Inspect `scripts/organize_workspace.py`.
2. From the repository root run:

```bash
python scripts/organize_workspace.py
```

This script will move CSVs and shapefile components into `data/` when
possible. If you prefer to move files manually, create the `data/raw/...`
and `data/gis/...` directories and put the package contents there.

Notes
-----
- The application uses `dashboard_rca/config.py` which prefers `data/` but
  falls back to the legacy `RR_WLD_2025_520` bundle for backwards
  compatibility.
- Add any large proprietary data to `data/raw/` and mark it in gitignore.
