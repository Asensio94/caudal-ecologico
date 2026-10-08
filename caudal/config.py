from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
REQUIREMENTS_DIR = DATA_DIR / "requirements"   # minimums parsed from the BOE, one CSV per basin
STATIONS_FILE = DATA_DIR / "stations.csv"      # control points and how to read each one
FLOWS_DIR = DATA_DIR / "flows"                 # daily means, one CSV per station
DOCS_DIR = ROOT / "docs"                       # the published page

for _d in (REQUIREMENTS_DIR, FLOWS_DIR, DOCS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# A day counts as below the minimum only when its mean is more than this fraction under
# it. Rating curves are least accurate at low flows; 5 % keeps measurement noise out.
TOLERANCE = 0.05

# Days fetched on each run. The SAIH data are provisional and get corrected for a while,
# so the last week is re-read every day and overwritten.
REFRESH_DAYS = 7
