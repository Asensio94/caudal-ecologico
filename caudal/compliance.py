"""Compare daily flows with the minimum ecological flow that applies each day.

Everything here is pure: no network, no files. Sources and storage feed it series and
requirements; the page and the alerts read what it returns. That keeps the one part
that decides "below the minimum" small enough to test exhaustively.

Vocabulary on purpose: a day is *below the minimum*, never "a breach". Whether a
shortfall is an infringement is a legal judgement (drought exemptions, measurement
error, who controls the release) that a bot does not make.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum

SECONDS_PER_DAY = 86_400
M3_PER_HM3 = 1_000_000


class Status(str, Enum):
    OK = "ok"
    BELOW = "below"          # daily mean under the applicable minimum
    NO_DATA = "no_data"      # missing day, or too few readings to trust its mean
    NO_RULE = "no_rule"      # no requirement in force that day (e.g. before valid_from)


class Regime(str, Enum):
    ORDINARY = "ordinary"
    DROUGHT = "drought"      # prolonged-drought minimum, where the plan allows it


@dataclass(frozen=True)
class Requirement:
    """The minimum flow at one control point, as the hydrological plan sets it.

    `monthly_min` holds 12 values (January first) in m³/s. Plans that give one annual
    value repeat it twelve times. 0 is a legal value: months of "cese", when an
    intermittent river may run dry. None is a month the plan leaves blank, so no rule
    applies. `drought_min` is the relaxed regime for prolonged drought; None when the
    plan sets none or forbids relaxing it (Natura 2000 and Ramsar sites keep the
    ordinary minimum).
    """
    station_id: str
    monthly_min: tuple[float | None, ...]
    drought_min: tuple[float | None, ...] | None = None
    valid_from: date = date(2023, 1, 1)
    valid_to: date | None = None
    protected_area: bool = False
    source_url: str = ""

    def __post_init__(self):
        for name in ("monthly_min", "drought_min"):
            values = getattr(self, name)
            if values is not None and len(values) != 12:
                raise ValueError(f"{self.station_id}: {name} needs 12 monthly values, got {len(values)}")

    def in_force(self, day: date) -> bool:
        return self.valid_from <= day and (self.valid_to is None or day <= self.valid_to)

    def minimum(self, day: date, drought: bool) -> tuple[float | None, Regime]:
        """The minimum that applies on `day` and which regime it comes from."""
        if drought and self.drought_min is not None and not self.protected_area:
            return self.drought_min[day.month - 1], Regime.DROUGHT
        return self.monthly_min[day.month - 1], Regime.ORDINARY


def pick_requirement(reqs: list[Requirement], day: date) -> Requirement | None:
    """The requirement in force on `day`. Phased plans (Tajo) chain several by date."""
    live = [r for r in reqs if r.in_force(day)]
    return max(live, key=lambda r: r.valid_from) if live else None


@dataclass(frozen=True)
class DayResult:
    day: date
    flow: float | None        # daily mean, m³/s
    minimum: float | None     # applicable minimum, m³/s
    regime: Regime | None
    status: Status
    provisional: bool = True  # SAIH real-time data until the validated yearbook replaces it

    @property
    def ratio(self) -> float | None:
        """Flow as a fraction of the minimum (0.5 = half of what is required)."""
        if self.flow is None or not self.minimum:
            return None
        return self.flow / self.minimum

    @property
    def deficit_hm3(self) -> float:
        """Water missing that day to reach the minimum, in hm³."""
        if self.status is not Status.BELOW:
            return 0.0
        return (self.minimum - self.flow) * SECONDS_PER_DAY / M3_PER_HM3


def evaluate(
    flows: dict[date, float | None],
    reqs: list[Requirement],
    drought_days: set[date] | None = None,
    validated_days: set[date] | None = None,
    tolerance: float = 0.0,
) -> list[DayResult]:
    """One DayResult per day in `flows`, in date order.

    `tolerance` is a relative margin (0.05 = a day only counts as below when the flow
    is more than 5 % under the minimum). Low flows are where rating curves are least
    accurate, so a strict zero margin would flag measurement noise.
    """
    drought_days = drought_days or set()
    validated_days = validated_days or set()
    out = []
    for day in sorted(flows):
        q = flows[day]
        provisional = day not in validated_days
        req = pick_requirement(reqs, day)
        if req is None:
            out.append(DayResult(day, q, None, None, Status.NO_RULE, provisional))
            continue
        q_min, regime = req.minimum(day, day in drought_days)
        if q_min is None:
            out.append(DayResult(day, q, None, None, Status.NO_RULE, provisional))
            continue
        if q is None:
            status = Status.NO_DATA
        elif q < q_min * (1 - tolerance):
            status = Status.BELOW
        else:
            status = Status.OK
        out.append(DayResult(day, q, q_min, regime, status, provisional))
    return out


@dataclass
class Episode:
    """A run of consecutive days below the minimum.

    Days without data inside a run neither break it nor count towards it: a gauge that
    goes silent for a day in the middle of a dry spell has not shown the river recovered.
    """
    days: list[DayResult] = field(default_factory=list)

    @property
    def start(self) -> date:
        return self.days[0].day

    @property
    def end(self) -> date:
        return self.days[-1].day

    @property
    def length(self) -> int:
        return len(self.days)

    @property
    def deficit_hm3(self) -> float:
        return sum(d.deficit_hm3 for d in self.days)

    @property
    def worst_ratio(self) -> float:
        return min(d.ratio for d in self.days)

    @property
    def provisional(self) -> bool:
        return any(d.provisional for d in self.days)


def episodes(results: list[DayResult], max_gap_days: int = 1) -> list[Episode]:
    """Group BELOW days into episodes, bridging gaps of up to `max_gap_days` without data."""
    found: list[Episode] = []
    current: Episode | None = None
    last_below: date | None = None
    for r in results:
        if r.status is Status.BELOW:
            if current and last_below and (r.day - last_below) <= timedelta(days=max_gap_days + 1):
                current.days.append(r)
            else:
                current = Episode([r])
                found.append(current)
            last_below = r.day
        elif r.status is Status.OK:
            current, last_below = None, None
        # NO_DATA / NO_RULE: keep the run open; the gap check above decides if it bridges.
    return found


def daily_mean(readings: list[tuple[int, float]], expected: int, min_coverage: float = 0.75) -> float | None:
    """Mean flow of one day from its sub-daily readings.

    `readings` are (minute_of_day, m³/s). With fewer than `min_coverage` of the
    `expected` readings the day is left without a value instead of averaging, say,
    three night readings that would miss a release in the afternoon.
    """
    values = [q for _, q in readings if q is not None and q >= 0]
    if expected <= 0 or len(values) < expected * min_coverage:
        return None
    return sum(values) / len(values)
