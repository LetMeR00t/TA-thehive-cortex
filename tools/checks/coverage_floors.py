#!/usr/bin/env python3
"""Enforce coverage floors PER PATH, never a global one.

A global floor over 8,685 lines is either trivially met or unreachable, and it
says nothing either way: a repository can sit at 60 % while the three functions
that decide whether data is lost sit at zero. That was literally the case here
-- instance resolution and credential arbitration were at 0 % while the suite
looked respectable.

So the floors name the paths that hurt when they break, and only those. Adding
a line here is a deliberate act: it means "this code is now load-bearing".

    python tools/checks/coverage_floors.py

Exit 0 when every floor is met, 1 otherwise, naming what fell short.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
BIN = RACINE / "TA-thehive-cortex" / "package" / "bin"

#: (fichier, fonction, plancher EXIGÉ, cible VISÉE) — motivé un par un.
#:
#: ⚠️ The floor is a RATCHET, not an ambition. It sits at or just below what is
#: measured today, so the build goes red on a regression and only on that. A
#: floor set above reality would make CI red from birth, and a guard that is red
#: from birth gets switched off -- after which it guards nothing at all.
#:
#: The target is the ambition, and it is REPORTED, never enforced. Raising the
#: floor towards it is a deliberate act, taken once the tests that justify it
#: exist.
PLANCHERS = [
    # ⚠️ THE FLOOR FOLLOWED THE CODE, AND IT HAD TO. `parse_events` was the
    # heart of the data loss at CC 126; the dispatch that decided what a field
    # IS now lives in `field_mapping`. Left alone, this line would have gone on
    # reporting a comfortable green over a fifteen-line function -- a ratchet
    # measuring the one place the risk had just left. An extraction moves code
    # out of the paths a floor watches, so the moment of extraction is the
    # moment to move the floor with it.
    ("ta_thehive_cortex/modalert_thehive_common.py", "parse_events", 95, 95),
    # Where the branching actually went. Measured after the extraction, so the
    # ratchet starts where reality is.
    ("ta_thehive_cortex/field_mapping.py", "dispatch_row", 90, 100),
    ("ta_thehive_cortex/value_codecs.py", "encode_custom_field", 90, 100),
    # Moved with the code: `build_observables`/`_observables_of` now live in
    # `observable_builder` (field_mapping crossed its own ceiling a second time).
    ("ta_thehive_cortex/observable_builder.py", "build_observables", 90, 100),
    ("ta_thehive_cortex/field_mapping.py", "_extract_ttp", 85, 95),
    ("ta_thehive_cortex/field_mapping.py", "_extract_custom_field", 90, 100),
    ("ta_thehive_cortex/observable_builder.py", "_observables_of", 90, 100),
    # Were at 0 % while calling sys.exit() on an unknown id -- a path that ended
    # the Splunk process and that nothing could reach.
    ("common.py", "getInstanceURL", 90, 90),
    ("common.py", "getInstanceUsernameApiKey", 90, 90),

    # The arbitration of SECRETS. It was at 0 % while existing in two copies,
    # so its floor is the only one set at 100: a pure function with no I/O has
    # no excuse for an unreached branch, and a rule that decides which password
    # authenticates deserves the strictest ratchet in this table.
    ("common.py", "pick_password", 100, 100),
    ("common.py", "account_from_ucc_username", 100, 100),
]


def mesurer() -> int:
    lance = subprocess.run(
        [sys.executable, "-m", "coverage", "run", "--branch",
         "--source", str(BIN),
         "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"],
        cwd=RACINE, capture_output=True, text=True,
    )
    if lance.returncode != 0:
        print("the test suite is not green; coverage is meaningless until it is.")
        print(lance.stderr[-2000:])
        return 1

    import json
    subprocess.run([sys.executable, "-m", "coverage", "json", "-o", "coverage.json"],
                   cwd=RACINE, capture_output=True, text=True)
    rapport = json.loads((RACINE / "coverage.json").read_text(encoding="utf-8"))

    echecs = []
    for fichier, fonction, plancher, cible in PLANCHERS:
        chemin = str(BIN / fichier)
        donnees = None
        for cle, valeur in rapport.get("files", {}).items():
            if Path(cle).resolve() == Path(chemin).resolve():
                donnees = valeur
                break
        if donnees is None:
            echecs.append(f"{fichier}: not measured at all -- the floor guards nothing")
            continue

        bornes = _bornes_de_fonction(Path(chemin), fonction)
        if bornes is None:
            echecs.append(f"{fichier}:{fonction}: function not found -- renamed? the "
                          f"floor must follow it, or it silently stops guarding")
            continue

        debut, fin = bornes
        executees = {n for n in donnees["executed_lines"] if debut <= n <= fin}
        manquantes = {n for n in donnees["missing_lines"] if debut <= n <= fin}
        total = len(executees) + len(manquantes)
        pct = 100 * len(executees) // total if total else 100
        marque = "ok " if pct >= plancher else "LOW"
        ecart = f", {cible - pct} points below the {cible} % target" if pct < cible else ""
        print(f"  {marque} {fichier}:{fonction}  {pct} % (floor {plancher} %{ecart})")
        if pct < plancher:
            echecs.append(f"{fichier}:{fonction} at {pct} %, floor is {plancher} %")

    if echecs:
        print()
        for e in echecs:
            print(f"  {e}")
        return 1
    return 0


def _bornes_de_fonction(chemin: Path, nom: str):
    """First and last line of a function, by AST rather than by grep."""
    import ast
    arbre = ast.parse(chemin.read_text(encoding="utf-8"), filename=str(chemin))
    for noeud in ast.walk(arbre):
        if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)) and noeud.name == nom:
            return noeud.lineno, (noeud.end_lineno or noeud.lineno)
    return None


if __name__ == "__main__":
    raise SystemExit(mesurer())
