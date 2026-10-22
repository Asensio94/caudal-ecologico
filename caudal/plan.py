"""Read the minimum ecological flows straight from the BOE, never typed by hand.

Real Decreto 35/2023 approved the 2022–2027 plans of the intercommunity basins. The
BOE open-data API returns each annex block as XML with the tables as plain HTML, so
the values here are parsed from the official text and every one keeps its legal
reference. Run `python -m caudal.cli plan` to rebuild data/requirements/*.csv.
"""
from __future__ import annotations

import csv
import math
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


def tables_by_appendix(html: str) -> dict[str, list[list[list[str]]]]:
    """Tables grouped by the "Apéndice 6.2"-style heading above them, so a reordering of
    the annex or an extra table does not shift which one is read as which."""
    parts = re.split(r'<p class="[^"]*">\s*Ap[ée]ndice\s+(\d+(?:\.\d+)*)', html)
    return {parts[i]: parse_tables(parts[i + 1]) for i in range(1, len(parts) - 1, 2)}


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


# ---- Guadiana (Anexo VI, apéndice 6) ---------------------------------------------

GUADIANA_BLOCK = "a6-22"
NOT_YET_ENFORCEABLE = "(*)"   # Alto Guadiana bodies: only once its aquifers recover


def _body_key(name: str) -> str:
    """'RÍO GUADAJIRA II.' and 'RIO GUADAJIRA II' → 'GUADAJIRA II'; 'RIVERA LIMONETES' and
    'RIVERA DE LOS LIMONETES' → 'LIMONETES'. For comparing names across tables."""
    import unicodedata
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().upper()
    skip = {"RIO", "RIVERA", "ARROYO", "DE", "DEL", "LA", "LAS", "LOS", "EL", "(*)"}
    return " ".join(w for w in re.sub(r"[.,]", " ", plain).split() if w not in skip)


def guadiana_minimums(html: str) -> tuple[dict[str, WaterBodyMinimum], dict[str, list[str]], list[str], list[tuple[str, str]]]:
    """Minimums per water body, SAIH stations per water body, bodies not yet enforceable and
    the 6.1 rows whose code had to be corrected.

    6.1 lists the control stations, 6.2 and 6.3 the ordinary minimums of strategic and
    other bodies (twelve months, then the annual volume), 6.7 the prolonged-drought ones.
    6.1 repeats the body name next to its code; where they disagree (the Guadajira gauge
    carries the Zújar II code), the name wins if it points to exactly one body.
    """
    by_app = tables_by_appendix(html)
    url = CONSOLIDATED_URL.format(boe=BOE_ID, block=GUADIANA_BLOCK)

    def rows(app):
        return [r for t in by_app.get(app, []) for r in t if len(r) >= 14 and r[0].startswith("ES040")]

    def months(r):
        return calendar_order([to_m3s(c) for c in r[2:14]])

    drought = {r[0]: months(r) for r in rows("6.7")}
    minimums, pending, by_name = {}, [], {}
    for r in rows("6.2") + rows("6.3"):
        by_name.setdefault(_body_key(r[1]), []).append(r[0])
        if NOT_YET_ENFORCEABLE in r[1]:
            pending.append(r[0])
            continue
        minimums[r[0]] = WaterBodyMinimum(
            code=r[0], name=r[1].replace(NOT_YET_ENFORCEABLE, "").strip(" ."), protected=False, temporality="",
            ordinary=months(r), drought=drought.get(r[0]),
            legal_ref="RD 35/2023, anexo VI, apéndices 6.2, 6.3 y 6.7", source_url=url)
    names = {code: _body_key(m.name) for code, m in minimums.items()}
    control: dict[str, list[str]] = {}
    corrected = []
    for t in by_app.get("6.1", []):
        for r in t:
            if len(r) < 3 or not r[0].startswith("ES040"):
                continue
            code, station = r[0], r[2].replace(" ", "-")
            if code in names and names[code] != _body_key(r[1]):
                match = by_name.get(_body_key(r[1]), [])
                if len(match) == 1:
                    corrected.append((station, f"El BOE pone junto a esta estación el código {code}, que es de otra "
                                      f"masa, y el nombre {title_es(r[1].strip(' .'))}; se usa la masa del nombre, {match[0]}."))
                    code = match[0]
            control.setdefault(code, []).append(station)
    return minimums, control, pending, corrected


