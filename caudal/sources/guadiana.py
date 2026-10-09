"""SIRA Guadiana (siraguadiana.com): the visor's REST backend, ten-minute flows in UTC.

The visor opens an anonymous session for every visitor (user "public") and sends its
JWT in the AUTHJWT header; this does the same. No account is created. The legal
notice of chguadiana.es allows reproduction citing the source.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
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


# River gauges ("CR", "NR") publish QR1 to the public profile; reservoir outlets ("E")
# do not publish their release (QSR) there, so they cannot be read yet.
FLOW_TYPES = {"CR", "NR"}


@dataclass(frozen=True)
class Station:
    code: str
    name: str
    river: str
    kind: str
    lon: float
    lat: float

    @property
    def flow_published(self) -> bool:
        return self.kind in FLOW_TYPES


def fetch_stations(http=None) -> dict[str, Station]:
    http = http or session()
    resp = http.get(f"{BASE}/Visor/estaciones", headers={"AUTHJWT": public_token(http)}, timeout=60)
    resp.raise_for_status()
    out = {}
    for e in resp.json()["estaciones"]:
        river = re.sub(r"^(?:río|arroyo)\s+(?:de\s+)?", "", (e.get("rio") or "").strip())
        out[e["cod_estacion"]] = Station(e["cod_estacion"], e["nombre"], river[:1].upper() + river[1:],
                                         e.get("tipo", ""), e.get("longitud"), e.get("latitud"))
    return out
