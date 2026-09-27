#!/usr/bin/env python3
"""Every test module passes ALONE, and the suite passes in REVERSED order.

⚠️ `unittest discover` walks modules alphabetically in one process, so a
module can lean on what an earlier one left behind -- a folder pushed onto
`sys.path`, a mock parked in `sys.modules` -- and stay green for as long as
nobody runs it on its own. Measured: `test_thehive_status_unit` and
`test_thehive_tasks_unit` imported `thehive` only because an earlier module had
put `bin/ta_thehive_cortex` on the path; after `timeline_events.py` moved there,
both were red alone and green in the suite, for weeks.

Discovery order is one order among many. This runs each module in a fresh
interpreter, then all of them in one process in the opposite order, and checks
that the number of tests run alone equals the number run together -- a module
that fails to import runs zero tests, which is not a pass.

    python tools/checks/tests_run_alone.py

It needs the same runtime dependencies as the suite itself
(`package/lib/requirements.txt`). Exit 0 when every module stands on its own.
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / "tests"


def run_alone(module: str) -> tuple[bool, int]:
    """Run one module in a fresh interpreter. Returns (passed, tests run)."""
    result = subprocess.run(
        [sys.executable, "-m", "unittest", module],
        cwd=TESTS, capture_output=True, text=True, encoding="utf-8",
        errors="replace", env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
    )
    ran = [line for line in result.stderr.splitlines() if line.startswith("Ran ")]
    return result.returncode == 0, int(ran[-1].split()[1]) if ran else 0


def run_reversed(modules: list[str]) -> unittest.TestResult:
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(TESTS))
    os.chdir(TESTS)
    loader = unittest.defaultTestLoader
    suite = unittest.TestSuite(loader.loadTestsFromName(m) for m in reversed(modules))
    with open(os.devnull, "w") as sink:
        return unittest.TextTestRunner(stream=sink).run(suite)


def main() -> int:
    modules = sorted(p.stem for p in TESTS.glob("test_*.py"))
    if not modules:
        print(f"no test module found under {TESTS}: nothing was checked.")
        return 1

    failing, alone_total = [], 0
    for module in modules:
        passed, ran = run_alone(module)
        alone_total += ran
        if not passed or ran == 0:
            failing.append(module)
    for module in failing:
        print(f" KO  {module}: red when run on its own")

    result = run_reversed(modules)
    reversed_ok = result.wasSuccessful()
    if not reversed_ok:
        for test, _ in result.failures + result.errors:
            print(f" KO  reversed order: {test.id()}")
    if alone_total != result.testsRun:
        print(f" KO  {alone_total} tests run alone, {result.testsRun} in one process")

    print(f"{len(modules)} modules, {result.testsRun} tests, reversed order included.")
    if failing or not reversed_ok or alone_total != result.testsRun:
        return 1
    print("every test module stands on its own.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
