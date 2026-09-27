#!/usr/bin/env python3
"""Refuse a duplication that has grown back.

⚠️ **86 % of common code is invisible in a diff review.** Nobody reads two
files side by side, so the case and the alert helpers drifted into 419 shared
lines out of ~1 050 -- including ~190 lines of attachment handling that used
the SAME log identifiers on both sides, making a production trace ambiguous.

Duplication of that size does not show up in a review. It shows up in a
measurement, which is why this is a check and not a guideline.

The comparison is NORMALISED: `case`/`alert`, `new_case`/`new_alert` and their
plurals are folded onto a neutral name first, so what is counted is structural
sameness rather than vocabulary.

    python tools/checks/duplication_threshold.py

Exit 0 when every pair stays under its ceiling, 1 otherwise.
"""

from __future__ import annotations

import difflib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HELPERS = ROOT / "TA-thehive-cortex" / "package" / "bin" / "ta_thehive_cortex"

#: (file A, file B, REQUIRED ceiling, TARGET aimed at)
#:
#: ⚠️ The ceiling is a RATCHET, like the coverage floors: it sits at today's
#: measurement, so it goes red on a REGROWTH and only on that. Setting it at
#: the ambition would make the check red from birth, and a check that is red
#: from birth gets switched off.
#: ⚠️ Bumped 148 -> 149 by Gitea #32: both helpers now `continue` past a
#: creation response with no `_id`, since everything below that point reads
#: `new_case["_id"]`/`new_alert["_id"]` and would otherwise KeyError. One
#: `continue` line, unavoidable in both, deliberately not chased away by
#: rewording -- see the commit for the measurement.
PAIRS = [
    (
        "modalert_thehive_create_a_new_case_helper.py",
        "modalert_thehive_create_a_new_alert_helper.py",
        149,
        120,
    ),
]

_SUBSTITUTIONS = [
    (r"\bnew_case\b|\bnew_alert\b", "OBJ"),
    (r"\bcases\b|\balerts\b", "OBJS"),
    (r"\bcase\b|\balert\b", "obj"),
    (r"\bCase\b|\bAlert\b", "Obj"),
]


def normalise(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    for pattern, replacement in _SUBSTITUTIONS:
        text = re.sub(pattern, replacement, text)
    return [l.rstrip() for l in text.splitlines() if l.strip()]


def common_lines(a: Path, b: Path) -> int:
    ga, gb = normalise(a), normalise(b)
    matcher = difflib.SequenceMatcher(None, ga, gb, autojunk=False)
    return sum(block.size for block in matcher.get_matching_blocks())


def main() -> int:
    failures = []
    for name_a, name_b, ceiling, target in PAIRS:
        a, b = HELPERS / name_a, HELPERS / name_b
        for path in (a, b):
            if not path.is_file():
                print(f"  {path.name}: absent -- the ceiling guards nothing")
                return 1

        common = common_lines(a, b)
        mark = "ok " if common <= ceiling else "NON"
        gap = f", {common - target} above the {target} target" if common > target else ""
        print(f"  {mark} {name_a} ↔ {name_b}: {common} common lines "
              f"(ceiling {ceiling}{gap})")

        if common > ceiling:
            failures.append(
                f"{name_a} and {name_b} share {common} lines, ceiling is {ceiling}"
            )
        elif common < ceiling - 15:
            # ⚠️ Same reasoning as a coverage floor: a ceiling left far above
            # reality stops guarding. Lowering it is a deliberate act.
            failures.append(
                f"{name_a} and {name_b} are down to {common} lines: lower the "
                f"ceiling from {ceiling}, or it no longer catches a regrowth"
            )

    for e in failures:
        print(f"  {e}")
    if failures:
        print()
        print("Duplication is invisible in a diff review; only a measurement sees it.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
