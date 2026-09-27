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

ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / "TA-thehive-cortex" / "package" / "bin"

IGNORED_DIRS = {"libs", "__pycache__", "modinput_wrapper"}


def modules():
    for path in sorted(BIN.rglob("*.py")):
        if any(p in IGNORED_DIRS for p in path.parts):
            continue
        yield path


def stored_keys() -> dict[str, tuple[Path, int]]:
    """The keys written in a `defaults = { … }` literal."""
    stored: dict[str, tuple[Path, int]] = {}
    for path in modules():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            targets = [c.id for c in node.targets if isinstance(c, ast.Name)]
            if "defaults" not in targets or not isinstance(node.value, ast.Dict):
                continue
            for key in node.value.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    stored.setdefault(key.value, (path, node.lineno))
    return stored


def read_keys() -> set[str]:
    """The keys read, whatever variable carries the dictionary.

    ⚠️ Deliberately broad: `defaults["X"]`, `conf["X"]`, `.get("X")`. The aim
    is to spot a value that NOBODY consumes, not to audit under which
    name it travels. Too narrow, and the check would invent dead values.
    """
    read = set()
    pattern = re.compile(r'(?:\[|\.get\()\s*["\']([A-Z][A-Z0-9_]+)["\']')
    for path in modules():
        text = path.read_text(encoding="utf-8")
        # The storing literals are removed, otherwise a key reads itself.
        without_store = re.sub(r"defaults\s*=\s*\{.*?\}", "", text, flags=re.S)
        read.update(pattern.findall(without_store))
    return read


def main() -> int:
    stored = stored_keys()
    if not stored:
        print("no `defaults` dictionary found: this check guards nothing")
        return 1

    read = read_keys()
    findings = []
    for key, (path, line) in sorted(stored.items()):
        if key not in read:
            findings.append(
                f"{path.relative_to(ROOT)}:{line} puts {key!r} into "
                f"`defaults`, and nothing ever reads it. The setting behind it "
                f"has no effect: a user can change it, save, and see nothing "
                f"happen"
            )

    for c in findings:
        print(f"  {c}")
    if findings:
        print()
        print("A setting read and dropped looks wired from every angle: the page")
        print("shows it, the getter exists, the getter is called. Only the last")
        print("hop is missing, and only a check can see that.")
        return 1

    print(f"{len(stored)} setting(s) handed over, all of them consumed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
