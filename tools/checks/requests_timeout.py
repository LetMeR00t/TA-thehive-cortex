#!/usr/bin/env python3
"""Refuse an HTTP call that can hang forever.

`requests` has **no default timeout**. A call without one waits until the
operating system gives up on the TCP connection, which on Linux is measured in
minutes. Inside Splunk that means a search command or a modular input holding
its worker while the search merely looks slow -- the only proven way this
add-on can block.

Both vendored libraries shipped without a single `timeout=`. They are patched
locally (see `libs/LOCAL_PATCHES.md`), and this check exists so the next
library upgrade cannot quietly undo it -- exactly how the UCC migration once
erased `cortex4py/__init__.py`.

⚠️ **Deliberately narrow, and here is why.** A first version flagged any
`.get()` / `.post()` on anything named `self` or `session`. It reported FIFTY
findings, nearly all of them `dict.get()` and `os.environ.get()`. A guard that
cries wolf gets switched off, and then it protects nothing. So it now checks
two things it can decide with certainty:

  1. module-level `requests.<verb>(...)` -- unambiguous, must carry `timeout=`;
  2. `TheHiveSession` still overrides `request()` -- one method that injects the
     session timeout into EVERY call, so the per-call sites need no annotation.

What it does NOT see: a bare `session.get(...)` on some other session object.
That is the accepted blind spot; widening it is what produced the wolf.

    python tools/checks/requests_timeout.py

Exit code 0 when clean, 1 otherwise.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
SOURCES = RACINE / "TA-thehive-cortex" / "package" / "bin"
SESSION = SOURCES / "ta_thehive_cortex" / "libs" / "thehive4py" / "session.py"

VERBES = {"get", "post", "put", "patch", "delete", "head", "options", "request"}
EXCLUS_REPERTOIRES = {"__pycache__"}


def appels_requests_nus(chemin: Path) -> list[tuple[int, str]]:
    """`requests.<verb>(...)` without `timeout=`. No ambiguity possible here."""
    arbre = ast.parse(chemin.read_text(encoding="utf-8"), filename=str(chemin))
    trouves: list[tuple[int, str]] = []
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.Call):
            continue
        f = noeud.func
        if not (isinstance(f, ast.Attribute) and f.attr in VERBES):
            continue
        if not (isinstance(f.value, ast.Name) and f.value.id == "requests"):
            continue
        mots = {kw.arg for kw in noeud.keywords}
        # `**kwargs` (arg is None) may carry it; not decidable, and flagging it
        # would be a false positive.
        if "timeout" in mots or None in mots:
            continue
        trouves.append((noeud.lineno, f"requests.{f.attr}() without timeout="))
    return trouves


def surcharge_de_session_presente() -> bool:
    """`TheHiveSession.request` must exist and set a default timeout.

    Checking the METHOD rather than its call sites is what keeps this guard
    narrow: one override covers every request the session will ever make,
    including those the add-on does not make today.
    """
    if not SESSION.is_file():
        return False
    arbre = ast.parse(SESSION.read_text(encoding="utf-8"), filename=str(SESSION))
    for classe in ast.walk(arbre):
        if not (isinstance(classe, ast.ClassDef) and classe.name == "TheHiveSession"):
            continue
        for membre in classe.body:
            if isinstance(membre, ast.FunctionDef) and membre.name == "request":
                corps = ast.dump(membre)
                return "timeout" in corps and "setdefault" in corps
    return False


def main() -> int:
    if not SOURCES.is_dir():
        print(f"sources not found: {SOURCES}", file=sys.stderr)
        return 1

    total = 0
    for chemin in sorted(SOURCES.rglob("*.py")):
        if EXCLUS_REPERTOIRES & set(chemin.relative_to(SOURCES).parts):
            continue
        for ligne, quoi in appels_requests_nus(chemin):
            print(f"{chemin.relative_to(RACINE)}:{ligne}: {quoi}")
            total += 1

    if not surcharge_de_session_presente():
        print(f"{SESSION.relative_to(RACINE)}: TheHiveSession no longer overrides "
              "request() with a default timeout — the local patch is gone")
        total += 1

    if total:
        print()
        print(f"{total} finding(s). requests waits for the OS to give up — minutes,")
        print("holding a Splunk worker. Pass timeout=, or restore the session patch.")
        return 1

    print("every module-level requests call is bounded, and the session patch holds.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