def build_guadiana(boe_html: str, stations: dict) -> tuple[list[dict], list[dict], list[str]]:
    """`stations` is the SIRA catalogue keyed by station code (see sources.guadiana)."""
    minimums, control, pending, corrected = guadiana_minimums(boe_html)
    out_st, reqs = [], []
    unread = [f"Masa {c}: tramo del Alto Guadiana marcado (*), exigible solo cuando se recupere el acuífero"
              for c in pending if c in control]
    fixed = dict(corrected)
    for code, codes in sorted(control.items()):
        wb = minimums.get(code)
        for sc in codes:
            st = stations.get(sc)
            if wb is None or st is None or not st.flow_published:
                if code not in pending:
                    why = ("la masa no tiene mínimo en las tablas 6.2 y 6.3" if wb is None
                           else "la estación no está en el visor SIRA" if st is None
                           else "salida de embalse o azud: el SIRA no publica el caudal soltado al río")
                    unread.append(f"{st.name + ' ' if st else ''}({sc}), masa {code}: {why}")
                continue
            sid = f"guadiana-{sc}"
            out_st.append({"station_id": sid, "basin": "guadiana", "source": "sira-guadiana", "source_id": sc,
                           "name": st.name, "river": st.river, "water_body_code": code,
                           "water_body_name": title_es(wb.name), "protected": 0, "roea": "",
                           "lon": st.lon, "lat": st.lat,
                           "note": fixed.get(sc, f"El plan nombra la estación {sc} para controlar esta masa.")})
            reqs += requirement_rows(sid, wb)
    return out_st, reqs, unread


# ---- Cantábrico (anexos I y II, apéndice 4 of each) ------------------------------

# The two plans share the table layout and the seasons; the Oriental one adds a stretch
# column, and its drought regime is "sequía prolongada" where the Occidental one's is
# "emergencia por sequía declarada".
CANTABRICO_PLANS = {"a4-12": ("anexo I", "Oriental"), "a4-18": ("anexo II", "Occidental")}
# Nota 1 of each table: aguas altas Jan–Apr, medias May, Jun, Nov, Dec, bajas Jul–Oct.
SEASON_OF_MONTH = (0, 0, 0, 0, 1, 1, 2, 2, 2, 2, 1, 1)
RIVER_RESERVE = "*"   # the body holds a Reserva Natural Fluvial stretch with its own minimums
# The gauge must sit on the body's river line and drain nearly the same catchment as the
# point where the plan sets the minimum, so the BOE value applies as it stands.
SNAP_METRES = 50
CATCHMENT_TOLERANCE = 0.10
_WB_CODE = re.compile(r"^ES\d{3}(?!SEXP)[A-Z0-9]+$")


@dataclass(frozen=True)
class ControlPoint:
    """Lower end of a water body (or of a stretch of one) with its minimums."""
    x: float       # ETRS89 UTM 30N
    y: float
    km2: float     # catchment area at the point
    minimum: WaterBodyMinimum
    river_reserve: bool


def _season_months(cells: list[str]) -> tuple[float | None, ...]:
    values = [to_m3s(c) for c in cells]
    return tuple(values[s] for s in SEASON_OF_MONTH)


def _plain_name(name: str) -> str:
    """'Río Nansa I*.' → 'Río Nansa I'; 'RÍo Deva III.' → 'Río Deva III'."""
    return re.sub(r"^R[ÍI]o\b", "Río", name.replace("*", "").strip(" ."))


def cantabrico_points(html: str, block: str) -> list[ControlPoint]:
    """Apéndice 4.1: rivers and reservoirs. The last nine cells of a row are the lower-end
    UTM X and Y, the catchment area and three seasonal minimums for each regime; the
    Occidental plan opens each exploitation system with an extra system-code cell."""
    annex, part = CANTABRICO_PLANS[block]
    url = CONSOLIDATED_URL.format(boe=BOE_ID, block=block)
    out = []
    for r in (r for t in tables_by_appendix(html).get("4.1", []) for r in t):
        codes = [i for i, c in enumerate(r) if _WB_CODE.match(c)]
        if not codes or len(r) - codes[0] < 11:
            continue
        i = codes[0]
        name = _plain_name(r[i + 1])
        if len(r) - i == 12 and r[i + 2].strip(" .-"):     # Oriental stretch
            name += f" ({r[i + 2].strip(' .')})"
        x, y, km2, *values = r[-9:]
        out.append(ControlPoint(
            x=to_m3s(x), y=to_m3s(y), km2=to_m3s(km2), river_reserve=RIVER_RESERVE in r[i + 1].replace("**", ""),
            minimum=WaterBodyMinimum(
                code=r[i], name=name, protected=False, temporality="",
                ordinary=_season_months(values[:3]), drought=_season_months(values[3:]),
                legal_ref=f"RD 35/2023, {annex} (Cantábrico {part}), apéndice 4.1", source_url=url)))
    return out


