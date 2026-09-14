"""Tests for agentcost SARIF output."""
import json
from pathlib import Path
from agentcost.sarif import budget_to_sarif, sarif_to_string


def test_sarif_no_violations():
    """SARIF with no violations returns empty results."""
    budget = {"daily": 10.0, "weekly": 50.0, "monthly": 200.0}
    actual = {"daily": 5.0, "weekly": 20.0, "monthly": 80.0}
    doc = budget_to_sarif(budget, actual)
    assert doc["version"] == "2.1.0"
    assert len(doc["runs"][0]["results"]) == 0
    assert len(doc["runs"][0]["tool"]["driver"]["rules"]) == 3


def test_sarif_with_violations():
    """SARIF with violations returns error results."""
    budget = {"daily": 10.0, "weekly": 50.0}
    actual = {"daily": 15.0, "weekly": 30.0}
    doc = budget_to_sarif(budget, actual)
    results = doc["runs"][0]["results"]
    assert len(results) == 1
    assert results[0]["ruleId"] == "agentcost/budget-daily"
    assert results[0]["level"] == "error"
    assert "$15.0000 / $10.00" in results[0]["message"]["text"]


def test_sarif_partial_config():
    """SARIF handles partial config (only some thresholds set)."""
    budget = {"monthly": 200.0}
    actual = {"monthly": 250.0}
    doc = budget_to_sarif(budget, actual)
    rules = doc["runs"][0]["tool"]["driver"]["rules"]
    assert len(rules) == 1
    assert rules[0]["id"] == "agentcost/budget-monthly"
    results = doc["runs"][0]["results"]
    assert len(results) == 1


def test_sarif_serialization():
    """SARIF document serializes to valid JSON."""
    budget = {"daily": 10.0}
    actual = {"daily": 15.0}
    doc = budget_to_sarif(budget, actual)
    output = sarif_to_string(doc)
    parsed = json.loads(output)
    assert parsed["version"] == "2.1.0"
