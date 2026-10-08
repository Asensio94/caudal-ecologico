"""SIRA Guadiana (siraguadiana.com): the visor's REST backend, ten-minute flows in UTC.

The visor opens an anonymous session for every visitor (user "public") and sends its
JWT in the AUTHJWT header; this does the same. No account is created. The legal
notice of chguadiana.es allows reproduction citing the source.
"""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from ..compliance import daily_mean
from . import DailyFlow, expected_readings, local_day_bounds_utc, session

BASE = "https://siraguadiana.com/backend"
STEP_MINUTES = 10
FLOW = "QR1"


def public_token(http) -> str:
    resp = http.post(f"{BASE}/security/getProfile", timeout=60,
                     json={"COD_USUARIO": "public", "ORIGIN": "db", "APP": "VISOR", "CASTICKET": None})
    resp.raise_for_status()
    return resp.json()["sesionId"]


def parse(payload: dict, variable: str, day: date) -> list[tuple[int, float]]:
    start, end = local_day_bounds_utc(day)
    out = []
    for row in payload.get("valores", []):
        q = row.get(variable)
        if q is None:
            continue
        t = datetime.strptime(row["timestamp"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=ZoneInfo("UTC"))
        if start <= t < end:
            out.append((int((t - start).total_seconds() // 60), float(q)))
    return out


def fetch_day(station: str, day: date, http=None, token: str | None = None) -> DailyFlow:
    http = http or session()
    token = token or public_token(http)
    variable = f"{station}/{FLOW}"
    start, end = local_day_bounds_utc(day)
    resp = http.post(f"{BASE}/Visor/evolucionEstacion", headers={"AUTHJWT": token}, timeout=60, json={
        "variables": [variable], "zoom": "i", "encabezado": True,
        "fecha_i": int(start.timestamp()), "fecha_f": int(end.timestamp()),
    })
    resp.raise_for_status()
    readings = parse(resp.json(), variable, day)
    expected = expected_readings(day, STEP_MINUTES)
    return DailyFlow(day, daily_mean(readings, expected), len(readings), expected, "sira-guadiana")