def _distance_to_line(px: float, py: float, paths) -> float:
    best = float("inf")
    for path in paths:
        for (ax, ay), (bx, by) in zip(path, path[1:]):
            dx, dy = bx - ax, by - ay
            t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
            best = min(best, math.hypot(px - ax - t * dx, py - ay - t * dy))
    return best


def build_cantabrico(boe_html: dict[str, str], gauges: dict, catchments: dict[str, float],
                     river_bodies: dict[str, list]) -> tuple[list[dict], list[dict], list[str]]:
    """The plans name no gauges, so each SAIH gauge is placed by geometry: on the river
    line of a water body (as the basin's own visor does) and at one of that body's
    control points, judged by catchment area. A gauge in the upper part of a long body
    drains less than the lower end the minimum is set for, so it is left out."""
    points: dict[str, list[ControlPoint]] = {}
    for block, html in boe_html.items():
        for p in cantabrico_points(html, block):
            points.setdefault(p.minimum.code, []).append(p)
    stations, reqs, unread = [], [], []
    for roea, g in sorted(gauges.items()):
        label = f"{title_es(g.name)} ({title_es(g.river)}), ROEA {roea}"
        on = {c for c, paths in river_bodies.items() if c in points and _distance_to_line(g.x, g.y, paths) <= SNAP_METRES}
        area = catchments.get(roea)
        if area is None:
            unread.append(f"{label}: sin superficie de cuenca en el anuario del CEDEX")
            continue
        fits = [p for c in on for p in points[c] if abs(area / p.km2 - 1) <= CATCHMENT_TOLERANCE]
        if len(fits) != 1:
            why = "no está sobre una masa con caudal mínimo" if not on else                   "su cuenca no coincide con la de ningún punto de control" if not fits else "encaja en varios puntos"
            unread.append(f"{label}: {why}")
            continue
        p = fits[0]
        if p.river_reserve:
            unread.append(f"{label}: masa con tramo de reserva natural fluvial (apéndice aparte)")
            continue
        sid = f"cantabrico-{roea}"
        stations.append({"station_id": sid, "basin": "cantabrico", "source": "saih-cantabrico", "source_id": roea,
                         "name": title_es(g.name), "river": title_es(g.river), "water_body_code": p.minimum.code,
                         "water_body_name": p.minimum.name, "protected": 0, "roea": roea,
                         **dict(zip(("lon", "lat"), utm30_to_lonlat(g.x, g.y))),
                         "note": f"A {_distance_to_line(g.x, g.y, river_bodies[p.minimum.code]):.0f} m del cauce de la masa; "
                                 f"cuenca de {area:,.0f} km² frente a {p.km2:,.0f} km² en el punto del plan.".replace(",", ".")})
        reqs += requirement_rows(sid, p.minimum)
    return stations, reqs, unread


# ---- Guadalquivir (anexo VII, apéndice 6) ----------------------------------------

GUADALQUIVIR_BLOCK = "a6-30"
# 6.1.3 (ordinary) and 6.2.2 (prolonged drought) set the minimums of the monitoring
# network in l/s over five periods: Oct–Nov, Dec–Apr, May, Jun and Jul–Sep.
PERIOD_OF_MONTH = (1, 1, 1, 1, 2, 3, 4, 4, 4, 0, 0, 1)
LITRES = 0.001
MONTHS_ES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
             "octubre", "noviembre", "diciembre")


def _place_key(text: str) -> str:
    """'Estación de aforos de Écija(*).' → 'ecija'; 'Presa de Alcalá del Río.' → 'alcala rio'."""
    import unicodedata
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    skip = {"estacion", "aforos", "presa", "azud", "de", "del", "el", "la"}
    return " ".join(w for w in re.sub(r"[^a-z ]", " ", plain).split() if w not in skip)


