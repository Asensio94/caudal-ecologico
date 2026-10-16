"""Status, objectives and exemptions of every water body of a country, from the EEA's WISE.

Spain reported its third-cycle plans (2022–2027) to the European Environment Agency in
summer 2023; La Palma resubmitted in February 2025. The EEA serves what was reported
through Discodata, a read-only SQL endpoint, and the Spanish name and a representative
point of each body through its WFD2022 map services. Nothing here is typed by hand.
France reported the same cycle in 2022–2023; the same queries read it with countryCode='FR'.
Run `python -m caudal.cli wfd` (and `wfd --country FR`) to rebuild data/wfd/*.csv.
"""
from __future__ import annotations

import csv
import re

from .config import WFD_DIR
from .plan import title_es
from .sources import session

DISCODATA = "https://discodata.eea.europa.eu/sql"
# A pinned release: [latest] moves with every EEA update, and a silent change of the
# numbers behind the page should come as a deliberate commit, not overnight.
SCHEMA = "[WISE_WFD].[v2r1]"
CYCLE = 2022           # cYear of the third cycle; the same tables hold 2010 and 2016
PAGE = 50_000         # every Spanish table fits in one page; Discodata refuses ORDER BY


def scope(country: str) -> str:
    return f"countryCode='{country}' AND cYear={CYCLE}"


SPAIN = scope("ES")

MAPS = "https://marine.discomap.eea.europa.eu/arcgis/rest/services/WISE_WFD"
# River lines, lake/transitional/coastal polygons, groundwater bodies: name in Spanish
# (nameText) and the EEA's representative point (lat, lon), read as plain attributes.
PLACE_LAYERS = (f"{MAPS}/WFD2022_SurfaceWaterBody_WM/MapServer/16",
                f"{MAPS}/WFD2022_SurfaceWaterBody_WM/MapServer/17",
                f"{MAPS}/WFD2022_GroundWaterBody_WM/MapServer/2")
MAP_PAGE = 2000        # maxRecordCount of those services

RBD_NAMES = {
    "ES010": "Miño-Sil", "ES014": "Galicia-Costa", "ES017": "Cantábrico Oriental",
    "ES018": "Cantábrico Occidental", "ES020": "Duero", "ES030": "Tajo", "ES040": "Guadiana",
    "ES050": "Guadalquivir", "ES060": "Cuencas Mediterráneas Andaluzas", "ES063": "Guadalete y Barbate",
    "ES064": "Tinto, Odiel y Piedras", "ES070": "Segura", "ES080": "Júcar", "ES091": "Ebro",
    "ES100": "Cataluña", "ES110": "Islas Baleares", "ES120": "Gran Canaria", "ES122": "Fuerteventura",
    "ES123": "Lanzarote", "ES124": "Tenerife", "ES125": "La Palma", "ES126": "La Gomera",
    "ES127": "El Hierro", "ES150": "Ceuta", "ES160": "Melilla",
    # French river basin districts, under their usual French names.
    "FRA": "Artois-Picardie", "FRB1": "Meuse", "FRB2": "Sambre", "FRC": "Rhin",
    "FRD": "Rhône et côtiers méditerranéens", "FRE": "Corse", "FRF": "Adour-Garonne",
    "FRG": "Loire-Bretagne", "FRH": "Seine-Normandie", "FRI": "Guadeloupe", "FRJ": "Martinique",
    "FRK": "Guyane", "FRL": "La Réunion", "FRM": "Mayotte",
}



def surface_sql(country: str) -> str:
    return f"""SELECT euSurfaceWaterBodyCode code, euRBDCode rbd, surfaceWaterBodyCategory category,
  naturalAWBHMWB nature, surfaceWaterBodyName name_en,
  swEcologicalStatusOrPotentialValue ecological, swChemicalStatusValue chemical,
  swEcologicalStatusOrPotentialExpectedAchievementDate ecological_by,
  swChemicalStatusExpectedAchievementDate chemical_by, fileUrl file_url
FROM {SCHEMA}.[SWB_SurfaceWaterBody] WHERE {scope(country)}"""


def ground_sql(country: str) -> str:
    return f"""SELECT euGroundWaterBodyCode code, euRBDCode rbd, groundWaterBodyName name_en,
  gwQuantitativeStatusValue quantitative, gwChemicalStatusValue chemical,
  gwQuantitativeStatusExpectedAchievementDate quantitative_by,
  gwChemicalStatusExpectedAchievementDate chemical_by, fileUrl file_url
FROM {SCHEMA}.[GWB_GroundWaterBody] WHERE {scope(country)}"""


SURFACE_SQL, GROUND_SQL = surface_sql("ES"), ground_sql("ES")

