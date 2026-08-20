#!/usr/bin/env python3
"""A setting read from the configuration and then thrown away.

⚠️ This is invisible to a reading, and that is the whole problem. The setting
exists on the configuration page, the code has a getter for it, the getter is
called — everything looks wired. What is missing is the last hop: **nobody
consumes the value**. The user changes the setting, saves, and nothing happens.

Two shipped instances:

* `thehive_ttp_catalog_name` — exposed in the Settings page, read by
  `common.py`, placed into the `defaults` dictionary by `thehive.py`, and read
  from there by **nothing**. Meanwhile the MITRE `patternId` of a TTP was never
  validated, for want of a catalogue to check it against. The setting that was
  doing nothing existed precisely for the check that was missing.
* `splunk_es_alerts_index` — read through `get_global_setting`, written into
  the alert arguments, never read again. One configuration round-trip per
  instance and per execution, for nothing.

The rule checked here is the narrow, decidable one: **every key placed into a
`defaults` dictionary must be read as `defaults["KEY"]` somewhere.** That
dictionary is the add-on's own hand-off between "I read the configuration" and
"I use it", so a key that enters and never leaves is a value dropped on the
floor.

    python tools/checks/settings_are_used.py

Exit 0 when every setting handed over is picked up.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
BIN = RACINE / "TA-thehive-cortex" / "package" / "bin"

DOSSIERS_IGNORES = {"libs", "__pycache__", "modinput_wrapper"}


def modules():
    for chemin in sorted(BIN.rglob("*.py")):
        if any(p in DOSSIERS_IGNORES for p in chemin.parts):
            continue
        yield chemin


def cles_deposees() -> dict[str, tuple[Path, int]]:
    """Les clés écrites dans un littéral `defaults = { … }`."""
    deposees: dict[str, tuple[Path, int]] = {}
    for chemin in modules():
        try:
            arbre = ast.parse(chemin.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.Assign):
                continue
            cibles = [c.id for c in noeud.targets if isinstance(c, ast.Name)]
            if "defaults" not in cibles or not isinstance(noeud.value, ast.Dict):
                continue
            for cle in noeud.value.keys:
                if isinstance(cle, ast.Constant) and isinstance(cle.value, str):
                    deposees.setdefault(cle.value, (chemin, noeud.lineno))
    return deposees


def cles_relues() -> set[str]:
    """Les clés lues, quelle que soit la variable qui porte le dictionnaire.

    ⚠️ Volontairement large : `defaults["X"]`, `conf["X"]`, `.get("X")`. Le but
    est de repérer une valeur que PERSONNE ne consomme, pas d'auditer par quel
    nom elle voyage. Trop étroit, le contrôle inventerait des morts.
    """
    lues = set()
    motif = re.compile(r'(?:\[|\.get\()\s*["\']([A-Z][A-Z0-9_]+)["\']')
    for chemin in modules():
        texte = chemin.read_text(encoding="utf-8")
        # On retire les littéraux de dépôt, sinon une clé se lit elle-même.
        sans_depot = re.sub(r"defaults\s*=\s*\{.*?\}", "", texte, flags=re.S)
        lues.update(motif.findall(sans_depot))
    return lues


def main() -> int:
    deposees = cles_deposees()
    if not deposees:
        print("no `defaults` dictionary found: this check guards nothing")
        return 1

    lues = cles_relues()
    constats = []
    for cle, (chemin, ligne) in sorted(deposees.items()):
        if cle not in lues:
            constats.append(
                f"{chemin.relative_to(RACINE)}:{ligne} puts {cle!r} into "
                f"`defaults`, and nothing ever reads it. The setting behind it "
                f"has no effect: a user can change it, save, and see nothing "
                f"happen"
            )

    for c in constats:
        print(f"  {c}")
    if constats:
        print()
        print("A setting read and dropped looks wired from every angle: the page")
        print("shows it, the getter exists, the getter is called. Only the last")
        print("hop is missing, and only a check can see that.")
        return 1

    print(f"{len(deposees)} setting(s) handed over, all of them consumed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
