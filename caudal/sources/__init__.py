"""Readers for each basin's SAIH. Each one returns the daily mean flow of a local day.

Every reader fetches the sub-daily series of one Spanish local day and averages it with
`compliance.daily_mean`, instead of trusting a basin's own daily product: the
Cantábrico daily CSV, for one, comes shifted by a day and does not match its own
five-minute data. One rule for all basins keeps the days comparable.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import requests

MADRID = ZoneInfo("Europe/Madrid")
USER_AGENT = "caudal-ecologico/0.1 (+https://github.com/Asensio94/caudal-ecologico)"


@dataclass(frozen=True)
class DailyFlow:
    day: date
    mean: float | None   # m³/s; None when coverage is too low
    readings: int
    expected: int
    source: str


def local_day_bounds_utc(day: date) -> tuple[datetime, datetime]:
    """UTC start (inclusive) and end (exclusive) of a Spanish local day; handles DST days."""
    start = datetime.combine(day, time(0), MADRID)
    end = datetime.combine(day + timedelta(days=1), time(0), MADRID)
    return start.astimezone(ZoneInfo("UTC")), end.astimezone(ZoneInfo("UTC"))


def expected_readings(day: date, step_minutes: int) -> int:
    """Readings in a local day: 288 at 5 min, but 276 or 300 on the DST change days."""
    start, end = local_day_bounds_utc(day)
    return int((end - start).total_seconds() // 60 // step_minutes)


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "es-ES,es;q=0.9"})
    return s
