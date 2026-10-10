import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from click.testing import CliRunner

from agentcost.cli import cli
from agentcost.cost import TokenUsage
from agentcost.forecasting import daily_costs_by_date, fill_daily, forecast

MONDAY = date(2026, 10, 5)


def test_linear_trend():
    costs = [1 + 0.5 * i for i in range(20)]
    result = forecast(costs, MONDAY, 5)
    assert result.points[0].cost == pytest.approx(11.0, abs=1e-6)
    assert result.daily_slope == pytest.approx(0.5)


def test_flat_with_noise_stays_in_range():
    costs = [10 + (-1) ** i for i in range(20)]
    result = forecast(costs, MONDAY, 7)
    for p in result.points:
        assert 8 < p.cost < 12
        assert 0 <= p.low <= p.cost <= p.high


def test_weekend_seasonality():
    # 4 full weeks, +5 on Saturday and Sunday; the forecast starts on a Monday.
    costs = [10 + (5 if (MONDAY.weekday() + i) % 7 >= 5 else 0) for i in range(28)]
    result = forecast(costs, MONDAY, 7)
    assert result.seasonal
    assert result.points[5].cost - result.points[0].cost == pytest.approx(5.0, abs=0.01)


def test_too_little_history():
    with pytest.raises(ValueError):
        forecast([1.0, 2.0], MONDAY, 5)


def test_fill_daily_pads_gaps_with_zero():
    by_day = {MONDAY: 2.0, MONDAY + timedelta(days=2): 3.0}
    assert fill_daily(by_day, MONDAY, MONDAY + timedelta(days=2)) == [2.0, 0.0, 3.0]


def test_daily_costs_skips_missing_timestamps():
    ts = datetime(2026, 10, 5, 12, 0)
    usages = [
        TokenUsage(model="claude-sonnet-4", input_tokens=1_000_000,
                   output_tokens=0, timestamp=ts),
        TokenUsage(model="claude-sonnet-4", input_tokens=1_000_000,
                   output_tokens=0, timestamp=None),
    ]
    totals = daily_costs_by_date(usages)
    assert list(totals) == [ts.date()]
    assert totals[ts.date()] > 0