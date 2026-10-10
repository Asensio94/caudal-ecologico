"""SAIH Cantábrico (visor.saichcantabrico.es): the visor's public historical download.

A POST to WordPress admin-ajax returns CSV. robots.txt explicitly allows that path and
the legal notice allows reuse citing the source. Five-minute values come in UTC; a
request for local day D returns 22:00/23:00 UTC of D-1 onwards, so readings are
filtered to the exact local day.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from ..compliance import daily_mean
from . import DailyFlow, expected_readings, local_day_bounds_utc, session

URL = "https://visor.saichcantabrico.es/wp-admin/admin-ajax.php"
STEP_MINUTES = 5
FLOW_PARAMETER = 3       # caudal
FIVE_MINUTES = 1         # id_frecuencia
INSTANT_VALUE = 1        # tipo_dato

# The basin's ArcGIS server (nodoide.chcantabrico.es) publishes the SAIH network and the
# water-body river lines; CEDEX's gauging yearbook gives each gauge's catchment area.
ARCGIS = "https://nodoide.chcantabrico.es/server/rest/services/Internet"
SAIH_LAYER = f"{ARCGIS}/RedesControl/MapServer/0"
# River water bodies of each plan, and the field holding the code the BOE tables use.
RIVER_LAYERS = {f"{ARCGIS}/PH3_Masas_de_Agua/MapServer/4": "MSPF_EM_CD",    # Oriental
                f"{ARCGIS}/PH3_Masas_de_Agua/MapServer/11": "thematicId"}   # Occidental
CEDEX_STATIONS = "https://ceh.cedex.es/anuarioaforos/anuario-2021-2022/CANTABRICO/estaf.csv"
UTM30 = 25830   # ETRS89 / UTM 30N, the frame of the BOE coordinates


@dataclass(frozen=True)
class Gauge:
    roea: str
    name: str
    river: str
    x: float     # ETRS89 UTM 30N
    y: float


def _query(layer: str, http, **params) -> list[dict]:
    resp = http.get(f"{layer}/query", timeout=180, params={"where": "1=1", "f": "json", **params})
    resp.raise_for_status()
    payload = resp.json()
    if "error" in payload or payload.get("exceededTransferLimit"):
        raise RuntimeError(f"{layer}: {payload.get('error') or 'truncated response'}")
    return payload["features"]


def fetch_gauges(http=None) -> dict[str, Gauge]:
    """River gauges of the SAIH network that are in service and record flow, by ROEA code."""
    http = http or session()
    out = {}
    for f in _query(SAIH_LAYER, http, outFields="*", returnGeometry="false"):
        a = f["attributes"]
        if a.get("DATO_NIVEL_CAUDAL") == "Si" and a.get("EN_SERVICIO") == "Si" and (a.get("COD_ROEA") or "").strip():
            roea = a["COD_ROEA"].strip()
            out[roea] = Gauge(roea, a["LOCALIDAD"].strip(), a["RIO"].strip(),
                              float(a["X_ETRS89_UTM30"]), float(a["Y_ETRS89_UTM30"]))
    return out


def fetch_catchments(http=None) -> dict[str, float]:
    """Catchment area (km²) upstream of each gauge, by ROEA code, from the CEDEX yearbook."""
    http = http or session()
    resp = http.get(CEDEX_STATIONS, timeout=120)
    resp.raise_for_status()
    rows = csv.DictReader(io.StringIO(resp.content.decode("latin-1")), delimiter=";")
    return {r["indroea"].strip(): float(r["suprest"]) for r in rows if (r.get("suprest") or "").strip()}


def fetch_river_bodies(http=None) -> dict[str, list[list[tuple[float, float]]]]:
    """Polylines of every river water body, by the code the BOE tables use, in UTM 30N."""
    http = http or session()
    out: dict[str, list] = {}
    for layer, field in RIVER_LAYERS.items():
        for f in _query(layer, http, outFields=field, outSR=UTM30, geometryPrecision=0):
            out.setdefault(f["attributes"][field], []).extend(
                [[(x, y) for x, y, *_ in path] for path in f["geometry"]["paths"]])
    return out


def parse(csv_text: str, day: date) -> list[tuple[int, float]]:
    start, end = local_day_bounds_utc(day)
    out = []
    for line in csv_text.splitlines()[1:]:          # header: Valor;Fecha-hora UTC
        try:
            value, stamp = line.strip().split(";")
            t = datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S").replace(tzinfo=ZoneInfo("UTC"))
            q = float(value)
        except ValueError:
            continue
        if start <= t < end:
            out.append((int((t - start).total_seconds() // 60), q))
    return out


def fetch_day(roea_code: str, day: date, http=None) -> DailyFlow:
    http = http or session()
    resp = http.post(URL, timeout=60, data={
        "action": "ddh_descargar_historico", "cod_roea": roea_code,
        "id_frecuencia": FIVE_MINUTES, "id_parametro": FLOW_PARAMETER, "tipo_dato": INSTANT_VALUE,
        "fechaInicio": f"{day:%Y-%m-%d}", "fechaFin": f"{day:%Y-%m-%d}", "tipoArchivo": "csv",
    })
    resp.raise_for_status()
    # 204 with X-DDH-No-Data when the station has nothing for that day.
    readings = parse(resp.text, day) if resp.status_code == 200 else []
    expected = expected_readings(day, STEP_MINUTES)
    return DailyFlow(day, daily_mean(readings, expected), len(readings), expected, "saih-cantabrico")
