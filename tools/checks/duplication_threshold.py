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

RACINE = Path(__file__).resolve().parents[2]
HELPERS = RACINE / "TA-thehive-cortex" / "package" / "bin" / "ta_thehive_cortex"

#: (fichier A, fichier B, plafond EXIGÉ, cible VISÉE)
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
PAIRES = [
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


def normaliser(chemin: Path) -> list[str]:
    texte = chemin.read_text(encoding="utf-8")
    for motif, remplacement in _SUBSTITUTIONS:
        texte = re.sub(motif, remplacement, texte)
    return [l.rstrip() for l in texte.splitlines() if l.strip()]


def lignes_communes(a: Path, b: Path) -> int:
    ga, gb = normaliser(a), normaliser(b)
    apparieur = difflib.SequenceMatcher(None, ga, gb, autojunk=False)
    return sum(bloc.size for bloc in apparieur.get_matching_blocks())


def main() -> int:
    echecs = []
    for nom_a, nom_b, plafond, cible in PAIRES:
        a, b = HELPERS / nom_a, HELPERS / nom_b
        for chemin in (a, b):
            if not chemin.is_file():
                print(f"  {chemin.name}: absent -- the ceiling guards nothing")
                return 1

        communes = lignes_communes(a, b)
        marque = "ok " if communes <= plafond else "NON"
        ecart = f", {communes - cible} above the {cible} target" if communes > cible else ""
        print(f"  {marque} {nom_a} ↔ {nom_b}: {communes} common lines "
              f"(ceiling {plafond}{ecart})")

        if communes > plafond:
            echecs.append(
                f"{nom_a} and {nom_b} share {communes} lines, ceiling is {plafond}"
            )
        elif communes < plafond - 15:
            # ⚠️ Same reasoning as a coverage floor: a ceiling left far above
            # reality stops guarding. Lowering it is a deliberate act.
            echecs.append(
                f"{nom_a} and {nom_b} are down to {communes} lines: lower the "
                f"ceiling from {plafond}, or it no longer catches a regrowth"
            )

    for e in echecs:
        print(f"  {e}")
    if echecs:
        print()
        print("Duplication is invisible in a diff review; only a measurement sees it.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
