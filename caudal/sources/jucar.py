"""SAIH Júcar (saih.chj.es): five-minute flows as JSON, no key.

The value endpoint takes local times and answers in UTC. Each reading carries a
quality code; 0 and 128 come with plausible values, 130 with zeros during the 2025
outage, so only the first two are kept until the CHJ documents the codes.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from ..compliance import daily_mean
from . import DailyFlow, expected_readings, local_day_bounds_utc, session

BASE = "https://saih.chj.es"
STEP_MINUTES = 5
VALID_STATES = {0, 128}


def readings_url(variable_id: str, first: date, last: date | None = None) -> str:
    last = last or first
    return f"{BASE}/admin/variables/valor/{variable_id}/{first:%Y-%m-%d}%2000:00:00/{last:%Y-%m-%d}%2023:59:59"


def parse(payload: list[dict], day: date) -> list[tuple[int, float]]:
    """(minute of the local day, m³/s) for the valid readings inside `day`."""
    start, end = local_day_bounds_utc(day)
    out = []
    for r in payload:
        if r.get("estado") not in VALID_STATES or r.get("valor") is None:
            continue
        t = datetime.fromisoformat(r["fecha"].replace("Z", "+00:00"))
        if start <= t < end:
            out.append((int((t - start).total_seconds() // 60), float(r["valor"])))
    return out


def fetch_day(variable_id: str, day: date, http=None) -> DailyFlow:
    http = http or session()
    resp = http.get(readings_url(variable_id, day), timeout=60)
    resp.raise_for_status()
    readings = parse(resp.json(), day)
    expected = expected_readings(day, STEP_MINUTES)
    return DailyFlow(day, daily_mean(readings, expected), len(readings), expected, "saih-jucar")


def fetch_range(variable_id: str, first: date, last: date, http=None) -> list[DailyFlow]:
    """Every day from `first` to `last` in one request: a month of 5-minute data is ~9 000 rows, 2 s."""
    http = http or session()
    resp = http.get(readings_url(variable_id, first, last), timeout=120)
    resp.raise_for_status()
    payload = resp.json()
    out = []
    for i in range((last - first).days + 1):
        day = first + timedelta(days=i)
        readings = parse(payload, day)
        expected = expected_readings(day, STEP_MINUTES)
        out.append(DailyFlow(day, daily_mean(readings, expected), len(readings), expected, "saih-jucar"))
    return out


def water_body(variable_id: str, http=None) -> tuple[str, str]:
    """(water body code, name) the CHJ assigns to a flow variable, e.g. ('18-33', 'Río Júcar: …')."""
    http = http or session()
    props = http.get(f"{BASE}/api/variables/{variable_id}/propiedades", timeout=60).json()[0]
    return props["fkTCodigoMasaAgua"], props["fldTNombreMasaAgua"]


@dataclass(frozen=True)
class Gauge:
    variable_id: str
    roea: str            # "08089": the national gauge code the plan uses to name control points
    name: str            # "EA 89 HUERTO MULET"
    river: str
    utm_x: float         # ETRS89 / UTM 30N, despite the Lat/Lon field names
    utm_y: float


def parse_gauges(page: str) -> dict[str, Gauge]:
    """Flow gauges on the map page, keyed by ROEA code.

    The page embeds `let aforos = [...]`. Gauging stations are named "EA nn …", and
    EA nn is ROEA 08000+nn: the same number the plan's monitoring table cites, so the
    join needs no hand-made mapping. Reservoir outlets without an EA number are skipped.
    """
    m = re.search(r"let aforos\s*=\s*(\[.*?\]);", page, re.S)
    if not m:
        raise ValueError("SAIH Júcar map page changed: no aforos array")
    out = {}
    for a in json.loads(m.group(1)):
        if ea := re.match(r"EA\s*(\d+)", a["fldTNombre"]):
            roea = f"08{int(ea.group(1)):03d}"
            river = re.sub(r"^CAUDAL (SALIDA )?(R[IÍ]O )?", "", a["fldTNombreVariable"]).title()
            out[roea] = Gauge(a["idVariable"], roea, a["fldTNombre"], river,
                              float(a["fldNCoordGPSLat"]), float(a["fldNCoordGPSLon"]))
    return out


def fetch_gauges(http=None) -> dict[str, Gauge]:
    http = http or session()
    resp = http.get(f"{BASE}/mapa-aforos", timeout=60)
    resp.raise_for_status()
    return parse_gauges(resp.text)
