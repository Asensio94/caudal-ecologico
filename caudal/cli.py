"""Command line: rebuild the plan catalogue, fetch daily flows, render the page."""
from __future__ import annotations

import time
from datetime import date, timedelta

import typer

from . import plan, sources, store
from .config import REFRESH_DAYS
from .sources import cantabrico, guadalquivir, guadiana, hubeau, jucar

app = typer.Typer(add_completion=False, help="Caudal ecológico: daily flows against the legal minimum.")

READERS = {"saih-jucar": jucar.fetch_day, "saih-cantabrico": cantabrico.fetch_day, "sira-guadiana": guadiana.fetch_day}
# Sources that answer a date range in one request; the rest are read day by day.
RANGE_READERS = {"saih-jucar": jucar.fetch_range, "saih-guadalquivir": guadalquivir.fetch_range}
RANGE_CHUNK_DAYS = 31


@app.command("plan")
def build_plan():
    """Parse the minimums from the BOE and rebuild data/stations.csv and data/requirements/."""
    builds = {
        "jucar": lambda: plan.build_jucar(plan.fetch_block(plan.JUCAR_BLOCK), jucar.fetch_gauges()),
        "guadiana": lambda: plan.build_guadiana(plan.fetch_block(plan.GUADIANA_BLOCK), guadiana.fetch_stations()),
        "cantabrico": lambda: plan.build_cantabrico(
            {b: plan.fetch_block(b) for b in plan.CANTABRICO_PLANS}, cantabrico.fetch_gauges(),
            cantabrico.fetch_catchments(), cantabrico.fetch_river_bodies()),
        "guadalquivir": lambda: plan.build_guadalquivir(plan.fetch_block(plan.GUADALQUIVIR_BLOCK), guadalquivir.GAUGES),
    }
    all_stations, excluded = [], []
    for basin, build in builds.items():
        stations, reqs, unread = build()
        plan.write_requirements(basin, reqs)
        all_stations += stations
        excluded += [(basin, u) for u in unread]
        typer.echo(f"{basin}: {len(stations)} control points with public flows; not compared:")
        for u in unread:
            typer.echo(f"  - {u}")
    plan.write_stations(all_stations)
    plan.write_excluded(excluded)


@app.command("plan-fr")
def build_plan_fr():
    """Read the crisis flows (DCR) of each French SDAGE and rebuild the French stations.

    A basin whose table or gauges cannot be read keeps last month's stations and files."""
    from . import plan_fr
    from .sources import session
    http = session()
    stations, excluded, failed = [], [], []
    for slug, basin in plan_fr.BASINS.items():
        try:
            st, reqs, unread = plan_fr.build_basin(basin, http)
        except Exception as e:
            typer.echo(f"{slug}: {type(e).__name__} {e}; keeping last month's thresholds", err=True)
            failed.append(slug)
            stations += [s for s in store.load_stations(plan_fr.COUNTRY) if s["basin"] == slug]
            excluded += [(slug, r["reason"]) for r in store.load_excluded(plan_fr.COUNTRY) if r["basin"] == slug]
            continue
        plan.write_requirements(slug, reqs, plan_fr.REQ_FIELDS_FR)
        stations += st
        excluded += [(slug, u) for u in unread]
        typer.echo(f"{slug}: {len(st)} nodal points with public flows; not compared:")
        for u in unread:
            typer.echo(f"  - {u}")
    plan.write_stations(stations, plan_fr.COUNTRY)
    plan.write_excluded(excluded, plan_fr.COUNTRY)
    if failed:
        raise typer.Exit(1)


@app.command("wfd")
def build_wfd(country: str = "ES"):
    """Status and exemptions of every water body (EEA WISE) and, for Spain, deadlines from the BOE plans."""
    from . import objectives, wfd
    http = sources.session()
    bodies = wfd.build_bodies(wfd.sql(wfd.surface_sql(country), http), wfd.sql(wfd.ground_sql(country), http),
                              wfd.fetch_places(http, country), country)
    exemptions = wfd.fetch_exemptions(http, country)
    wfd.write_csv(wfd.file_name("water_bodies.csv", country), wfd.WB_FIELDS, bodies)
    wfd.write_csv(wfd.file_name("exemptions.csv", country), wfd.EXEMPTION_FIELDS, exemptions)
    typer.echo(f"{country}: {len(bodies)} water bodies, {len(exemptions)} exemption rows; "
               f"{sum(not b['lat'] for b in bodies)} without a point")
    if country != "ES":
        return   # the plan deadlines are read from the BOE: Spain only
    found = []
    for block, read in objectives.READERS.items():
        html = plan.fetch_block(block)
        found += read(html, block)
    rows, unmatched = objectives.rows(found, {b["code"] for b in bodies})
    wfd.write_csv("objectives.csv", objectives.OBJ_FIELDS, rows)
    typer.echo(f"{len(rows)} plan objectives from the BOE; {len(unmatched)} plan codes match no reported body:")
    for u in unmatched:
        typer.echo(f"  - {u}")


