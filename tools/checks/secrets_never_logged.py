#!/usr/bin/env python3
"""A log line may say whether a credential is THERE. Never anything else.

⚠️ This add-on shipped a debug line carrying the last four characters of the API
key **in four versions**, into a file Splunk indexes and any account with access
to the internal index can read -- and that travels verbatim into a `splunk diag`,
the one file people send to a third party. It was then reduced to the key's
LENGTH, which looks harmless and is not: a length identifies *which* key is in
play across logs, tickets and screenshots.

Every derived value is a correlation channel: length, prefix, suffix,
fingerprint, hash. So the rule enforced here is narrow on purpose:

    the ONLY reduction allowed in a log message is a boolean of presence --
    `bool(x)`, or a comparison with None.

Anything else -- interpolating it, slicing it, measuring it, hashing it -- is a
finding. Mentioning the WORD is fine: this reads expressions, not prose, so
"initialized with an API Key" is not a match.

    python tools/checks/secrets_never_logged.py

Exit 0 when no log message derives anything from a credential, 1 otherwise.

A deliberate exception is declared ON THE LINE, with its reason:

    logger_file.debug(id="X", message=f"...")  # credential-free: <why>

⚠️ Never a list of exemptions kept somewhere else. An allow-list far from the
code is read by nobody and outlives the reason it was written for.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / "TA-thehive-cortex" / "package" / "bin"

#: Identifiers that name, or plainly hold, a credential.
SENSITIVE_NAME = re.compile(
    r"(secret|password|passwd|pwd|apikey|api_key|token|passphrase|credential"
    # HTTP headers carry the credential itself (`Authorization: Bearer <key>`
    # or Basic `user:password`); logging them is logging the secret (TH46).
    r"|headers|authorization)",
    re.IGNORECASE,
)

#: The calls that reach a log file. `log_*` comes from the generated alert
#: action base, the bare levels from this add-on's own wrapper.
LOG_METHODS = {
    "debug", "info", "warn", "warning", "error", "critical", "exception",
    "log_debug", "log_info", "log_warning", "log_error", "log_critical",
}

MARKER = "credential-free"


def _is_log_call(node: ast.Call) -> bool:
    return isinstance(node.func, ast.Attribute) and node.func.attr in LOG_METHODS


def _sensitive_uses(node: ast.AST):
    """Every identifier under `node` that names a credential."""
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and SENSITIVE_NAME.search(child.id):
            yield child, child.id
        elif isinstance(child, ast.Attribute) and SENSITIVE_NAME.search(child.attr):
            yield child, child.attr


def _presence_only(node: ast.AST) -> set[int]:
    """Nodes whose value is only ever reduced to "is it there".

    `bool(x)` and `x is None` / `x is not None` say presence and nothing more.
    Everything else -- len(), a slice, str(), an f-string field -- carries part
    of the value out with it.
    """
    safe = set()
    for child in ast.walk(node):
        if (
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Name)
            and child.func.id == "bool"
        ):
            for argument in child.args:
                safe.update(id(n) for n in ast.walk(argument))
        elif isinstance(child, ast.Compare) and all(
            isinstance(op, (ast.Is, ast.IsNot)) for op in child.ops
        ):
            safe.update(id(n) for n in ast.walk(child.left))
            for comparator in child.comparators:
                safe.update(id(n) for n in ast.walk(comparator))
    return safe


def modules():
    for path in sorted(BIN.rglob("*.py")):
        if "/libs/" in path.as_posix() or "__pycache__" in path.as_posix():
            continue
        yield path


def main() -> int:
    findings = set()
    for path in modules():
        source = path.read_text(encoding="utf-8")
        lines = source.splitlines()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and _is_log_call(node)):
                continue
            # ⚠️ The marker is looked for across the WHOLE call, not just the
            # line the identifier sits on. A message long enough to be a finding
            # is long enough to be wrapped, and a reader writes the reason on
            # its own line above -- refusing that would push people to write no
            # reason at all, which is the failure this exemption exists to
            # prevent.
            span = "\n".join(lines[node.lineno - 1 : (node.end_lineno or node.lineno)])
            if MARKER in span:
                continue

            arguments = list(node.args) + [kw.value for kw in node.keywords]
            for argument in arguments:
                safe = _presence_only(argument)
                for used, name in _sensitive_uses(argument):
                    if id(used) in safe:
                        continue
                    findings.add(
                        f"  {path.relative_to(BIN).as_posix()}:{used.lineno} — a log "
                        f"message derives something from '{name}'"
                    )

    if findings:
        for finding in sorted(findings):
            print(finding)
        print()
        print("A log may say whether a credential is THERE. Its length, its\n"
              "ending, its fingerprint -- each of those says WHICH one, across\n"
              "every log, ticket and screenshot it ever reaches.")
        return 1

    print("no log message derives anything from a credential.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
