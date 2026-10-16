"""Drought restrictions in force at each French gauge, from VigiEau (the State's restriction map).

Prefects split each department into alert zones and, when rivers run low, raise them by
order (arrêté) through four levels: vigilance, alerte, alerte renforcée and crise. VigiEau
answers, for a point, the zone it falls in and the order in force there. Only surface-water
zones (SUP) are asked for: those are the ones that restrict taking water from the river.

VigiEau keeps no history by point, so each run stores the level of the day; the file grows
one row per station and day it is read. The restrictions do not change the DCR: they are
shown as context, the measure the State took while the river was low.
"""
from __future__ import annotations

import csv
import time
from datetime import date

from . import session
from ..config import DATA_DIR

API = "https://api.vigieau.gouv.fr/api/zones"
SITE = "https://vigieau.gouv.fr/"
LEVELS = ("vigilance", "alerte", "alerte_renforcee", "crise")   # mildest first
FILE = DATA_DIR / "vigieau.csv"
FIELDS = ["date", "station_id", "level", "zone_code", "zone_name", "order_from", "order_to", "order_url"]


def zone_at(lon: float, lat: float, http=None) -> dict | None:
    """The surface-water alert zone with an order in force at the point, or None if there is none."""
    http = http or session()
    for attempt in range(4):
        resp = http.get(API, params={"lon": lon, "lat": lat, "profil": "particulier", "zoneType": "SUP"}, timeout=60)
        if resp.status_code not in (500, 502, 503, 504):
            break
        time.sleep(2 ** attempt)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    zones = [z for z in resp.json() if z.get("type") == "SUP" and z.get("niveauGravite") in LEVELS]
    if not zones:
        return None
    z = max(zones, key=lambda z: LEVELS.index(z["niveauGravite"]))   # the strictest, if several
    order = z.get("arrete") or {}
    return {"level": z["niveauGravite"], "zone_code": z.get("code") or "", "zone_name": z.get("nom") or "",
            "order_from": (order.get("dateDebutValidite") or "")[:10], "order_to": (order.get("dateFinValidite") or "")[:10],
            "order_url": order.get("cheminFichier") or ""}


def load() -> dict[str, dict[date, dict]]:
    """Stored levels: station → day → row."""
    if not FILE.exists():
        return {}
    out: dict[str, dict[date, dict]] = {}
    with FILE.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out.setdefault(r["station_id"], {})[date.fromisoformat(r["date"])] = r
    return out


def save(day: date, levels: dict[str, dict | None]) -> None:
    """Store the level of `day` at each station (an empty level: no order in force)."""
    rows = load()
    for sid, z in levels.items():
        rows.setdefault(sid, {})[day] = {"date": day.isoformat(), "station_id": sid, **(z or {"level": ""})}
    with FILE.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, restval="")
        w.writeheader()
        w.writerows(rows[s][d] for s in sorted(rows) for d in sorted(rows[s]))