# (table, code field, exemption-type field, pressure field, aspect). Exemptions come one
# row per water body and pressure (and per substance or pollutant for chemical status).
EXEMPTION_TABLES = (
    ("SWB_SurfaceWaterBody_SWEcologicalExemptionType", "euSurfaceWaterBodyCode",
     "swEcologicalExemptionType", "swEcologicalExemptionPressure", "ecological"),
    ("SWB_SurfaceWaterBody_SWPrioritySubstance_SWChemicalExemptionType", "euSurfaceWaterBodyCode",
     "swChemicalExemptionType", "swChemicalExemptionPressure", "chemical"),
    ("GWB_GroundWaterBody_gwQuantitativeExemptionType", "euGroundWaterBodyCode",
     "gwQuantitativeExemptionType", None, "quantitative"),
    ("GWB_GroundWaterBody_GWPollutant_GWChemicalExemptionType", "euGroundWaterBodyCode",
     "gwChemicalExemptionType", "gwChemicalExemptionPressure", "chemical"),
)
# Quantitative exemptions keep their pressures in a table of their own, by body only.
GW_QUANT_PRESSURES = "GWB_GroundWaterBody_gwQuantitativeExemptionPressure"

_EXEMPTION = re.compile(r"^Article\s+(4\(\d\))(?:\s*-\s*(.+))?$")
_REPORTED = re.compile(r"_(\d{4})(\d{2})(\d{2})\.xml$")


def sql(query: str, http=None) -> list[dict]:
    """All rows of a Discodata query. Pages are a safety net: without ORDER BY (refused by
    the endpoint) their order is not guaranteed, so PAGE is set above any Spanish table."""
    http = http or session()
    rows, page = [], 1
    while True:
        resp = http.get(DISCODATA, params={"query": query, "p": page, "nrOfHits": PAGE}, timeout=180)
        resp.raise_for_status()
        payload = resp.json()
        if "errors" in payload:
            raise RuntimeError(f"Discodata: {payload['errors']}")
        batch = payload.get("results", [])
        rows += batch
        if len(batch) < PAGE:
            return rows
        page += 1


def parse_exemption(value: str | None) -> tuple[str, str] | None:
    """'Article 4(4) - Technical feasibility' → ('4(4)', 'technical feasibility'); 'None' → None."""
    m = _EXEMPTION.match((value or "").strip())
    if not m:
        return None
    return m.group(1), (m.group(2) or "").strip().lower()


def reported_on(file_url: str | None) -> str:
    """'…/SWB_ES_ES125_20250228.xml' → '2025-02-28': the date Spain delivered that file."""
    m = _REPORTED.search(file_url or "")
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else ""


def body_name(text: str, country: str = "ES") -> str:
    """'RÍO MIÑO I' → 'Río Miño I'; 'ZUMAIA-IRUN' → 'Zumaia-Irun'. French names: title_fr."""
    if country == "FR":
        return title_fr(text)
    return re.sub(r"-(\w)", lambda m: "-" + m.group(1).upper(), title_es(text))


_FR_LOWER = {"de", "du", "des", "la", "le", "les", "à", "au", "aux", "et", "en", "sur", "sous", "l", "d"}
# Words a French body name capitalises only by accident ("Depuis la Source Jusqu'A la Confluence
# Avec la Bouble"). "A" alone is the preposition à, its accent lost upstream.
_FR_PLAIN = _FR_LOWER | {"ses", "sa", "son", "depuis", "avec", "jusqu", "confluence", "confluent", "source",
                         "affluents", "affluent", "incluse", "inclus", "exclue", "exclu", "amont", "aval", "a"}


def title_fr(text: str) -> str:
    """'LA GARONNE DU CONFLUENT DE L'ARIÈGE AU CONFLUENT DE L'AVEYRON' → 'La Garonne du confluent
    de l'Ariège au confluent de l'Aveyron'. Names already in mixed case keep their proper nouns
    and only lose the capitals of their common words."""
    text = text.strip()
    plain = _FR_PLAIN if text != text.upper() else _FR_LOWER | {"confluent", "confluence", "amont", "aval"}

    def word(w: str, first: bool) -> str:
        parts = re.split(r"([-'’])", w if text != text.upper() else w.lower())
        out = []
        for i, part in enumerate(parts):
            low = part.lower()
            if part in "-'’" or not part:
                out.append(part)
            elif low in plain and not (first and i == 0) and (i + 1 < len(parts) or i == 0 or parts[i - 1] in "'’"):
                out.append("à" if low == "a" else low)
            elif text != text.upper():
                out.append(part)
            else:
                out.append(part[:1].upper() + part[1:])
        return "".join(out)
    return " ".join(word(w, i == 0) for i, w in enumerate(text.split()))


