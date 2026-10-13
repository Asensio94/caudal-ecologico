"""docs/signals.json for estado-iba, following its CONTRATO.md.

Two kinds of signal:
- `river_flow`: one per gauging station with a day below the minimum in the last 30
  days, as the hub's adapter has read it so far (it stops reading our files once this
  one exists), but with the page's own 5 % margin for measurement error.
- `water_status`: one per water body short of good status or under an exemption of the
  Water Framework Directive. A kind of its own, proposed to the hub; until it takes it,
  the hub drops these signals and keeps the rest.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .compliance import Status
from .config import DOCS_DIR
from .countdown import CATEGORIES, PAGE_URL, REASONS, horizon_label, status_label
from .outlook import VERDICTS
from .wfd import RBD_NAMES

SOURCE = "caudal-ecologico"
SITE = "https://asensio94.github.io/caudal-ecologico/"


def _signal(id_: str, kind: str, day: str, title: str, url: str, **extra) -> dict:
    return {"id": id_, "kind": kind, "date": day, "title": title, "url": url, "precision": "punto",
            "deadline": None, **extra}


def river_flow(rows: list[dict]) -> list[dict]:
    """`rows` as built by web.build_rows: one per station, with its last 30 days evaluated."""
    out = []
    for r in rows:
        s, latest = r["station"], r["latest"]
        days = [x for x in r["results"] if x.flow is not None]
        if not r["below_days"] or latest is None:
            continue
        out.append(_signal(
            s["station_id"], "river_flow", latest.day.isoformat(),
            f"{s['name']}: {r['below_days']} de {len(days)} días por debajo del caudal mínimo",
            f"{SITE}#{s['station_id']}",
            status=latest.status.value, value={"amount": round(latest.flow, 4), "unit": "m³/s"},
            details={"minimum": latest.minimum, "days_below": r["below_days"], "days": len(days),
                     "below_now": latest.status is Status.BELOW, "river": s["river"],
                     "water_body": s["water_body_code"], "point": [float(s["lon"]), float(s["lat"])]}))
    return out


def water_status(bodies: list[dict]) -> list[dict]:
    """`bodies` as built by countdown.bodies(); only the flagged ones become signals."""
    out = []
    for b in bodies:
        if not b["flagged"]:
            continue
        o = b["outlook"]
        aspects = {a: status_label(a, b[a]) for a in ("ecological", "chemical", "quantitative") if b[a]}
        details = {"code": b["code"], "category": CATEGORIES.get(b["category"], b["category"]),
                   "district": RBD_NAMES.get(b["rbd"], b["rbd"]), **aspects,
                   "horizon": horizon_label(o.horizon), "horizon_source": "BOE" if o.horizon_source == "boe" else "AEMA",
                   "exemptions": [f"art. {a}" for a in o.articles], "reasons": [REASONS.get(r, r) for r in o.reasons]}
        if b["lat"] and b["lon"]:
            details["point"] = [round(float(b["lon"]), 5), round(float(b["lat"]), 5)]
        out.append(_signal(b["code"], "water_status", b["reported"],
                           f"{b['name'] or b['code']}: {VERDICTS[o.verdict].lower()}",
                           f"{PAGE_URL}#{b['code']}", status=o.verdict, details=details))
    return out


def build(rows: list[dict], bodies: list[dict], now: datetime | None = None) -> dict:
    now = now or datetime.now(ZoneInfo("UTC"))
    return {
        "source": SOURCE, "version": 1, "generated": now.strftime("%Y-%m-%dT%H:%MZ"),
        "coverage": {"label": "Toda España", "sites": None,
                     "note": "Caudal diario frente al mínimo ecológico en Júcar, Guadiana y Cantábrico; "
                             "estado y plazo de la Directiva Marco del Agua de todas las masas de agua."},
        "signals": river_flow(rows) + water_status(bodies),
    }


def write(rows: list[dict], bodies: list[dict]) -> Path:
    out = DOCS_DIR / "signals.json"
    out.write_text(json.dumps(build(rows, bodies), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return out


def render(today: date | None = None) -> Path:
    from .countdown import bodies
    from .web import build_rows
    today = today or datetime.now(ZoneInfo("Europe/Madrid")).date()
    return write(build_rows(today)[0], bodies())
