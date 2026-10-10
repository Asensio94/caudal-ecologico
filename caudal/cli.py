"""Command line: rebuild the plan catalogue, fetch daily flows, render the page."""
from __future__ import annotations

import time
from datetime import date, timedelta

import typer

from . import plan, store
from .config import REFRESH_DAYS
from .sources import cantabrico, guadiana, jucar

app = typer.Typer(add_completion=False, help="Caudal ecológico: daily flows against the legal minimum.")

READERS = {"saih-jucar": jucar.fetch_day, "saih-cantabrico": cantabrico.fetch_day, "sira-guadiana": guadiana.fetch_day}
# Sources that answer a date range in one request; the rest are read day by day.
RANGE_READERS = {"saih-jucar": jucar.fetch_range}
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
    }
    all_stations = []
    for basin, build in builds.items():
        stations, reqs, unread = build()
        plan.write_requirements(basin, reqs)
        all_stations += stations
        typer.echo(f"{basin}: {len(stations)} control points with public flows; not compared:")
        for u in unread:
            typer.echo(f"  - {u}")
    plan.write_stations(all_stations)


@app.command()
def fetch(days: int = REFRESH_DAYS, until: str = "", station: str = "", pause: float = 0.5):
    """Fetch the daily means of the last `days` complete days (yesterday backwards)."""
    last = date.fromisoformat(until) if until else date.today() - timedelta(days=1)
    span = [last - timedelta(days=i) for i in range(days)][::-1]
    for s in store.load_stations():
        if station and s["station_id"] != station:
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
def page():
    """Render docs/index.html from the stored flows."""
    from .web import render
    render()


if __name__ == "__main__":
    app()
