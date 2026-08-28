#!/usr/bin/env python3
"""Cyclomatic complexity ceilings, per function, as a ratchet.

⚠️ **A ceiling that is not a ratchet is a wish.** `parse_events` reached CC 126
-- 540 lines, nine sub-responsibilities, five branches with no `else` and three
silent losses -- one `elif` at a time, each of them reasonable on the day it was
written. Nobody added complexity; everybody added a field type.

So the ceilings below are MEASURED values, not aspirations. Lowering one is a
deliberate act. Raising one requires editing this file, which is the point: the
next `elif` has to argue for itself in a diff.

    python tools/checks/complexity_ceiling.py            # enforce
    python tools/checks/complexity_ceiling.py --report   # print every function

Exit 0 when every function is at or under its ceiling, 1 otherwise.

⚠️ No third-party dependency on purpose. `radon` is not installed on the build
machines, and a check that only runs where a tool happens to be present is a
check that reports green by being absent -- the exact failure this repository
keeps finding elsewhere.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / "TA-thehive-cortex" / "package" / "bin"

#: The ceiling that applies when a function is not named below.
DEFAULT_CEILING = 15

#: Measured ceilings. `<path>:<function>` -> max CC.
#: ⚠️ Every entry here is a debt with a number on it, not a permission.
CEILINGS: dict[str, int] = {
    "backfill_alerts_cases.py:BACKFILL_ALERTS_CASES.stream_events": 45,
    "thehive.py:TheHive4Splunk.get_cases_events": 41,
    "thehive_alerts_cases.py:THEHIVE_ALERTS_CASES.stream_events": 40,
    "ta_thehive_cortex/modalert_thehive_add_observables_helper.py:process_event": 35,
    "common.py:Settings.__init__": 28,
    "thehive.py:TheHive4Splunk.get_alerts_events": 28,
    "ta_thehive_cortex/cim_actions.py:ModularAction.result2stash": 26,
    "thehive.py:TheHive4Splunk.get_case_timeline_events": 25,
    "backfill_observables.py:BACKFILL_OBSERVABLES.stream_events": 24,
    "ta_thehive_cortex/cim_actions.py:ModularAction.message": 21,
    "cortex_search_jobs.py:collect_job": 20,
    "thehive.py:TheHive4Splunk.get_audit_logs_events": 19,
    "ta_logging.py:setup_logging": 18,
    "thehive.py:TheHive4Splunk.get_observables_events": 18,
    "thehive.py:TheHive4Splunk.get_tasks_events": 18,
    "thehive_observables.py:THEHIVE_OBSERVABLES.stream_events": 17,
    "ta_thehive_cortex/modalert_thehive_common.py:create_datatype_lookup": 16,
}


def complexity(node: ast.AST) -> int:
    """McCabe complexity: one, plus one per decision point.

    Counted: if/elif, for, while, `and`/`or` (each extra operand), except
    handlers, comprehension conditions, ternaries, `assert`, and `match` cases.
    A nested function is NOT counted here -- it gets its own entry, because a
    ceiling that lumps them together cannot say which one grew.
    """
    total = 1
    for child in ast.walk(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child is not node:
            continue
        if isinstance(child, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.IfExp, ast.Assert)):
            total += 1
        elif isinstance(child, ast.ExceptHandler):
            total += 1
        elif isinstance(child, ast.BoolOp):
            total += len(child.values) - 1
        elif isinstance(child, ast.comprehension):
            total += 1 + len(child.ifs)
        elif hasattr(ast, "match_case") and isinstance(child, ast.match_case):
            total += 1
    return total


def functions(path: Path):
    """Every function of a module, with the dotted name of its owner class."""
    tree = ast.parse(path.read_text(encoding="utf-8"))

    def walk(node, prefix=""):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                yield from walk(child, f"{prefix}{child.name}.")
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                yield f"{prefix}{child.name}", complexity(child), child.lineno
                yield from walk(child, f"{prefix}{child.name}.")

    yield from walk(tree)


def measure():
    results = []
    for path in sorted(BIN.rglob("*.py")):
        if "/libs/" in path.as_posix() or "__pycache__" in path.as_posix():
            continue
        relative = path.relative_to(BIN).as_posix()
        for name, cc, line in functions(path):
            results.append((f"{relative}:{name}", cc, line))
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", action="store_true",
                        help="print every function, worst first, and exit 0")
    args = parser.parse_args()

    results = measure()

    if args.report:
        for key, cc, line in sorted(results, key=lambda r: -r[1])[:40]:
            ceiling = CEILINGS.get(key, DEFAULT_CEILING)
            mark = "  " if cc <= ceiling else "!!"
            print(f"{mark} {cc:4d} (ceiling {ceiling:3d})  {key}:{line}")
        return 0

    findings = []
    for key, cc, line in results:
        ceiling = CEILINGS.get(key, DEFAULT_CEILING)
        if cc > ceiling:
            findings.append(f"  {key}:{line} — CC {cc}, ceiling {ceiling}")

    # ⚠️ A ceiling naming a function that no longer exists is a ceiling that
    # protects nothing, and it hides a rename. Report it rather than ignore it.
    known = {key for key, _, _ in results}
    for key in CEILINGS:
        if key not in known:
            findings.append(f"  {key} — named in CEILINGS but no such function (renamed? deleted?)")

    if findings:
        print("\n".join(findings))
        print()
        print("Complexity does not arrive in one commit. It arrives one `elif` at\n"
              "a time, each reasonable on its own day.")
        return 1

    print(f"{len(results)} function(s), every one at or under its ceiling "
          f"(default {DEFAULT_CEILING}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
