"""Why a river may run short: what the plans report around each control point.

One row per station and groundwater body under it (a station with none gets one row with
the aquifer fields empty). The river fields repeat on every row of a station.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass

from . import store
from .config import CONTEXT_FILE
from .sources import chj_piezometry, session, wise

FIELDS = ["station_id", "river_body_code", "flow_pressures", "aquifer_code", "aquifer_name", "aquifer_status",
          "aquifer_at_risk", "level_trend_m_year", "trend_piezometers", "trend_falling", "trend_years"]
CHJ_PREFIX = "ES080MSBT"   # EU code of a Júcar groundwater body = this + the CHJ code


@dataclass(frozen=True)
class Context:
    river_body_code: str
    flow_pressures: tuple[str, ...]
    aquifers: tuple[dict, ...]


def build(log=print, country: str | None = None) -> int:
    """With a country, only its stations are looked up; the rows of the others are kept."""
    http = session()
    stations = store.load_stations(country)
    ids = {s["station_id"] for s in stations}
    trends = chj_piezometry.trends(chj_piezometry.fetch(http)) if country in (None, "ES") else {}
    rows = []
    if country and CONTEXT_FILE.exists():
        with CONTEXT_FILE.open(encoding="utf-8") as f:
            rows = [r for r in csv.DictReader(f) if r["station_id"] not in ids]
    for s in stations:
        lon, lat = float(s["lon"]), float(s["lat"])
        try:
            river = wise.river_body_at(lon, lat, s["water_body_code"], s["river"], http=http)
            aquifers = wise.aquifers_at(lon, lat, http=http)
        except Exception as e:   # one failed lookup leaves that station without context
            log(f"{s['station_id']}: {type(e).__name__} {e}")
            continue
        base = {"station_id": s["station_id"], "river_body_code": river.code if river else "",
                "flow_pressures": ";".join(river.flow_pressures) if river else ""}
        if not aquifers:
            rows.append(base)
        for a in aquifers:
            t = trends.get(a.code.removeprefix(CHJ_PREFIX)) if a.code.startswith(CHJ_PREFIX) else None
            rows.append({**base, "aquifer_code": a.code, "aquifer_name": a.name, "aquifer_status": a.status,
                         "aquifer_at_risk": int(a.at_risk),
                         **({"level_trend_m_year": f"{t.slope_m_per_year:.3f}", "trend_piezometers": t.piezometers,
                             "trend_falling": t.falling, "trend_years": f"{t.first_year}-{t.last_year}"} if t else {})})
        log(f"{s['station_id']}: river body {base['river_body_code'] or '—'}, {len(aquifers)} aquifer(s)")
    with CONTEXT_FILE.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, restval="")
        w.writeheader()
        w.writerows(rows)
    return len(rows)


def load() -> dict[str, Context]:
    if not CONTEXT_FILE.exists():
        return {}
    by_station: dict[str, list[dict]] = {}
    with CONTEXT_FILE.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            by_station.setdefault(r["station_id"], []).append(r)
    return {sid: Context(rs[0]["river_body_code"], tuple(p for p in rs[0]["flow_pressures"].split(";") if p),
                         tuple(r for r in rs if r["aquifer_code"]))
            for sid, rs in by_station.items()}
