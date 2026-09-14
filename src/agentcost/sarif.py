"""SARIF 2.1.0 output for agentcost."""
from __future__ import annotations

import json
from typing import Any


def budget_to_sarif(
    budget: dict[str, float],
    actual: dict[str, float],
    tool_name: str = "agentcost",
    tool_version: str = "0.1.0",
) -> dict[str, Any]:
    """Convert budget check results to SARIF 2.1.0 format.

    Args:
        budget: {"daily": 10.0, "weekly": 50.0, "monthly": 200.0}
        actual: {"daily": 12.5, "weekly": 30.0, "monthly": 80.0}
        tool_name: Tool name for SARIF runner
        tool_version: Tool version for SARIF runner

    Returns:
        SARIF 2.1.0 document as dict
    """
    rules = []
    results = []

    for period, threshold in budget.items():
        if threshold is None:
            continue
        rule_id = f"agentcost/budget-{period}"
        rules.append(
            {
                "id": rule_id,
                "name": f"Budget {period}",
                "shortDescription": {
                    "text": f"Cost exceeds {period} budget threshold",
                },
                "fullDescription": {
                    "text": f"Total cost in the last {period} period exceeds the configured budget limit.",
                },
                "defaultConfiguration": {
                    "level": "error",
                },
            }
        )

        current = actual.get(period, 0.0)
        if current > threshold:
            results.append(
                {
                    "ruleId": rule_id,
                    "level": "error",
                    "message": {
                        "text": (
                            f"{period.capitalize()} budget exceeded: "
                            f"${current:.4f} / ${threshold:.2f} "
                            f"(over by ${current - threshold:.4f})"
                        ),
                    },
                    "locations": [
                        {
                            "physicalLocation": {
                                "artifactLocation": {
                                    "uri": "agentcost-budget",
                                },
                            },
                        },
                    ],
                    "properties": {
                        "period": period,
                        "threshold": threshold,
                        "actual": current,
                    },
                }
            )

    return {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": tool_name,
                        "version": tool_version,
                        "informationUri": "https://github.com/yunaremaia/agentcost",
                        "rules": rules,
                    },
                },
                "results": results,
            }
        ],
    }


def sarif_to_string(sarif_doc: dict[str, Any]) -> str:
    """Serialize SARIF document to JSON string."""
    return json.dumps(sarif_doc, indent=2)
