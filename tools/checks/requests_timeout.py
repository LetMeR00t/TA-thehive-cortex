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

ROOT = Path(__file__).resolve().parents[2]
SOURCES = ROOT / "TA-thehive-cortex" / "package" / "bin"
SESSION = SOURCES / "ta_thehive_cortex" / "libs" / "thehive4py" / "session.py"

VERBS = {"get", "post", "put", "patch", "delete", "head", "options", "request"}
EXCLUDED_DIRS = {"__pycache__"}


def bare_requests_calls(path: Path) -> list[tuple[int, str]]:
    """`requests.<verb>(...)` without `timeout=`. No ambiguity possible here."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if not (isinstance(f, ast.Attribute) and f.attr in VERBS):
            continue
        if not (isinstance(f.value, ast.Name) and f.value.id == "requests"):
            continue
        words = {kw.arg for kw in node.keywords}
        # `**kwargs` (arg is None) may carry it; not decidable, and flagging it
        # would be a false positive.
        if "timeout" in words or None in words:
            continue
        found.append((node.lineno, f"requests.{f.attr}() without timeout="))
    return found


def session_override_present() -> bool:
    """`TheHiveSession.request` must exist and set a default timeout.

    Checking the METHOD rather than its call sites is what keeps this guard
    narrow: one override covers every request the session will ever make,
    including those the add-on does not make today.
    """
    if not SESSION.is_file():
        return False
    tree = ast.parse(SESSION.read_text(encoding="utf-8"), filename=str(SESSION))
    for class_node in ast.walk(tree):
        if not (isinstance(class_node, ast.ClassDef) and class_node.name == "TheHiveSession"):
            continue
        for member in class_node.body:
            if isinstance(member, ast.FunctionDef) and member.name == "request":
                body = ast.dump(member)
                return "timeout" in body and "setdefault" in body
    return False


def main() -> int:
    if not SOURCES.is_dir():
        print(f"sources not found: {SOURCES}", file=sys.stderr)
        return 1

    total = 0
    for path in sorted(SOURCES.rglob("*.py")):
        if EXCLUDED_DIRS & set(path.relative_to(SOURCES).parts):
            continue
        for line, what in bare_requests_calls(path):
            print(f"{path.relative_to(ROOT)}:{line}: {what}")
            total += 1

    if not session_override_present():
        print(f"{SESSION.relative_to(ROOT)}: TheHiveSession no longer overrides "
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
