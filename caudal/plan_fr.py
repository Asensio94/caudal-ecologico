"""French thresholds: the crisis flows (DCR) of three SDAGE 2022–2027, one basin at a time.

Each SDAGE sets, at a network of nodal points, a low-water objective (DOE), judged over the
season and over years, and a crisis flow (DCR), the daily mean below which only essential
uses may go on. The DCR is the one compared day by day here; the DOE (and the alert flow,
DSA, where the table gives one) is shown alongside as context, since a single day under it
is not a failure of the rule.

- Adour-Garonne publishes its table C3 as a CSV inside a zip, under the Licence Ouverte. Each
  point names a gauge (Code Station Hydro1) and, where that gauge moved or closed, the one
  that replaced it (Hydro2); the first that Hub'Eau publishes is read.
- Loire-Bretagne and Rhône-Méditerranée only print theirs in the SDAGE, in PDF, without the
  gauge's code (Rhône-Méditerranée) or with codes that are often stale (Loire-Bretagne). They
  are kept in data/sdage/<basin>.csv: a transcription checked against the PDF, with the gauge
  of each point chosen by hand (data/sdage/README.md). The tables do not change until the
  next SDAGE, so the PDFs are not downloaded every month.

For every basin, Hub'Eau is asked which gauges published a daily mean recently. Run `python
-m caudal.cli plan-fr` to rebuild data/requirements/<basin>.csv and the French stations.
"""
from __future__ import annotations

import csv
import io
import re
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Callable

import requests

from .config import DATA_DIR
from .plan import REQ_FIELDS
from .sources import hubeau, session

COUNTRY = "FR"
BASIN = "adour-garonne"
ZIP_URL = "https://adour-garonne.eaufrance.fr/upload/DATA/SIG/ZONAGES/SDAGE_2022/C3_DOE_DCR_SDAGE2022_.zip"
CSV_NAME = "data/C3_DOE_DCR.csv"
DATASET_URL = "https://www.data.gouv.fr/fr/datasets/aeag-sdage-2022-2027-doe-dcr/"
LEGAL_REF = "SDAGE Adour-Garonne 2022-2027, disposition C3 (tableau C3)"
VALID_FROM = "2022-03-10"   # arrêté of the coordinating prefect approving the SDAGE

LB = "loire-bretagne"
LB_PDF = ("https://sdage-sage.eau-loire-bretagne.fr/files/live/mounts/midas/Donnees-et-documents/Sdage/"
          "AELB-SDAGE_Tome1_maj_car")
LB_LEGAL = "SDAGE Loire-Bretagne 2022-2027, chapitre 7, tableau des objectifs de quantité aux points nodaux"
RM = "rhone-mediterranee"
RM_PDF = ("https://rhone-mediterranee.eaufrance.fr/sites/sierm/files/content/2022-03/"
          "20220318-SDAGE-2022-2027_vol.principal_ADOPTE-1.pdf")
RM_LEGAL = "SDAGE Rhône-Méditerranée 2022-2027, disposition 7-07, tableau 7C"

SDAGE_DIR = DATA_DIR / "sdage"   # the transcribed tables
REQ_FIELDS_FR = REQ_FIELDS + ["objective", "alert"]   # the DOE and the DSA, as the table writes them
RECENT_DAYS = 60            # a gauge counts as published if Hub'Eau has a daily mean this recent
_SITE = re.compile(r"^[A-Z]\d{7}$")
_PARTIAL = re.compile(r"\[partielle\]|\bbras\b", re.I)   # gauges on one arm of the river


@dataclass(frozen=True)
class NodalPoint:
    basin: str        # sub-basin as the table names it (Garonne, Lot, Charente…), or the basin
    river: str
    label: str        # "Séoune à St Pierre de Clairac"
    codes: tuple[str, ...]   # Hydro1, then Hydro2 when different; only well-formed site codes
    doe: str          # as written: "0.2", or "48/52" where the table gives two values
    dcr: float | None
    alert: str = ""            # the DSA, where the table gives one (Loire-Bretagne)
    dcr_text: str = ""         # the DCR as written when it is not a number ("à définir")
    agency_code: str = ""      # the gauge the agency's layer gives, kept to say when another is read
    why: str = ""              # why no gauge is read, from the review of the transcription
    water_body_code: str = ""  # the river water body the table names (Rhône-Méditerranée)
    revisable: bool = False    # values the table marks (*), open to change during the cycle
    legal_ref: str = ""        # down to the point and page, for the page to cite
    source_url: str = ""


