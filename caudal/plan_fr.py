"""French thresholds: the crisis flow (DCR) of the Adour-Garonne SDAGE, read from its open file.

The SDAGE 2022–2027 of Adour-Garonne (disposition C3) sets, at a network of nodal points,
two flows: the low-water objective (DOE), to be met as a daily mean during the low-water
season eight years out of ten, and the crisis flow (DCR), which "must imperatively be
safeguarded as a daily mean". The DCR is the one compared day by day here; the DOE is shown
alongside as context, since a single day under it is not a failure of the rule.

The agency publishes table C3 as a CSV inside a zip, under the Licence Ouverte. Each point
names a gauge (Code Station Hydro1) and, where that gauge moved or closed, the one that
replaced it (Hydro2); the first that Hub'Eau publishes is read. Run `python -m caudal.cli
plan-fr` to rebuild data/requirements/adour-garonne.csv and the French stations.
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

import requests

from .plan import REQ_FIELDS
from .sources import hubeau, session

COUNTRY = "FR"
BASIN = "adour-garonne"
ZIP_URL = "https://adour-garonne.eaufrance.fr/upload/DATA/SIG/ZONAGES/SDAGE_2022/C3_DOE_DCR_SDAGE2022_.zip"
CSV_NAME = "data/C3_DOE_DCR.csv"
DATASET_URL = "https://www.data.gouv.fr/fr/datasets/aeag-sdage-2022-2027-doe-dcr/"
LEGAL_REF = "SDAGE Adour-Garonne 2022-2027, disposition C3 (tableau C3)"
VALID_FROM = "2022-03-10"   # arrêté of the coordinating prefect approving the SDAGE
REQ_FIELDS_FR = REQ_FIELDS + ["objective"]   # the DOE, as the table writes it
RECENT_DAYS = 60            # a gauge counts as published if Hub'Eau has a daily mean this recent
_SITE = re.compile(r"^[A-Z]\d{7}$")
_PARTIAL = re.compile(r"\[partielle\]|\bbras\b", re.I)   # gauges on one arm of the river


@dataclass(frozen=True)
class NodalPoint:
    basin: str        # sub-basin as the table names it (Garonne, Lot, Charente…)
    river: str
    label: str        # "Séoune à St Pierre de Clairac"
    codes: tuple[str, ...]   # Hydro1, then Hydro2 when different; only well-formed site codes
    doe: str          # as written: "0.2", or "48/52" where the table gives two values
    dcr: float | None


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


def build(points: list[NodalPoint], published: set[str], sites: dict[str, dict]) -> tuple[list[dict], list[dict], list[str]]:
    """Station rows, requirement rows and the points left out, with the reason in French."""
    stations, reqs, unread = [], [], []
    for p in points:
        if p.dcr is None:
            unread.append(f"{p.label} : le tableau C3 ne donne pas de DCR pour ce point")
            continue
        if not p.codes:
            unread.append(f"{p.label} : le tableau C3 ne rattache ce point à aucune station hydrométrique")
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
            "station_id": sid, "basin": BASIN, "source": hubeau.SOURCE, "source_id": code, "name": s["name"],
            "river": _river_name(p.river or s["river"]), "water_body_code": "", "water_body_name": p.label,
            "protected": 0, "roea": "", "lon": f"{s['lon']:.5f}", "lat": f"{s['lat']:.5f}",
            "municipality": s["insee"],
            "note": " ".join(x for x in (
                f"Le SDAGE nomme la station {p.codes[0]}, sans débit récent sur Hub'Eau ; on lit {code}, "
                "la station de remplacement que donne le même tableau." if moved else "",
                "D'après son nom, cette station ne mesure qu'une partie de la rivière (un bras) : un débit "
                "très bas peut ne pas valoir pour tout le cours d'eau." if _PARTIAL.search(s["name"]) else "") if x)})
        base = {"station_id": sid, "water_body_code": "", "water_body_name": p.label, "protected": 0,
                "temporality": "", "valid_from": VALID_FROM, "valid_to": "", "legal_ref": LEGAL_REF,
                "source_url": DATASET_URL, "objective": p.doe}
        reqs.append({**base, "regime": "ordinary", **{f"m{m:02d}": f"{p.dcr:g}" for m in range(1, 13)}})
    return stations, reqs, unread


def published_sites(codes: list[str], today: date, http=None) -> set[str]:
    """Sites with at least one daily mean in the last RECENT_DAYS days."""
    rows = hubeau.daily_rows(codes, today - timedelta(days=RECENT_DAYS), today, http)
    return {r["code_site"] for r in rows if r.get("resultat_obs_elab") is not None}


def build_all(http=None, today: date | None = None) -> tuple[list[dict], list[dict], list[str]]:
    http = http or session()
    points = parse_table(fetch_table(http))
    codes = sorted({c for p in points for c in p.codes})
    return build(points, published_sites(codes, today or date.today(), http), hubeau.sites(codes, http))
