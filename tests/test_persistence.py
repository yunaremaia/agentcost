"""Tests for agentcost SQLite persistence layer."""
import sqlite3
import pytest
from datetime import datetime
from pathlib import Path

from agentcost.cost import TokenUsage, CostBreakdown
from agentcost.persistence import CostPersistence


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test_costs.db"


@pytest.fixture
def persistence(db_path):
    return CostPersistence(db_path)


def test_init_creates_tables(db_path):
    persistence = CostPersistence(db_path)
    assert db_path.exists()

    conn = sqlite3.connect(str(db_path))
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    conn.close()
    assert ("token_usage",) in tables


def test_record_single(persistence, db_path):
    usage = TokenUsage(
        model="meituan/longcat-2.0:free",
        input_tokens=1000,
        output_tokens=500,
        session_id="test-session",
        timestamp=datetime(2026, 9, 15, 12, 0, 0),
        agent_id="test-agent",
    )
    persistence.record(usage, estimated_cost=0.01, actual_cost=0.02)

    summary = persistence.get_cost_summary()
    assert summary["total_records"] == 1
    assert summary["total_input_tokens"] == 1000
    assert summary["total_output_tokens"] == 500
    assert summary["total_estimated_cost"] == 0.01
    assert summary["total_actual_cost"] == 0.02


def test_record_many(persistence):
    usages = [
        (TokenUsage(model="m1", input_tokens=100, output_tokens=50, session_id="s1"), 0.001, 0.002),
        (TokenUsage(model="m2", input_tokens=200, output_tokens=90, session_id="s2"), 0.003, 0.004),
    ]
    persistence.record_many(usages)
    summary = persistence.get_cost_summary()
    assert summary["total_records"] == 2
    assert summary["total_estimated_cost"] == 0.004


def test_get_model_breakdown(persistence):
    usages = [
        (TokenUsage(model="m1", input_tokens=100, output_tokens=50), 0.001, 0.002),
        (TokenUsage(model="m1", input_tokens=200, output_tokens=90), 0.003, 0.004),
        (TokenUsage(model="m2", input_tokens=300, output_tokens=130), 0.005, 0.006),
    ]
    persistence.record_many(usages)
    breakdown = persistence.get_model_breakdown()
    assert len(breakdown) == 2
    assert breakdown[0]["model"] in ("m1", "m2")
    assert breakdown[0]["records"] >= 1


def test_get_session_breakdown(persistence):
    usages = [
        (TokenUsage(model="m1", input_tokens=100, output_tokens=50, session_id="s1"), 0.001, 0.002),
        (TokenUsage(model="m1", input_tokens=200, output_tokens=90, session_id="s2"), 0.003, 0.004),
    ]
    persistence.record_many(usages)
    sessions = persistence.get_session_breakdown()
    assert len(sessions) == 2


def test_get_daily_summary(persistence):
    usage = TokenUsage(
        model="m1",
        input_tokens=100,
        output_tokens=50,
        timestamp=datetime(2026, 9, 15, 12, 0, 0),
    )
    persistence.record(usage, estimated_cost=0.001, actual_cost=0.002)
    daily = persistence.get_daily_summary()
    assert len(daily) >= 1
    assert daily[0]["day"] == "2026-09-15"


def test_empty_db_summary(db_path):
    summary = CostPersistence(db_path).get_cost_summary()
    assert summary["total_records"] == 0
    assert summary["total_input_tokens"] == 0


def test_filter_by_session(persistence):
    usages = [
        (TokenUsage(model="m1", input_tokens=100, output_tokens=50, session_id="s1"), 0.001, 0.002),
        (TokenUsage(model="m1", input_tokens=200, output_tokens=90, session_id="s2"), 0.003, 0.004),
    ]
    persistence.record_many(usages)
    s1 = persistence.get_cost_summary(session_id="s1")
    assert s1["total_records"] == 1
    assert s1["total_input_tokens"] == 100
