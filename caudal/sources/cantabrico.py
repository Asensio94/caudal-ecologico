"""SAIH Cantábrico (visor.saichcantabrico.es): the visor's public historical download.

A POST to WordPress admin-ajax returns CSV. robots.txt explicitly allows that path and
the legal notice allows reuse citing the source. Five-minute values come in UTC; a
request for local day D returns 22:00/23:00 UTC of D-1 onwards, so readings are
filtered to the exact local day.
"""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from ..compliance import daily_mean
from . import DailyFlow, expected_readings, local_day_bounds_utc, session

URL = "https://visor.saichcantabrico.es/wp-admin/admin-ajax.php"
STEP_MINUTES = 5
FLOW_PARAMETER = 3       # caudal
FIVE_MINUTES = 1         # id_frecuencia
INSTANT_VALUE = 1        # tipo_dato


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