def _litres(cell: str) -> float | None:
    """'1.600' l/s → 1.6 m³/s. A decimal comma has no place in an l/s table (Arroyo María
    reads '1,22' in May and June, against 370–610 the rest of the year): left blank, not guessed."""
    return None if "," in cell else to_m3s(cell, LITRES)


def guadalquivir_points(html: str) -> dict[tuple[str, str], WaterBodyMinimum]:
    """Minimums per control point, keyed by (river, place) as `_place_key` writes them.
    A row of seven cells opens a river; the rows after it, of six, are further points on it."""
    by_app = tables_by_appendix(html)
    url = CONSOLIDATED_URL.format(boe=BOE_ID, block=GUADALQUIVIR_BLOCK)

    def rows(app):
        river, out = "", {}
        for r in (r for t in by_app.get(app, []) for r in t):
            if len(r) not in (6, 7) or r[-5] == "Oct.-Nov.":
                continue
            if len(r) == 7:
                river = r[0].strip(" .")
            periods = [_litres(c) for c in r[-5:]]
            out[(_place_key(river), _place_key(r[-6]))] = (river, r[-6], tuple(periods[p] for p in PERIOD_OF_MONTH))
        return out

    drought = rows("6.2.2")
    points = {}
    for key, (_, place, ordinary) in rows("6.1.3").items():
        name = re.sub(r"\s*\(\*\)", "", place).strip(" .")
        points[key] = WaterBodyMinimum(
            code="", name=name.replace("Marin", "Marín"), protected=False, temporality="", ordinary=ordinary,
            drought=drought[key][2] if key in drought else None,
            legal_ref="RD 35/2023, anexo VII, apéndices 6.1.3 y 6.2.2", source_url=url)
    return points


def build_guadalquivir(boe_html: str, gauges: dict) -> tuple[list[dict], list[dict], list[str]]:
    """`gauges` maps the plan's (river, place) to the SAIH signal read there (sources.guadalquivir)."""
    points = guadalquivir_points(boe_html)
    if missing := set(gauges) - set(points):   # the BOE text changed under the curated table
        raise ValueError(f"control points not found in the BOE: {sorted(missing)}")
    stations, reqs, unread = [], [], []
    for key, wb in sorted(points.items()):
        blank = [MONTHS_ES[i] for i, v in enumerate(wb.ordinary) if v is None]
        g = gauges.get(key)
        if g is None:
            unread.append(f"{wb.name}: el SAIH no publica el caudal que circula por el punto")
            continue
        sid = f"guadalquivir-{g.signal.split('_')[0].lower()}"
        stations.append({"station_id": sid, "basin": "guadalquivir", "source": "saih-guadalquivir",
                         "source_id": g.signal, "name": g.name, "river": g.river, "water_body_code": "",
                         "water_body_name": wb.name, "protected": 0, "roea": g.roea,
                         **dict(zip(("lon", "lat"), utm30_to_lonlat(g.x, g.y))),
                         "note": g.note + (f" En {' y '.join(blank)} el BOE no da un valor legible en l/s: esos meses "
                                           "quedan sin mínimo." if blank else "")})
        reqs += requirement_rows(sid, wb)
    return stations, reqs, unread


# ---- Output --------------------------------------------------------------------

REQ_FIELDS = (["station_id", "water_body_code", "water_body_name", "protected", "temporality", "regime"]
              + [f"m{m:02d}" for m in range(1, 13)] + ["valid_from", "valid_to", "legal_ref", "source_url"])


def write_requirements(basin: str, rows: list[dict], fields: list[str] = REQ_FIELDS) -> None:
    path = REQUIREMENTS_DIR / f"{basin}.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
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
                  "water_body_code", "water_body_name", "protected", "roea", "lon", "lat", "note", "country", "municipality"]


def build_jucar(boe_html: str, gauges: dict) -> tuple[list[dict], list[dict], list[str]]:
    """Station rows, requirement rows and the plan control points no public gauge reads."""
    minimums, control = jucar_minimums(boe_html)
    stations, reqs, unread = [], [], []
    for code, roeas in sorted(control.items()):
        wb = minimums.get(code)
        for roea in roeas:
            g = gauges.get(roea)
            if wb is None or g is None:
                why = "la masa no tiene mínimo en las tablas 5.1 y 5.2" if wb is None else "el SAIH no publica un aforo con ese código"
                unread.append(f"{wb.name + ' (' if wb else ''}ROEA {roea}, masa {code}{')' if wb else ''}: {why}")
                continue
            sid = f"jucar-{roea}"
            stations.append({"station_id": sid, "basin": "jucar", "source": "saih-jucar", "source_id": g.variable_id,
                             "name": title_es(re.sub(r"^EA\s*\d+\s*", "", g.name)), "river": title_es(g.river),
                             "water_body_code": code, "water_body_name": wb.name, "protected": int(wb.protected),
                             "roea": roea, **dict(zip(("lon", "lat"), utm30_to_lonlat(g.utm_x, g.utm_y))),
                             "note": f"El plan nombra el aforo ROEA {roea} para controlar esta masa."})
            reqs += requirement_rows(sid, wb)
    return stations, reqs, unread


