#!/usr/bin/env python3
"""What an alert action DECLARES must be what its code READS.

⚠️ Nothing enforces this. `globalConfig.json` has no `alerts` section — the six
forms are hand-written HTML — so the declaration in `alert_actions.conf`, the
form, and the code are three independent statements about the same parameter.
Every gap below shipped:

* `cortex_instance_id` and `analyzers` were **read by the code and declared
  nowhere**. `analyzers` is marked required in the form: when empty, the code
  reached `cortex.py` and called `.replace()` on `None` — an `AttributeError`
  instead of a message naming the missing field.
* `thehive_run_function` declared `param.title`; the form posts `name` and the
  code reads `name`. The declared parameter did not exist, and the one that
  exists was not declared.

⚠️ And the parameter name does not always sit next to `get_param`. The timeline
action reads its two dates through a local `resolve_date(param_name)` helper,
so the literal is an argument to *that* function. A check scanning only
`get_param("literal")` reported both as dead — a false positive, and the second
time in one session that a value moving from a literal to a parameter silenced
a guard. Indirection through a one-argument helper is followed below.

The two directions are not the same defect:

* **declared, never read** — dead weight, and a promise to the user that the
  field does something.
* **read, never declared** — the dangerous one. Splunk does not pass an
  undeclared parameter, so the code receives `None` for a field the form calls
  required.

    python tools/checks/alert_action_params.py

Exit 0 when both directions agree.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "TA-thehive-cortex" / "package"
CONF = PACKAGE / "default" / "alert_actions.conf"
HELPERS = PACKAGE / "bin" / "ta_thehive_cortex"

#: GLOBAL settings, read by `get_global_setting` or from the configuration, not
#: passed as `param.*`. Declaring them would be wrong.
NOT_IN_FORM = {
    "splunk_sanitize_backslashes", "splunk_es_alerts_index",
}

#: Provided by Splunk to every action, never declared by the add-on.
PROVIDED_BY_SPLUNK = {"search_name", "sid", "results_file", "results_link"}


def declared_params() -> dict[str, set[str]]:
    """Stanza -> declared parameters."""
    by_stanza: dict[str, set[str]] = {}
    stanza = None
    for line in CONF.read_text(encoding="utf-8").splitlines():
        bare = line.strip()
        if bare.startswith("[") and bare.endswith("]"):
            stanza = bare[1:-1]
            by_stanza[stanza] = set()
        elif stanza and bare.startswith("param.") and "=" in bare:
            name = bare.split("=", 1)[0].strip()[len("param."):]
            if not name.startswith("_"):
                by_stanza[stanza].add(name)
    return by_stanza


def read_params(stanza: str) -> set[str] | None:
    """Parameters actually read by this action's helper."""
    helper = HELPERS / f"modalert_{stanza}_helper.py"
    if not helper.is_file():
        return None
    sources = [helper.read_text(encoding="utf-8")]
    # The shared code also reads parameters on the action's behalf.
    for shared in ("modalert_args.py",):
        path = HELPERS / shared
        if path.is_file() and shared.replace(".py", "") in sources[0]:
            sources.append(path.read_text(encoding="utf-8"))

    names = set()
    for source in sources:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue

        # Local functions that forward their argument to get_param:
        # `def resolve_date(param_name): … helper.get_param(param_name) …`
        relays = _relay_functions(tree)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            callee = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
            if callee == "get_param" and node.args:
                if isinstance(node.args[0], ast.Constant):
                    names.add(node.args[0].value)
            elif callee in relays and node.args:
                position = relays[callee]
                if position < len(node.args) and isinstance(node.args[position], ast.Constant):
                    names.add(node.args[position].value)
    return names


def _relay_functions(tree) -> dict[str, int]:
    """Name -> position of the argument forwarded to `get_param`.

    ⚠️ Without this, a parameter read through a one-line sleight of hand looks
    dead. The parameter name does not always sit right next to `get_param`.
    """
    relays: dict[str, int] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        arguments = [a.arg for a in node.args.args]
        for inner in ast.walk(node):
            if not isinstance(inner, ast.Call) or not inner.args:
                continue
            callee = getattr(inner.func, "attr", None)
            first = inner.args[0]
            if callee == "get_param" and isinstance(first, ast.Name):
                if first.id in arguments:
                    relays[node.name] = arguments.index(first.id)
    return relays


def main() -> int:
    if not CONF.is_file():
        print(f"not found: {CONF}", file=sys.stderr)
        return 1

    findings = []
    for stanza, declaration in sorted(declared_params().items()):
        read = read_params(stanza)
        if read is None:
            continue  # no dedicated helper: nothing to compare

        for name in sorted(read - declaration - PROVIDED_BY_SPLUNK - NOT_IN_FORM):
            findings.append(
                f"[{stanza}] reads `{name}` and declares it nowhere. Splunk does "
                f"not pass an undeclared parameter, so the code gets None — for "
                f"a field the form may well call required"
            )
        for name in sorted(declaration - read - NOT_IN_FORM):
            findings.append(
                f"[{stanza}] declares `param.{name}` and nothing reads it. The "
                f"user is shown a field that does nothing"
            )

    for c in findings:
        print(f"  {c}")
    if findings:
        print()
        print("The declaration, the form and the code are three independent")
        print("statements about the same parameter, and nothing else compares them.")
        return 1

    print("every alert action declares what it reads, and reads what it declares.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
