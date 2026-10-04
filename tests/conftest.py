"""Shared pytest configuration.

Pins the console width for the whole session.

Sixteen tests across six modules assert on `rich`-rendered output, and `rich`
sizes itself from ``COLUMNS``. A shell that exports a narrow value -- or no
value at all -- therefore changes what those assertions see: at 80 columns the
common default, a long absolute path is hard-wrapped mid-filename because a
path has no spaces to break on, and at 0 columns `rich` emits nothing at all.
Both outcomes are failures of the console's layout, not of the code under
test, so the suite depended on how the run happened to be invoked.

Setting the variable once here, at collection time, makes every console
assertion deterministic without touching each test. Tests that care about a
specific width can still override it with their own ``monkeypatch``.
"""

import os

# Applied to the process environment before any test module is imported, so
# every `Console` built during the session resolves the same width.
os.environ["COLUMNS"] = "200"
