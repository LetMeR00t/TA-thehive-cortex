#!/usr/bin/env python3
"""Every local graft is still in the vendored libraries.

⚠️ **A vendored library carries no sign of what is ours.** An upgrade overwrites
local work in silence, and this repository has already paid for it: the UCC
migration erased `cortex4py/__init__.py`, and nobody noticed for years. Nothing
failed loudly; the package simply stopped being importable the day someone
needed it.

`tools/vendoring/replay_thehive4py.py` rebuilds the fork from upstream plus the
patch series, and it is the right tool for an upgrade. But it needs the runtime
dependencies and a network round-trip to PyPI, so it cannot run in CI here --
and *a guard that only runs where a dependency happens to be installed reports
green by being absent*.

This one reads the SOURCE of what is vendored today. No import, no network, no
dependency. It cannot prove the tree loads; it can prove nothing was silently
dropped, which is the failure that actually happened.

    python tools/checks/vendored_grafts_present.py

Exit 0 when every graft is present, 1 otherwise, naming what disappeared.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIBS = ROOT / "TA-thehive-cortex" / "package" / "bin" / "ta_thehive_cortex" / "libs"

#: thehive4py methods grafted locally: they do not exist upstream, so an
#: upgrade that overwrites the file takes them with it. Kept in step with
#: `tools/vendoring/replay_thehive4py.py`, which checks the same set after a
#: rebuild -- there by import, here by source.
THEHIVE4PY_METHODS = {
    "endpoints/procedure.py": ("ProcedureEndpoint", ["find_list_catalog", "get_catalog"]),
    "endpoints/task.py": ("TaskEndpoint", ["get_tasks", "count_case_tasks", "get_case_tasks"]),
    "endpoints/observable_type.py": ("ObservableTypeEndpoint", ["list"]),
    "endpoints/alert.py": ("AlertEndpoint", [
        "count_observables", "get_alert_observables",
        "count_attachments", "get_alert_attachments",
    ]),
    "endpoints/case.py": ("CaseEndpoint", ["count_pages", "get_case_pages"]),
    "endpoints/function.py": ("FunctionEndpoint", ["run"]),
}

#: Files that exist ONLY here. Upstream has no such file, so there is nothing to
#: diff against and nothing to warn if they vanish.
THEHIVE4PY_OWN_FILES = [
    "endpoints/function.py",
    "types/catalog.py",
    "types/pattern.py",
]

#: cortex4py has NO replay script: upstream is archived, there is no release to
#: rebuild from, and its version is not even determinable (no setup.py, no
#: __version__). Which makes it the more exposed of the two, not the less.
#: ⚠️ PATTERNS, not literal fragments. The first version of this check compared
#: exact strings and fired immediately -- on a graft that was perfectly present,
#: written `kwargs.get('cert',None)` with no space after the comma. A guard that
#: reports a missing graft because someone reformatted a line is worse than no
#: guard: the first false alarm is what teaches people to skip the next one.
CORTEX4PY_FRAGMENTS = {
    "api.py": [
        # Client certificate support, grafted in 1c5ab88 (2021) to fix HTTPS
        # Cortex instances. Upstream passes no `cert` at all.
        (r"self\.__cert\s*=\s*kwargs\.get\(\s*['\"]cert['\"]",
         "the client certificate is read from the constructor"),
        (r"cert\s*=\s*self\.__cert",
         "the client certificate is passed to the request"),
    ],
}

#: The file the UCC migration deleted. It is listed on its own because its loss
#: is the reason this check exists.
CORTEX4PY_FILES = ["__init__.py"]


def _methods_of(path: Path, class_name: str) -> set[str] | None:
    """Every method name defined on a class, or None if the class is gone."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {
                child.name
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
    return None


def check_thehive4py() -> list[str]:
    findings = []
    base = LIBS / "thehive4py"
    if not base.is_dir():
        return ["  thehive4py is not vendored at all"]

    for relative in THEHIVE4PY_OWN_FILES:
        if not (base / relative).is_file():
            findings.append(
                f"  thehive4py/{relative} is missing — it exists ONLY here, so no "
                f"upstream diff would ever mention it"
            )

    for relative, (class_name, methods) in THEHIVE4PY_METHODS.items():
        path = base / relative
        if not path.is_file():
            findings.append(f"  thehive4py/{relative} is missing")
            continue
        defined = _methods_of(path, class_name)
        if defined is None:
            findings.append(f"  thehive4py/{relative}: class {class_name} is gone")
            continue
        for method in methods:
            if method not in defined:
                findings.append(
                    f"  thehive4py/{relative}: {class_name}.{method} — grafted here, "
                    f"absent upstream, and no longer present"
                )
    return findings


def check_cortex4py() -> list[str]:
    findings = []
    base = LIBS / "cortex4py"
    if not base.is_dir():
        return ["  cortex4py is not vendored at all"]

    for relative in CORTEX4PY_FILES:
        if not (base / relative).is_file():
            findings.append(
                f"  cortex4py/{relative} is missing — this is the exact file the UCC "
                f"migration deleted, unnoticed for years"
            )

    for relative, fragments in CORTEX4PY_FRAGMENTS.items():
        path = base / relative
        if not path.is_file():
            findings.append(f"  cortex4py/{relative} is missing")
            continue
        source = path.read_text(encoding="utf-8")
        for pattern, what in fragments:
            if not re.search(pattern, source):
                findings.append(
                    f"  cortex4py/{relative}: {what} — the graft is gone. Client "
                    f"certificate support for HTTPS Cortex instances came from "
                    f"1c5ab88 and exists nowhere upstream."
                )
    return findings


def main() -> int:
    findings = check_thehive4py() + check_cortex4py()
    if findings:
        print("\n".join(findings))
        print()
        print("A vendored library carries no sign of what is ours. An upgrade\n"
              "overwrites local work in silence -- and silence is what makes it\n"
              "cost years rather than minutes.")
        return 1

    grafted = sum(len(m) for _c, m in THEHIVE4PY_METHODS.values())
    print(f"every local graft is present: {grafted} thehive4py method(s), "
          f"{len(THEHIVE4PY_OWN_FILES)} fork-only file(s), and the cortex4py "
          f"client-certificate support.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