@app.command()
def fetch(days: int = REFRESH_DAYS, until: str = "", station: str = "", country: str = "", pause: float = 0.5):
    """Fetch the daily means of the last `days` complete days (yesterday backwards)."""
    last = date.fromisoformat(until) if until else date.today() - timedelta(days=1)
    span = [last - timedelta(days=i) for i in range(days)][::-1]
    stations = [s for s in store.load_stations(country or None) if not station or s["station_id"] == station]
    # Hub'Eau answers many sites and days in one request: read them all at once.
    french = [s for s in stations if s["source"] == hubeau.SOURCE]
    if french:
        # Hub'Eau values keep being corrected for weeks; one request re-reads a whole month.
        first = min(span[0], last - timedelta(days=hubeau.REFRESH_DAYS - 1))
        try:
            got = hubeau.fetch_range([s["source_id"] for s in french], first, last)
        except Exception as e:
            typer.echo(f"hubeau {first}..{last}: {type(e).__name__} {e}", err=True)
            got = {}
        for s in french:
            flows = got.get(s["source_id"], [])
            store.save_flows(s["station_id"], flows)
            typer.echo(f"{s['station_id']}: {sum(g.mean is not None for g in flows)}/{(last - first).days + 1} days")
    for s in stations:
        if s["source"] == hubeau.SOURCE:
            continue
        got = []
        if ranged := RANGE_READERS.get(s["source"]):
            chunks = [span[i:i + RANGE_CHUNK_DAYS] for i in range(0, len(span), RANGE_CHUNK_DAYS)]
            for c in chunks:
                try:
                    got += ranged(s["source_id"], c[0], c[-1])
                except Exception as e:   # one bad gauge must not stop the run
                    typer.echo(f"{s['station_id']} {c[0]}..{c[-1]}: {type(e).__name__} {e}", err=True)
                time.sleep(pause)
        else:
            for d in span:
                try:
                    got.append(READERS[s["source"]](s["source_id"], d))
                except Exception as e:
                    typer.echo(f"{s['station_id']} {d}: {type(e).__name__} {e}", err=True)
                time.sleep(pause)
        store.save_flows(s["station_id"], got)
        typer.echo(f"{s['station_id']}: {sum(g.mean is not None for g in got)}/{len(span)} days")


@app.command()
def restrictions(pause: float = 0.3):
    """Store today's drought restriction level (VigiEau) at each French station."""
    from .sources import vigieau
    http, levels = sources.session(), {}
    for s in store.load_stations("FR"):
        try:
            levels[s["station_id"]] = vigieau.zone_at(float(s["lon"]), float(s["lat"]), http)
        except Exception as e:   # a station without today's level just has a gap
            typer.echo(f"{s['station_id']}: {type(e).__name__} {e}", err=True)
            continue
        time.sleep(pause)
    vigieau.save(date.today(), levels)
    typer.echo(f"{sum(v is not None for v in levels.values())}/{len(levels)} stations under a restriction order")


@app.command()
def context(country: str = typer.Option("", help="Only this country's stations (ES, FR); keeps the rest")):
    """Rebuild data/context.csv: river pressures and aquifer status (EEA) and level trends (CHJ)."""
    from .context import build
    typer.echo(f"{build(typer.echo, country or None)} rows")


@app.command()
def page():
    """Render docs/index.html and france.html, docs/2027.html (with masas-2027.json) and docs/signals.json."""
    from . import countdown, countdown_fr, signals, web, web_fr
    web.render()
    web_fr.render()
    countdown.render()
    countdown_fr.render()
    signals.render()


if __name__ == "__main__":
    app()
