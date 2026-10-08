from datetime import date, timedelta

import pytest

from caudal.compliance import (
    Regime, Requirement, Status, daily_mean, episodes, evaluate, pick_requirement,
)

FLAT = Requirement("T1", monthly_min=(10.0,) * 12, drought_min=(6.0,) * 12)


def days(start: date, values):
    return {start + timedelta(days=i): v for i, v in enumerate(values)}


def test_requirement_needs_twelve_months():
    with pytest.raises(ValueError):
        Requirement("X", monthly_min=(1.0,) * 11)


def test_monthly_value_follows_the_calendar():
    req = Requirement("T1", monthly_min=tuple(float(m) for m in range(1, 13)))
    assert req.minimum(date(2025, 3, 15), drought=False) == (3.0, Regime.ORDINARY)
    assert req.minimum(date(2025, 12, 1), drought=False) == (12.0, Regime.ORDINARY)


def test_drought_relaxes_only_outside_protected_areas():
    assert FLAT.minimum(date(2025, 7, 1), drought=True) == (6.0, Regime.DROUGHT)
    natura = Requirement("T1", (10.0,) * 12, (6.0,) * 12, protected_area=True)
    assert natura.minimum(date(2025, 7, 1), drought=True) == (10.0, Regime.ORDINARY)


def test_phased_requirements_pick_the_latest_in_force():
    old = Requirement("A", (6.0,) * 12, valid_from=date(2023, 1, 1), valid_to=date(2025, 12, 31))
    new = Requirement("A", (8.0,) * 12, valid_from=date(2026, 1, 1))
    assert pick_requirement([old, new], date(2025, 6, 1)) is old
    assert pick_requirement([old, new], date(2026, 6, 1)) is new
    assert pick_requirement([old, new], date(2022, 6, 1)) is None


def test_evaluate_statuses_and_deficit():
    res = evaluate(days(date(2025, 8, 1), [12.0, 9.0, None, 10.0]), [FLAT])
    assert [r.status for r in res] == [Status.OK, Status.BELOW, Status.NO_DATA, Status.OK]
    # 1 m³/s short for a whole day is 86 400 m³ = 0.0864 hm³.
    assert res[1].deficit_hm3 == pytest.approx(0.0864)
    assert res[1].ratio == pytest.approx(0.9)


def test_tolerance_absorbs_measurement_noise():
    flows = days(date(2025, 8, 1), [9.6])
    assert evaluate(flows, [FLAT])[0].status is Status.BELOW
    assert evaluate(flows, [FLAT], tolerance=0.05)[0].status is Status.OK


def test_drought_days_use_the_drought_minimum():
    flows = days(date(2025, 8, 1), [7.0, 7.0])
    res = evaluate(flows, [FLAT], drought_days={date(2025, 8, 1)})
    assert res[0].status is Status.OK and res[0].regime is Regime.DROUGHT
    assert res[1].status is Status.BELOW and res[1].regime is Regime.ORDINARY


def test_no_rule_before_the_plan():
    req = Requirement("T1", (10.0,) * 12, valid_from=date(2023, 1, 1))
    assert evaluate({date(2022, 12, 31): 1.0}, [req])[0].status is Status.NO_RULE


def test_validated_days_are_not_provisional():
    d = date(2025, 8, 1)
    assert evaluate({d: 5.0}, [FLAT])[0].provisional
    assert not evaluate({d: 5.0}, [FLAT], validated_days={d})[0].provisional


def test_episodes_bridge_one_silent_day_but_not_a_recovery():
    flows = days(date(2025, 8, 1), [8.0, None, 7.0, 11.0, 9.0, 9.0])
    eps = episodes(evaluate(flows, [FLAT]))
    assert [(e.start.day, e.end.day, e.length) for e in eps] == [(1, 3, 2), (5, 6, 2)]
    assert eps[0].worst_ratio == pytest.approx(0.7)
    assert eps[0].deficit_hm3 == pytest.approx((2 + 3) * 0.0864)


def test_episodes_split_on_long_gaps():
    flows = days(date(2025, 8, 1), [8.0, None, None, 8.0])
    assert len(episodes(evaluate(flows, [FLAT]))) == 2


def test_daily_mean_requires_coverage():
    full = [(m, 10.0) for m in range(0, 1440, 60)]          # 24 hourly readings
    assert daily_mean(full, expected=24) == 10.0
    assert daily_mean(full[:17], expected=24) is None        # 71 % < 75 %
    assert daily_mean(full[:18], expected=24) == 10.0
    assert daily_mean([(0, -1.0)] * 24, expected=24) is None  # sentinel negatives dropped


def test_blank_month_has_no_rule_and_cese_accepts_a_dry_river():
    months = [None] + [0.0] + [1.0] * 10          # January blank, February "cese"
    req = Requirement("E", tuple(months))
    res = evaluate({date(2025, 1, 10): 0.0, date(2025, 2, 10): 0.0, date(2025, 3, 10): 0.5}, [req])
    assert [r.status for r in res] == [Status.NO_RULE, Status.OK, Status.BELOW]
