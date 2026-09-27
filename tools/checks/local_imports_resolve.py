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

ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / "TA-thehive-cortex" / "package" / "bin"

IGNORED_DIRS = {"libs", "__pycache__", "modinput_wrapper"}


def local_module_paths() -> dict[str, Path]:
    """Module name -> path, for everything the package ships itself."""
    found = {}
    for path in BIN.rglob("*.py"):
        if any(p in IGNORED_DIRS for p in path.parts):
            continue
        found.setdefault(path.stem, path)
    return found


def exposed_names(path: Path) -> set[str] | None:
    """What a module defines or re-exports. None if unreadable."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return None
    exposed = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            exposed.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    exposed.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            exposed.add(node.target.id)
        elif isinstance(node, ast.Import):
            exposed.update((al.asname or al.name.split(".")[0]) for al in node.names)
        elif isinstance(node, ast.ImportFrom):
            # ⚠️ A re-export counts: `from x import y` makes `y` reachable
            # as an attribute of the module, and code relies on it.
            exposed.update((al.asname or al.name) for al in node.names)
    return exposed


def main() -> int:
    local = local_module_paths()
    exposed_by_module = {name: exposed_names(path) for name, path in local.items()}

    findings = []
    for module_name, path in sorted(local.items()):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.level:
                continue
            target = (node.module or "").split(".")[0]
            if target not in local or exposed_by_module.get(target) is None:
                continue  # third-party library, or unreadable module
            for al in node.names:
                if al.name == "*":
                    continue
                if al.name not in exposed_by_module[target]:
                    where = ", ".join(
                        m for m, n in exposed_by_module.items() if n and al.name in n
                    ) or "nowhere in the package"
                    findings.append(
                        f"{path.relative_to(ROOT)}:{node.lineno} imports "
                        f"`{al.name}` from `{target}`, which does not define it "
                        f"-- it is defined in: {where}"
                    )

    for c in findings:
        print(f"  {c}")
    if findings:
        print()
        print("An import that names nothing is an ImportError at load time, and")
        print("a test suite only proves the paths it actually runs.")
        return 1

    print(f"every local import across {len(local)} modules resolves.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
