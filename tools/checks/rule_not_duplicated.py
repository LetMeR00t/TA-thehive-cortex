#!/usr/bin/env python3
"""A rule that decides something important must exist in ONE place.

⚠️ A duplicated rule does not stay duplicated: it drifts. And the copy is
usually the one nobody tests, so the drift is invisible until the two
disagree in production.

Measured in this repository: the arbitration deciding *which stored value
becomes the password an account authenticates with* lived inline in
`Instances.__init__` **and** verbatim inside a manual diagnostic script. The
copy asserted nothing, was never collected by the test runner, and printed the
first characters of a real API key to stdout. It looked like a test, so it
bought the rule an appearance of coverage while the rule itself sat at 0 %.

The table below names a literal that belongs to exactly one rule, and the file
allowed to carry it. Note that `tests/test_pick_password_unit.py` is NOT in
that list, and does not need to be: it reads `common.CRED_SEP` instead of
restating the literal. A test that derives its constants from production
cannot drift away from it.

    python tools/checks/rule_not_duplicated.py

Exit 0 when every marker sits where it should, 1 otherwise.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

#: (marker, why it matters, paths allowed to carry it)
MARKERS = [
    (
        "``splunk_cred_sep``",
        "the UCC credential arbitration -- it decides which secret is used",
        {"TA-thehive-cortex/package/bin/common.py"},
    ),
]

#: Directories that are not ours to police.
IGNORED = {".git", "__pycache__", "node_modules", "output", "libs"}


SELF_PATH = Path(__file__).resolve()


def source_files():
    for path in ROOT.rglob("*.py"):
        if any(part in IGNORED for part in path.parts):
            continue
        # ⚠️ The table below spells the marker out, so without this the check
        # reports ITSELF -- a guard tripping on its own declaration is the
        # fastest way to get a guard switched off.
        if path.resolve() == SELF_PATH:
            continue
        yield path


def main() -> int:
    findings = []
    for marker, pattern, allowed in MARKERS:
        carriers = set()
        for path in source_files():
            try:
                if marker in path.read_text(encoding="utf-8"):
                    carriers.add(path.relative_to(ROOT).as_posix())
            except (OSError, UnicodeDecodeError):
                continue

        for extra in sorted(carriers - allowed):
            findings.append(
                f"{extra} carries `{marker}`, which belongs to "
                f"{pattern}. Expected only: {', '.join(sorted(allowed))}."
            )
        for absent in sorted(allowed - carriers):
            # ⚠️ Just as important: if the marker vanishes from the file that
            # OWNS the rule, this check would silently pass forever after.
            findings.append(
                f"{absent} no longer carries `{marker}`: either the rule "
                f"moved, or this check has stopped guarding anything."
            )

    for c in findings:
        print(f"  {c}")
    if findings:
        print()
        print("A rule in two places is a rule that drifts, and the copy is the")
        print("one nobody tests.")
        return 1

    print(f"{len(MARKERS)} rule marker(s), each in its single place.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
