"""Daily means on disk: one small CSV per station, easy to diff in git and to reuse."""
from __future__ import annotations

import csv
from datetime import date, datetime, timezone

from .compliance import Requirement
from .config import FLOWS_DIR, REQUIREMENTS_DIR, STATIONS_FILE
from .sources import DailyFlow

FLOW_FIELDS = ["date", "q_mean", "readings", "expected", "source", "fetched_at"]


def load_flows(station_id: str) -> dict[date, dict]:
    path = FLOWS_DIR / f"{station_id}.csv"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return {date.fromisoformat(r["date"]): r for r in csv.DictReader(f)}


def save_flows(station_id: str, new: list[DailyFlow]) -> None:
    """Merge `new` into the station file. Re-read days overwrite the stored ones."""
    rows = load_flows(station_id)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    for d in new:
        rows[d.day] = {"date": d.day.isoformat(), "q_mean": "" if d.mean is None else f"{d.mean:.4f}",
                       "readings": d.readings, "expected": d.expected, "source": d.source, "fetched_at": stamp}
    with (FLOWS_DIR / f"{station_id}.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FLOW_FIELDS)
        w.writeheader()
        w.writerows(rows[k] for k in sorted(rows))


def flow_series(station_id: str) -> dict[date, float | None]:
    return {d: (float(r["q_mean"]) if r["q_mean"] else None) for d, r in load_flows(station_id).items()}


def load_stations() -> list[dict]:
    if not STATIONS_FILE.exists():
        return []
    with STATIONS_FILE.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_requirements() -> dict[str, list[Requirement]]:
    """Requirements per station from every basin file, ordinary and drought rows merged."""
    by_key: dict[tuple, dict] = {}
    for path in sorted(REQUIREMENTS_DIR.glob("*.csv")):
        with path.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                months = tuple(float(r[f"m{m:02d}"]) if r[f"m{m:02d}"] != "" else None for m in range(1, 13))
                key = (r["station_id"], r["valid_from"], r["valid_to"])
                entry = by_key.setdefault(key, {"row": r})
                entry[r["regime"]] = months
    out: dict[str, list[Requirement]] = {}
    for (sid, vfrom, vto), e in by_key.items():
        r = e["row"]
        out.setdefault(sid, []).append(Requirement(
            sid, e["ordinary"], e.get("drought"), date.fromisoformat(vfrom),
            date.fromisoformat(vto) if vto else None, r["protected"] == "1", r["source_url"]))
    return out