@dataclass(frozen=True)
class Basin:
    slug: str
    table: str                  # how the reasons name the table: "le tableau C3"
    valid_from: str             # arrêté of the coordinating prefect approving the SDAGE
    legal_ref: str
    source_url: str
    load: Callable[..., list[NodalPoint]]


# The agency's server does not send its intermediate certificate, so a client that does not
# fetch it by itself (Python's) cannot verify the chain. The intermediate, downloaded from the
# URL the server certificate gives (cacerts.digitalcertvalidation.com) and signed by DigiCert
# Global Root G2, is kept here and added to certifi's roots. It expires in November 2027.
INTERMEDIATE = Path(__file__).parent / "certs" / "trust-provider-tls-rsa-ca-g1.pem"


def _ca_bundle() -> str:
    import certifi
    bundle = Path(tempfile.gettempdir()) / "caudal-ca-bundle.pem"
    bundle.write_text(Path(certifi.where()).read_text(encoding="ascii") + INTERMEDIATE.read_text(encoding="ascii"),
                      encoding="ascii")
    return str(bundle)


def fetch_table(http=None) -> str:
    http = http or session()
    try:
        resp = http.get(ZIP_URL, timeout=120)
    except requests.exceptions.SSLError:
        resp = http.get(ZIP_URL, timeout=120, verify=_ca_bundle())
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        return z.read(CSV_NAME).decode("latin-1")


def _number(cell: str) -> float | None:
    try:
        return float(cell.strip().replace(",", "."))
    except ValueError:
        return None


def parse_table(text: str) -> list[NodalPoint]:
    rows = list(csv.reader(io.StringIO(text), delimiter=";"))
    out = []
    for r in rows[1:]:
        if len(r) < 7 or not r[2].strip():
            continue
        codes = tuple(dict.fromkeys(c.strip() for c in r[3:5] if _SITE.match(c.strip())))
        out.append(NodalPoint(r[0].strip(), r[1].strip(), r[2].strip(), codes, r[5].strip(), _number(r[6])))
    return out


def doe_value(doe: str) -> float | None:
    """The DOE as one number, or None where the table gives two (they are shown as written)."""
    return _number(doe)


def _river_name(river: str) -> str:
    """"La Séoune" → "Séoune", "L'Isle" → "Isle": the bare name, as the EEA layers write it."""
    return re.sub(r"^(?:La |Le |Les |L')", "", river).strip()


def _written(text: str) -> str:
    """A DOE or DSA as written, or nothing where the table gives no value ("non pertinent")."""
    return text if re.search(r"\d", text) else ""


def build(points: list[NodalPoint], published: set[str], sites: dict[str, dict],
          basin: Basin | None = None) -> tuple[list[dict], list[dict], list[str]]:
    """Station rows, requirement rows and the points left out, with the reason in French."""
    basin = basin or BASINS[BASIN]
    stations, reqs, unread = [], [], []
    for p in points:
        if p.dcr is None:
            written = f" (« {p.dcr_text} »)" if p.dcr_text else ""
            unread.append(f"{p.label} : {basin.table} ne donne pas de DCR chiffré pour ce point{written}")
            continue
        if not p.codes:
            unread.append(f"{p.label} : {p.why or basin.table + ' ne rattache ce point à aucune station hydrométrique'}")
            continue
        code = next((c for c in p.codes if c in published and c in sites), None)
        if code is None:
            unread.append(f"{p.label} ({', '.join(p.codes)}) : Hub'Eau ne publie pas de débit journalier récent "
                          "pour cette station")
            continue
        s = sites[code]
        sid = f"fr-{code}"
        moved = code != p.codes[0]
        stations.append({
            "station_id": sid, "basin": basin.slug, "source": hubeau.SOURCE, "source_id": code, "name": s["name"],
            "river": _river_name(p.river or s["river"]), "water_body_code": p.water_body_code,
            "water_body_name": p.label, "protected": 0, "roea": "", "lon": f"{s['lon']:.5f}",
            "lat": f"{s['lat']:.5f}", "municipality": s["insee"],
            "note": " ".join(x for x in (
                f"Le SDAGE nomme la station {p.codes[0]}, sans débit récent sur Hub'Eau ; on lit {code}, "
                "la station de remplacement que donne le même tableau." if moved else "",
                f"La couche des points nodaux de l'agence de l'eau donne la station {p.agency_code} ; on lit "
                f"{code}, la station de Hub'Eau qui porte le nom que donne le SDAGE."
                if p.agency_code and p.agency_code != code else "",
                "D'après son nom, cette station ne mesure qu'une partie de la rivière (un bras) : un débit "
                "très bas peut ne pas valoir pour tout le cours d'eau." if _PARTIAL.search(s["name"]) else "",
                "Le SDAGE signale le DOE ou le DCR de ce point comme susceptibles d'être modifiés au cours du "
                "cycle 2022-2027." if p.revisable else "") if x)})
        base = {"station_id": sid, "water_body_code": p.water_body_code, "water_body_name": p.label,
                "protected": 0, "temporality": "", "valid_from": basin.valid_from, "valid_to": "",
                "legal_ref": p.legal_ref or basin.legal_ref, "source_url": p.source_url or basin.source_url,
                "objective": _written(p.doe), "alert": _written(p.alert)}
        reqs.append({**base, "regime": "ordinary", **{f"m{m:02d}": f"{p.dcr:g}" for m in range(1, 13)}})
    return stations, reqs, unread


