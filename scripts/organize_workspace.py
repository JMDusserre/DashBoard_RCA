"""Small helper to move raw inputs into the organized `data/` layout.

Run this from the repo root when you want to physically move files into the
new layout. It moves files and preserves directory structure for the
`RR_WLD_2025_520` package. It's conservative: it only moves if the source
exists and the target does not.
"""
from pathlib import Path
import shutil

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "RR_WLD_2025_520" / "Reproducibility-package" / "Inputs"
RAW_TARGET = REPO / "data" / "raw" / "RR_WLD_2025_520" / "Reproducibility-package" / "Inputs"
GIS_TARGET = REPO / "data" / "gis" / "RR_WLD_2025_520" / "Reproducibility-package" / "Inputs" / "GIS"

def ensure_parents(p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)


def move_if_present(src: Path, dst: Path):
    if not src.exists():
        print(f"source not found: {src}")
        return
    if dst.exists():
        print(f"target already exists, skipping: {dst}")
        return
    ensure_parents(dst)
    shutil.move(str(src), str(dst))
    print(f"moved {src} -> {dst}")


def main():
    # CSV
    csv_src = SRC / "Base_CAF_v1.csv"
    csv_dst = RAW_TARGET / "Base_CAF_v1.csv"
    move_if_present(csv_src, csv_dst)

    # GIS folder and common shapefile variants
    shapefile_names = [
        "Grid_5km_CFA_v4",
        "Grid_5km_CFA_v3",
        "BaseGrid_NewPrefs",
    ]
    for base in shapefile_names:
        for ext in [".shp", ".shx", ".dbf", ".prj", ".cpg", ".qmd"]:
            src = SRC / "GIS" / (base + ext)
            dst = GIS_TARGET / (base + ext)
            move_if_present(src, dst)

    print("Done. If files were large, check disk space and update gitignore as needed.")


if __name__ == "__main__":
    main()