def fetch_exemptions(http=None, country: str = "ES") -> list[dict]:
    """One row per water body, aspect, article and reason, with the pressures behind it."""
    http = http or session()
    found: dict[tuple, set[str]] = {}
    for table, code, kind, pressure, aspect in EXEMPTION_TABLES:
        # '!=' rather than '<>': the endpoint rejects queries containing '<>'.
        cols = f"{code} code, {kind} kind" + (f", {pressure} pressure" if pressure else "")
        query = (f"SELECT DISTINCT {cols} FROM {SCHEMA}.[{table}] WHERE {scope(country)} "
                 f"AND {kind} IS NOT NULL AND {kind} != 'None'")
        for r in sql(query, http):
            parsed = parse_exemption(r["kind"])
            if parsed:
                found.setdefault((r["code"], aspect, *parsed), set()).update(
                    [r["pressure"]] if r.get("pressure") else [])
    quant = sql(f"SELECT DISTINCT euGroundWaterBodyCode code, gwQuantitativeExemptionPressure pressure "
                f"FROM {SCHEMA}.[{GW_QUANT_PRESSURES}] WHERE {scope(country)} "
                f"AND gwQuantitativeExemptionPressure IS NOT NULL", http)
    for r in quant:
        for key, pressures in found.items():
            if key[0] == r["code"] and key[1] == "quantitative":
                pressures.add(r["pressure"])
    return [{"code": c, "aspect": a, "article": art, "reason": why, "pressures": "; ".join(sorted(p))}
            for (c, a, art, why), p in sorted(found.items())]


def fetch_places(http=None, country: str = "ES") -> dict[str, tuple[str, float, float]]:
    """Name in the country's language, longitude and latitude of each water body, by its EU code."""
    http = http or session()
    out = {}
    for layer in PLACE_LAYERS:
        offset = 0
        while True:
            resp = http.get(f"{layer}/query", timeout=180, params={
                "where": f"countryCode='{country}'", "outFields": "thematicIdIdentifier,nameText,lat,lon",
                "returnGeometry": "false", "orderByFields": "OBJECTID", "resultOffset": offset,
                "resultRecordCount": MAP_PAGE, "f": "json"})
            resp.raise_for_status()
            payload = resp.json()
            if "error" in payload:
                raise RuntimeError(f"{layer}: {payload['error']}")
            feats = payload.get("features", [])
            for f in feats:
                a = f["attributes"]
                if a.get("lat") is not None and a.get("lon") is not None:
                    out[a["thematicIdIdentifier"]] = ((a.get("nameText") or "").strip(), a["lon"], a["lat"])
            if not payload.get("exceededTransferLimit") and len(feats) < MAP_PAGE:
                break
            offset += len(feats)
    return out


WB_FIELDS = ["code", "rbd", "category", "nature", "name", "ecological", "chemical", "quantitative",
             "ecological_by", "chemical_by", "quantitative_by", "reported", "lon", "lat"]
EXEMPTION_FIELDS = ["code", "aspect", "article", "reason", "pressures"]


def build_bodies(surface: list[dict], ground: list[dict], places: dict, country: str = "ES") -> list[dict]:
    """One row per water body. Status values are the WISE codes: 1 high, 2 good, 3 moderate
    (chemical and groundwater: failing), 4 poor, 5 bad, 'Unknown'."""
    rows = []
    for r, category in [(r, r["category"]) for r in surface] + [(r, "GW") for r in ground]:
        name, lon, lat = places.get(r["code"], ("", "", ""))
        rows.append({
            "code": r["code"], "rbd": r["rbd"], "category": category, "nature": r.get("nature") or "",
            "name": body_name(name, country) if name else (
                title_es(r.get("name_en") or "") if country == "ES" else title_fr(r.get("name_en") or "")),
            **{k: r.get(k) or "" for k in ("ecological", "chemical", "quantitative",
                                            "ecological_by", "chemical_by", "quantitative_by")},
            "reported": reported_on(r.get("file_url")), "lon": lon, "lat": lat})
    return rows


def match_code(code: str, rbd: str, known: set[str]) -> str | None:
    """The EU code of a body named the way a basin plan names it.

    The Júcar plan writes '18-33' for ES080MSPF18-33 and '080-102' for ES080MSBT080-102;
    the Cantábrico Oriental one writes 'ES052MAR002710' for ES017MSPFES052MAR002710.
    Guadiana and Cantábrico Occidental use the EU code as it is.
    """
    if code in known:
        return code
    for kind in ("MSPF", "MSBT"):
        if f"{rbd}{kind}{code}" in known:
            return f"{rbd}{kind}{code}"
    tail = [k for k in known if k.startswith(rbd) and k.endswith(code)]
    return tail[0] if len(tail) == 1 else None


def file_name(base: str, country: str = "ES") -> str:
    """'water_bodies.csv' for Spain (as before France was added), 'water_bodies_fr.csv' for France."""
    return base if country == "ES" else base.replace(".csv", f"_{country.lower()}.csv")


def write_csv(name: str, fields: list[str], rows: list[dict]) -> None:
    with (WFD_DIR / name).open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def read_csv(name: str) -> list[dict]:
    path = WFD_DIR / name
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))