def published_sites(codes: list[str], today: date, http=None) -> set[str]:
    """Sites with at least one daily mean in the last RECENT_DAYS days."""
    rows = hubeau.daily_rows(codes, today - timedelta(days=RECENT_DAYS), today, http)
    return {r["code_site"] for r in rows if r.get("resultat_obs_elab") is not None}


def _label(river: str, location: str) -> str:
    """"Mayenne à Chambellay". A location that already names the river ("Sasse à Valernes")
    stands alone; one that is not a place ("aval immédiat de…", "Station du…") follows a comma."""
    first = lambda s: re.sub(r"^(?:les?|la|l')\s*", "", s.lower()).split()[0] if s.strip() else ""
    if first(location) == first(river):
        return location
    if not location[:1].isupper() or re.match(r"(?:Station|Au|Source|à définir)\b", location):
        return f"{river}, {location[:1].lower()}{location[1:]}"
    return f"{river} à {location}"


def read_transcription(slug: str, path: Path | None = None) -> list[dict]:
    with (path or SDAGE_DIR / f"{slug}.csv").open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def loire_bretagne(rows: list[dict]) -> list[NodalPoint]:
    """The table of the SDAGE's tome 1 (pp. 112-119), one row per nodal point, with its DSA."""
    return [NodalPoint(
        LB, r["river"], _label(r["river"], r["location"]), (r["code"],) if r["code"] else (), r["doe"],
        _number(r["dcr"]), alert=r["dsa"], dcr_text=r["dcr"], agency_code=r["agency_code"], why=r["reason"],
        legal_ref=f"{LB_LEGAL}, point {r['point']} (p. {r['pdf_page']})",
        source_url=f"{LB_PDF}#page={r['pdf_page']}") for r in rows]


def rhone_mediterranee(rows: list[dict]) -> list[NodalPoint]:
    """Table 7C of the SDAGE's main volume, one row per point, with the river water body it names."""
    return [NodalPoint(
        RM, r["river"], _label(r["river"], r["location"]), (r["code"],) if r["code"] else (), r["doe"],
        _number(r["dcr"]), dcr_text=r["dcr"], why=r["reason"], water_body_code=r["water_body_code"],
        revisable=r["revisable"] == "1", legal_ref=f"{RM_LEGAL}, point {r['id']}",
        source_url=f"{RM_PDF}#page={r['pdf_page']}") for r in rows]


BASINS = {b.slug: b for b in (
    Basin(BASIN, "le tableau C3", VALID_FROM, LEGAL_REF, DATASET_URL,
          lambda http: parse_table(fetch_table(http))),
    Basin(LB, "le tableau des points nodaux", "2022-03-18", LB_LEGAL, LB_PDF,
          lambda http: loire_bretagne(read_transcription(LB))),
    Basin(RM, "le tableau 7C", "2022-03-21", RM_LEGAL, RM_PDF,
          lambda http: rhone_mediterranee(read_transcription(RM))),
)}


def build_basin(basin: Basin, http=None, today: date | None = None) -> tuple[list[dict], list[dict], list[str]]:
    http = http or session()
    points = basin.load(http)
    codes = sorted({c for p in points for c in p.codes})
    return build(points, published_sites(codes, today or date.today(), http), hubeau.sites(codes, http), basin)
