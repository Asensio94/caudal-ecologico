"""French daily flows from Hub'Eau, the public API of the national hydrometric network.

Hub'Eau serves the daily mean flow (`QmnJ`, in l/s) the producers compute from their own
records, so there is no sub-daily series to average here: each value is taken as given.
Values come with a status, from raw (`Donnée brute`) to validated (`Donnée validée`); only
the last one counts as validated, the rest are shown as provisional.

Station codes: a site has 8 characters (O6194610) and its sensors 10 (O619461001). Asked for
a site, the API returns one row per sensor plus one for the site itself (`code_station`
empty); the site row is the series the producer publishes, and the one kept here.
"""
from __future__ import annotations

import time
from datetime import date

from . import DailyFlow, session

BASE = "https://hubeau.eaufrance.fr/api/v2/hydrometrie/"
SOURCE = "hubeau"
PAGE = 10_000   # the largest page every endpoint accepts (sites: 10 000, obs_elab: 20 000)
CODES_PER_REQUEST = 50   # the API takes a comma-separated list; keep URLs short
RETRIES = 5
REFRESH_DAYS = 31   # values are corrected for weeks after the day: re-read a month each run
VALIDATED = "Donnée validée"


def get(path: str, params: dict, http=None) -> list[dict]:
    """Every row of a Hub'Eau query, following the `next` links. The API answers 503 now and
    then under load; those are retried with a growing pause."""
    http = http or session()
    url, rows = BASE + path, []
    params = {**params, "size": PAGE, "format": "json"}
    while url:
        for attempt in range(RETRIES):
            resp = http.get(url, params=params, timeout=120)
            if resp.status_code not in (429, 500, 502, 503, 504):
                break
            time.sleep(2 ** attempt)
        resp.raise_for_status()
        body = resp.json()
        rows += body.get("data", [])
        url, params = body.get("next"), None   # `next` carries the query and the cursor
    return rows


def daily_rows(codes: list[str], first: date, last: date, http=None) -> list[dict]:
    """Site-level QmnJ rows of the given sites between two dates, both included."""
    out = []
    for i in range(0, len(codes), CODES_PER_REQUEST):
        rows = get("obs_elab", {"code_entite": ",".join(codes[i:i + CODES_PER_REQUEST]), "grandeur_hydro_elab": "QmnJ",
                                "date_debut_obs_elab": first.isoformat(), "date_fin_obs_elab": last.isoformat()}, http)
        out += [r for r in rows if r.get("code_station") is None]
    return out


def to_flows(rows: list[dict]) -> dict[str, list[DailyFlow]]:
    """Hub'Eau rows → daily flows per site, in m³/s. A missing value is a day without data."""
    out: dict[str, dict[date, DailyFlow]] = {}
    for r in rows:
        v = r.get("resultat_obs_elab")
        day = date.fromisoformat(r["date_obs_elab"][:10])
        out.setdefault(r["code_site"], {})[day] = DailyFlow(
            day, None if v is None else v / 1000, int(v is not None), 1, SOURCE, r.get("libelle_statut") or "")
    return {site: [days[d] for d in sorted(days)] for site, days in out.items()}


def fetch_range(codes: list[str], first: date, last: date, http=None) -> dict[str, list[DailyFlow]]:
    return to_flows(daily_rows(codes, first, last, http))


def sites(codes: list[str], http=None) -> dict[str, dict]:
    """Name, river, municipality (INSEE code) and position of each site. Free-text comments are
    not kept: some name the people who took the readings."""
    out = {}
    for i in range(0, len(codes), CODES_PER_REQUEST):
        for r in get("referentiel/sites", {"code_site": ",".join(codes[i:i + CODES_PER_REQUEST])}, http):
            out[r["code_site"]] = {
                "name": r["libelle_site"], "river": r.get("libelle_cours_eau") or "",
                "insee": (r.get("code_commune_site") or [""])[0], "department": (r.get("code_departement") or [""])[0],
                "lon": r["longitude_site"], "lat": r["latitude_site"], "catchment_km2": r.get("surface_bv")}
    return out