def utm30_to_lonlat(x: float, y: float) -> tuple[float, float]:
    """ETRS89 / UTM zone 30N to longitude and latitude (degrees, 5 decimals ≈ 1 m).

    Standard inverse transverse Mercator series on GRS80; enough for placing a gauge on a map.
    """
    import math
    a, f, k0 = 6378137.0, 1 / 298.257222101, 0.9996
    e2 = f * (2 - f)
    ep2 = e2 / (1 - e2)
    x -= 500000.0
    m = y / k0
    mu = m / (a * (1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256))
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    phi1 = (mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu)
            + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * math.sin(4 * mu)
            + (151 * e1 ** 3 / 96) * math.sin(6 * mu))
    n1 = a / math.sqrt(1 - e2 * math.sin(phi1) ** 2)
    t1 = math.tan(phi1) ** 2
    c1 = ep2 * math.cos(phi1) ** 2
    r1 = a * (1 - e2) / (1 - e2 * math.sin(phi1) ** 2) ** 1.5
    d = x / (n1 * k0)
    lat = phi1 - (n1 * math.tan(phi1) / r1) * (
        d ** 2 / 2 - (5 + 3 * t1 + 10 * c1 - 4 * c1 ** 2 - 9 * ep2) * d ** 4 / 24
        + (61 + 90 * t1 + 298 * c1 + 45 * t1 ** 2 - 252 * ep2 - 3 * c1 ** 2) * d ** 6 / 720)
    lon = (d - (1 + 2 * t1 + c1) * d ** 3 / 6
           + (5 - 2 * c1 + 28 * t1 - 3 * c1 ** 2 + 8 * ep2 + 24 * t1 ** 2) * d ** 5 / 120) / math.cos(phi1)
    return round(math.degrees(lon) - 3.0, 5), round(math.degrees(lat), 5)


_LOWER = {"de", "del", "la", "las", "los", "el", "y", "d'en", "en", "da", "do", "das", "dos"}


# Water bodies split into stretches are numbered "IV", "II B"...; those stay upper case.
_ORDINAL = re.compile(r"^(?:[ivx]+|[a-d])$")
# The Guadiana annex is written in capitals without accents.
_ACCENTS = {"rio": "río"}


def title_es(text: str) -> str:
    """'SALIDA DE ARQUILLO' → 'Salida de Arquillo', 'RIO GUADIANA IV B' → 'Río Guadiana IV B',
    'PONTENOVA (A)' → 'Pontenova (A)': a bracketed word opens its own phrase."""
    words = [_ACCENTS.get(w, w) for w in text.lower().split()]
    return " ".join("(" + w[1:2].upper() + w[2:] if w.startswith("(")
                    else w.upper() if i and _ORDINAL.match(w) else w if i and w in _LOWER else w[:1].upper() + w[1:]
                    for i, w in enumerate(words))


def write_excluded(rows: list[tuple[str, str]], country: str = "ES") -> None:
    """(basin, reason) for every plan point or gauge left out, so the page can list them.
    Replaces the rows of `country` and keeps those of the others."""
    from .config import EXCLUDED_FILE
    from .store import load_excluded
    kept = [(r["basin"], r["reason"], r["country"]) for r in load_excluded() if r["country"] != country]
    with EXCLUDED_FILE.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["basin", "reason", "country"])
        w.writerows(kept + [(b, r, country) for b, r in rows])


def write_stations(rows: list[dict], country: str = "ES") -> None:
    """Replace the stations of `country`, keeping those of the others."""
    from .config import STATIONS_FILE
    from .store import load_stations
    rows = [r for r in load_stations() if r["country"] != country] + [{**r, "country": country} for r in rows]
    with STATIONS_FILE.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=STATION_FIELDS, restval="")
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: r["station_id"]))
