"""SAIH Guadalquivir (chguadalquivir.es/saih): hourly flows from the visor's history chart.

The chart page asks `saihhist4.aspx` for one signal and a number of days back from
now, base64-encoded as "SIGNAL,days,0", and gets XML with epoch-UTC times (<x>) and
values (<y>). It needs only the anonymous ASP.NET session cookie that any visitor
gets on the first page. The legal notice allows reproduction citing the source.
"""
from __future__ import annotations

import base64
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from ..compliance import daily_mean
from . import MADRID, DailyFlow, expected_readings, local_day_bounds_utc, session

BASE = "https://www.chguadalquivir.es/saih/"
STEP_MINUTES = 60
MISSING = -999.0


def open_session(http=None):
    http = http or session()
    http.get(f"{BASE}AvisoLegal.aspx", timeout=60).raise_for_status()
    return http


def history_url(signal: str, days_back: int) -> str:
    b = base64.b64encode(f"{signal},{days_back},0".encode()).decode()
    return f"{BASE}saihhist4.aspx?b={b}&k=0x8"


def parse(xml: str) -> list[tuple[datetime, float]]:
    """(UTC time, m³/s) pairs; -999 marks a missing hour. An <Error> body is an empty series."""
    xs = re.search(r"<x>(.*?)</x>", xml, re.S)
    ys = re.search(r"<y>(.*?)</y>", xml, re.S)
    if not xs or not ys:
        return []
    utc = ZoneInfo("UTC")
    out = []
    for t, v in zip(xs.group(1).split(";"), ys.group(1).split(";")):
        try:
            q = float(v)
        except ValueError:
            continue
        if q != MISSING:
            out.append((datetime.fromtimestamp(int(t), utc), q))
    return out


def fetch_range(signal: str, first: date, last: date, http=None) -> list[DailyFlow]:
    """Every day from `first` to `last` in one request: the page counts days back from now."""
    http = http or open_session()
    days_back = (datetime.now(MADRID).date() - first).days + 1
    series: list[tuple[datetime, float]] = []
    for attempt in range(2):   # the page now and then answers "SQL return null" and works on retry
        resp = http.get(history_url(signal, days_back), timeout=120)
        resp.raise_for_status()
        if series := parse(resp.text):
            break
        time.sleep(2)
    out = []
    for i in range((last - first).days + 1):
        day = first + timedelta(days=i)
        start, end = local_day_bounds_utc(day)
        readings = [(int((t - start).total_seconds() // 60), q) for t, q in series if start <= t < end]
        expected = expected_readings(day, STEP_MINUTES)
        out.append(DailyFlow(day, daily_mean(readings, expected), len(readings), expected, "saih-guadalquivir"))
    return out


@dataclass(frozen=True)
class Gauge:
    signal: str
    roea: str      # blank for dams: they are not ROEA gauging stations
    name: str
    river: str
    x: float       # ETRS89 / UTM 30N, from the CHG "Listado de puntos de control"
    y: float


# The flow signal the SAIH publishes at each control point of the plan's monitoring
# network (anexo VII, apéndice 6.1.3), keyed by river and place as the BOE writes them.
# Gauging stations: the CEDEX anuario gives each ROEA code its SAIH point (cod_saih).
# Dams and weirs: the release or circulating flow the CHG's own flow map shows for that
# site. Écija is read at El Villar (ROEA 5165), as that map does: the Écija gauge is out
# of service and El Villar, just upstream, drains the same 8 020 km².
GAUGES = {
    ("guadalquivir", "arroyo maria"): Gauge("A40_211_X", "5001", "Arroyo María", "Guadalquivir", 514377, 4225681),
    ("guadalquivir", "pedro marin"): Gauge("H04_222_X", "", "Presa de Pedro Marín", "Guadalquivir", 463717, 4195812),
    ("guadalquivir", "mengibar"): Gauge("A08_211_X", "5004", "Mengíbar", "Guadalquivir", 429830, 4204333),
    ("guadalquivir", "villafranca"): Gauge("H07_221_X", "", "Presa de Villafranca", "Guadalquivir", 359529, 4202105),
    ("guadalquivir", "fuente palmera"): Gauge("I11_211_X", "", "Azud de Fuente Palmera", "Guadalquivir", 312226, 4182219),
    ("guadalquivir", "penaflor"): Gauge("E53_221_X", "", "Presa de Peñaflor", "Guadalquivir", 294498, 4174453),
    ("guadalquivir", "alcala rio"): Gauge("H09_215_X", "", "Presa de Alcalá del Río", "Guadalquivir", 236970, 4156562),
    ("guadiana menor", "posito"): Gauge("A13_211_X", "5023", "El Pósito", "Guadiana Menor", 481385, 4192701),
    ("guadalimar", "linares"): Gauge("A64_211_X", "5171", "Linares", "Guadalimar", 448697, 4213523),
    ("guadalbullon", "mengibar"): Gauge("A07_211_X", "5029", "Mengíbar", "Guadalbullón", 431415, 4203282),
    ("guadajoz", "valchillon"): Gauge("A14_211_X", "5016", "Valchillón", "Guadajoz", 341176, 4187429),
    ("genil", "canales pinos"): Gauge("A23_211_X", "5020", "Pinos Genil", "Genil", 456224, 4113015),
    ("genil", "loja"): Gauge("A15_211_X", "5045", "Loja", "Genil", 396397, 4114949),
    ("genil", "ecija"): Gauge("I15_211_X", "5165", "Écija (El Villar)", "Genil", 313972, 4163910),
    ("corbones", "carmona"): Gauge("A18_211_X", "", "Carmona", "Corbones", 269747, 4160608),
    ("guadiamar", "aznalcazar"): Gauge("A22_211_X", "5076", "Aznalcázar", "Guadiamar", 211061, 4133459),
}
# Cordobilla publishes only the gates' spill and a pumping flow, not what runs below the dam.
