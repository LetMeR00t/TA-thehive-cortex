#!/usr/bin/env python3
"""`from <module local> import <nom>` must name something that module defines.

⚠️ Written the day a refactor moved a function and pointed the import at the
wrong module. `modalert_args.py` did
`from modalert_thehive_common import create_thehive_instance`; the function
lives in `thehive`. That is an ImportError on the first useful line of BOTH
creation alert actions -- `thehive_create_a_new_case` and
`thehive_create_a_new_alert` dead on arrival.

**123 tests were green.** Not one of them executed the function that carries
the import, so the suite could not see it. A test proves the paths it runs;
this check proves the paths that merely EXIST, which is the other half.

It is deliberately static: importing these modules for real needs Splunk,
solnlib and a live sys.path, so a check that tried would either be skipped or
mock so much it proved nothing.

    python tools/checks/local_imports_resolve.py

Exit 0 when every local import resolves to a real definition.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
BIN = RACINE / "TA-thehive-cortex" / "package" / "bin"

DOSSIERS_IGNORES = {"libs", "__pycache__", "modinput_wrapper"}


def modules_locaux() -> dict[str, Path]:
    """Nom de module -> chemin, pour tout ce que le paquet livre lui-même."""
    trouves = {}
    for chemin in BIN.rglob("*.py"):
        if any(p in DOSSIERS_IGNORES for p in chemin.parts):
            continue
        trouves.setdefault(chemin.stem, chemin)
    return trouves


def noms_exposes(chemin: Path) -> set[str] | None:
    """Ce qu'un module définit ou ré-exporte. None si illisible."""
    try:
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    except SyntaxError:
        return None
    exposes = set()
    for noeud in arbre.body:
        if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            exposes.add(noeud.name)
        elif isinstance(noeud, ast.Assign):
            for cible in noeud.targets:
                if isinstance(cible, ast.Name):
                    exposes.add(cible.id)
        elif isinstance(noeud, ast.AnnAssign) and isinstance(noeud.target, ast.Name):
            exposes.add(noeud.target.id)
        elif isinstance(noeud, ast.Import):
            exposes.update((al.asname or al.name.split(".")[0]) for al in noeud.names)
        elif isinstance(noeud, ast.ImportFrom):
            # ⚠️ Un ré-export compte : `from x import y` rend `y` accessible
            # comme attribut du module, et du code s'appuie dessus.
            exposes.update((al.asname or al.name) for al in noeud.names)
    return exposes


def main() -> int:
    locaux = modules_locaux()
    expose = {nom: noms_exposes(chemin) for nom, chemin in locaux.items()}

    constats = []
    for nom_module, chemin in sorted(locaux.items()):
        try:
            arbre = ast.parse(chemin.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.ImportFrom) or noeud.level:
                continue
            cible = (noeud.module or "").split(".")[0]
            if cible not in locaux or expose.get(cible) is None:
                continue  # bibliothèque tierce, ou module illisible
            for al in noeud.names:
                if al.name == "*":
                    continue
                if al.name not in expose[cible]:
                    ou = ", ".join(
                        m for m, n in expose.items() if n and al.name in n
                    ) or "nowhere in the package"
                    constats.append(
                        f"{chemin.relative_to(RACINE)}:{noeud.lineno} imports "
                        f"`{al.name}` from `{cible}`, which does not define it "
                        f"-- it is defined in: {ou}"
                    )

    for c in constats:
        print(f"  {c}")
    if constats:
        print()
        print("An import that names nothing is an ImportError at load time, and")
        print("a test suite only proves the paths it actually runs.")
        return 1

    print(f"every local import across {len(locaux)} modules resolves.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
