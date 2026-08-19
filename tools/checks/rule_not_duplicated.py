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

RACINE = Path(__file__).resolve().parents[2]

#: (marker, why it matters, paths allowed to carry it)
MARQUEURS = [
    (
        "``splunk_cred_sep``",
        "the UCC credential arbitration -- it decides which secret is used",
        {"TA-thehive-cortex/package/bin/common.py"},
    ),
]

#: Directories that are not ours to police.
IGNORES = {".git", "__pycache__", "node_modules", "output", "libs"}


MOI = Path(__file__).resolve()


def fichiers_source():
    for chemin in RACINE.rglob("*.py"):
        if any(part in IGNORES for part in chemin.parts):
            continue
        # ⚠️ The table below spells the marker out, so without this the check
        # reports ITSELF -- a guard tripping on its own declaration is the
        # fastest way to get a guard switched off.
        if chemin.resolve() == MOI:
            continue
        yield chemin


def main() -> int:
    constats = []
    for marqueur, motif, autorises in MARQUEURS:
        porteurs = set()
        for chemin in fichiers_source():
            try:
                if marqueur in chemin.read_text(encoding="utf-8"):
                    porteurs.add(chemin.relative_to(RACINE).as_posix())
            except (OSError, UnicodeDecodeError):
                continue

        for surnumeraire in sorted(porteurs - autorises):
            constats.append(
                f"{surnumeraire} carries `{marqueur}`, which belongs to "
                f"{motif}. Expected only: {', '.join(sorted(autorises))}."
            )
        for absent in sorted(autorises - porteurs):
            # ⚠️ Just as important: if the marker vanishes from the file that
            # OWNS the rule, this check would silently pass forever after.
            constats.append(
                f"{absent} no longer carries `{marqueur}`: either the rule "
                f"moved, or this check has stopped guarding anything."
            )

    for c in constats:
        print(f"  {c}")
    if constats:
        print()
        print("A rule in two places is a rule that drifts, and the copy is the")
        print("one nobody tests.")
        return 1

    print(f"{len(MARQUEURS)} rule marker(s), each in its single place.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
