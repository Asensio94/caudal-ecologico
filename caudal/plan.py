"""Read the minimum ecological flows straight from the BOE, never typed by hand.

Real Decreto 35/2023 approved the 2022–2027 plans of the intercommunity basins. The
BOE open-data API returns each annex block as XML with the tables as plain HTML, so
the values here are parsed from the official text and every one keeps its legal
reference. Run `python -m caudal.cli plan` to rebuild data/requirements/*.csv.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from html.parser import HTMLParser

import requests

from .config import REQUIREMENTS_DIR

BOE_ID = "BOE-A-2023-3511"
BLOCK_URL = "https://www.boe.es/datosabiertos/api/legislacion-consolidada/id/{boe}/texto/bloque/{block}"
CONSOLIDATED_URL = "https://www.boe.es/buscar/act.php?id={boe}#{block}"

# Tables list months October first, as the hydrological year does.
HYDRO_MONTHS = (10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9)
CESE = "cese"   # months an intermittent river may run dry: the minimum is zero


class _Tables(HTMLParser):
    """Rows of every <table> as lists of cell text. Footnote marks (<sup>) are dropped."""

    def __init__(self):
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._sup = 0

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.tables.append([])
        elif tag == "tr":
            self._row = []
        elif tag in ("td", "th"):
            self._cell = []
        elif tag == "sup":
            self._sup += 1

    def handle_endtag(self, tag):
        if tag == "sup":
            self._sup -= 1
        elif tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None and self.tables:
            self.tables[-1].append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None and not self._sup:
            self._cell.append(data)


def parse_tables(html: str) -> list[list[list[str]]]:
    p = _Tables()
    p.feed(html)
    return p.tables


def fetch_block(block: str, http=None) -> str:
    http = http or requests
    resp = http.get(BLOCK_URL.format(boe=BOE_ID, block=block), headers={"Accept": "application/xml"}, timeout=120)
    resp.raise_for_status()
    return resp.content.decode("utf-8")


def to_m3s(cell: str, unit_factor: float = 1.0) -> float | None:
    """'0,03' → 0.03; 'Cese' → 0.0; blank or '-' → None. `unit_factor` 0.001 for l/s tables."""
    text = cell.strip().lower()
    if text == CESE:
        return 0.0
    text = text.replace(".", "").replace(",", ".")
    try:
        return round(float(text) * unit_factor, 6)
    except ValueError:
        return None


def calendar_order(hydro_values: list[float | None]) -> tuple[float | None, ...]:
    """Reorder 12 values from October-first to January-first."""
    by_month = dict(zip(HYDRO_MONTHS, hydro_values))
    return tuple(by_month[m] for m in range(1, 13))


@dataclass(frozen=True)
class WaterBodyMinimum:
    code: str
    name: str
    protected: bool
    temporality: str
    ordinary: tuple[float | None, ...]
    drought: tuple[float | None, ...] | None
    legal_ref: str
    source_url: str


# ---- Júcar (Anexo XI, apéndice 5) -----------------------------------------------

JUCAR_BLOCK = "a5-65"


def jucar_minimums(html: str) -> tuple[dict[str, WaterBodyMinimum], dict[str, list[str]]]:
    """Minimums per water body and the ROEA gauges the plan names to control each one.

    Table 5.1 is the ordinary regime, 5.2 the prolonged-drought one, both with the same
    rows. The monitoring table lists "ROEA 08030"-style devices per water body; an
    asterisk means a device still to be installed.
    """
    tables = parse_tables(html)
    ordinary, drought = tables[0], tables[1]
    url = CONSOLIDATED_URL.format(boe=BOE_ID, block=JUCAR_BLOCK)

    def rows(table):
        return [r for r in table if len(r) == 16 and re.match(r"^\d{2}-", r[0])]

    drought_by_code = {r[0]: calendar_order([to_m3s(c) for c in r[4:]]) for r in rows(drought)}
    minimums = {}
    for r in rows(ordinary):
        minimums[r[0]] = WaterBodyMinimum(
            code=r[0], name=r[1].rstrip("."), protected=r[2].lower().startswith("s"),
            temporality=r[3], ordinary=calendar_order([to_m3s(c) for c in r[4:]]),
            drought=drought_by_code.get(r[0]), legal_ref="RD 35/2023, anexo XI, apéndice 5.1 y 5.2",
            source_url=url,
        )

    control: dict[str, list[str]] = {}
    monitoring = next(t for t in tables if t and t[0] and "Punto de seguimiento" in t[0])
    for r in monitoring[1:]:
        if len(r) >= 4 and (m := re.search(r"ROEA\s*(\d+)", r[3])):
            control.setdefault(r[0], []).append(m.group(1))
    return minimums, control


# ---- Output --------------------------------------------------------------------

REQ_FIELDS = (["station_id", "water_body_code", "water_body_name", "protected", "temporality", "regime"]
              + [f"m{m:02d}" for m in range(1, 13)] + ["valid_from", "valid_to", "legal_ref", "source_url"])


def write_requirements(basin: str, rows: list[dict]) -> None:
    path = REQUIREMENTS_DIR / f"{basin}.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=REQ_FIELDS)
        w.writeheader()
        w.writerows(rows)


def requirement_rows(station_id: str, wb: WaterBodyMinimum, valid_from="2023-02-11", valid_to="") -> list[dict]:
    """One row per regime. The drought row is left out where it may not apply."""
    def fmt(v):
        return "" if v is None else f"{v:g}"
    base = {"station_id": station_id, "water_body_code": wb.code, "water_body_name": wb.name,
            "protected": int(wb.protected), "temporality": wb.temporality,
            "valid_from": valid_from, "valid_to": valid_to, "legal_ref": wb.legal_ref, "source_url": wb.source_url}
    out = [{**base, "regime": "ordinary", **{f"m{m:02d}": fmt(v) for m, v in enumerate(wb.ordinary, 1)}}]
    if wb.drought and wb.drought != wb.ordinary:
        out.append({**base, "regime": "drought", **{f"m{m:02d}": fmt(v) for m, v in enumerate(wb.drought, 1)}})
    return out


STATION_FIELDS = ["station_id", "basin", "source", "source_id", "name", "river",
                  "water_body_code", "water_body_name", "protected", "roea", "utm_x", "utm_y"]


def build_jucar(boe_html: str, gauges: dict) -> tuple[list[dict], list[dict], list[str]]:
    """Station rows, requirement rows and the plan control points no public gauge reads."""
    minimums, control = jucar_minimums(boe_html)
    stations, reqs, unread = [], [], []
    for code, roeas in sorted(control.items()):
        wb = minimums.get(code)
        for roea in roeas:
            g = gauges.get(roea)
            if wb is None or g is None:
                unread.append(f"{code} ROEA {roea}")
                continue
            sid = f"jucar-{roea}"
            stations.append({"station_id": sid, "basin": "jucar", "source": "saih-jucar", "source_id": g.variable_id,
                             "name": title_es(re.sub(r"^EA\s*\d+\s*", "", g.name)), "river": title_es(g.river),
                             "water_body_code": code, "water_body_name": wb.name, "protected": int(wb.protected),
                             "roea": roea, "utm_x": round(g.utm_x), "utm_y": round(g.utm_y)})
            reqs += requirement_rows(sid, wb)
    return stations, reqs, unread


_LOWER = {"de", "del", "la", "las", "los", "el", "y", "d'en", "en"}


def title_es(text: str) -> str:
    """'SALIDA DE ARQUILLO' → 'Salida de Arquillo': title case that leaves Spanish particles lower."""
    words = text.lower().split()
    return " ".join(w if i and w in _LOWER else w[:1].upper() + w[1:] for i, w in enumerate(words))


def write_stations(rows: list[dict]) -> None:
    from .config import STATIONS_FILE
    with STATIONS_FILE.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=STATION_FIELDS)
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: r["station_id"]))
