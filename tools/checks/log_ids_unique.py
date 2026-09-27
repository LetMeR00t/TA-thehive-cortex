#!/usr/bin/env python3
"""Every log identifier must designate exactly one place.

⚠️ An identifier that names two call sites names none -- and it is precisely
what someone reaches for when a production incident has to be traced back to a
line. Measured before this check existed: **15 ambiguous identifiers** across
five modules, including `135` labelling a TTPs success AND an observable
failure in the same file, and `140` labelling a TTPs failure AND the start of
attachment processing.

⚠️ An identifier can also travel as DATA. Since the shared helpers
(`create_with_retry`, `upload_attachment`) take an `ids={...}` mapping, a
literal sitting in that dict is a log identifier too -- and the first version
of this check, which only read `id=` on logger calls, was blind to it. It
missed `125` used both as the `exhausted` id and as a success line in the same
file, a collision shipped in v4.2.2 and carried forward. A guard that scans
call sites misses everything passed as an argument.

Scope, deliberately: a rendered line reads `[serial][<command_id>-<id>]`, and
`command_id` already namespaces the identifier per command. So uniqueness is
required **within a module**, not across the whole add-on. Demanding global
uniqueness would mean renumbering ~340 call sites and breaking every saved
search built on one -- for an ambiguity that does not exist.

    python tools/checks/log_ids_unique.py            # verify
    python tools/checks/log_ids_unique.py --write    # refresh the inventory block

⚠️ `docs/log_ids.md` has TWO parts, and the split is the point:

* everything above the `INVENTAIRE` markers is **written by hand** -- what a
  code means, and for the ones that signal a problem, what to do next. A
  machine cannot write that, and regenerating the file would erase it.
* the block between the markers is **generated** from the source, so the
  inventory itself cannot drift.

And the check closes the gap between the two: **every code the source emits at
error or warning level must have an interpretation in the hand-written part.**
A new code shipped without an explanation turns the build red. The document may
be incomplete -- it cannot quietly stop matching reality, which is the failure
mode of every hand-maintained registry.
"""

from __future__ import annotations

import ast
import collections
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / "TA-thehive-cortex" / "package" / "bin"
REGISTRY = ROOT / "docs" / "log_ids.md"

LEVELS = {"debug", "info", "warn", "warning", "error", "critical"}


def sites(module: Path):
    """Every (id, niveau, message) logged by this module, in source order."""
    try:
        tree = ast.parse(module.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        # ⚠️ Identifiers passed as DATA to the shared helpers.
        for kw in node.keywords:
            if kw.arg == "ids" and isinstance(kw.value, ast.Dict):
                for key, value in zip(kw.value.keys, kw.value.values):
                    if isinstance(value, ast.Constant) and isinstance(key, ast.Constant):
                        found.append(
                            (node.lineno, str(value.value), "via helper",
                             f"passed as `{key.value}` to {_callee_name(node)}")
                        )

        level = getattr(node.func, "attr", None)
        if level not in LEVELS:
            continue
        identifier = message = None
        for kw in node.keywords:
            if kw.arg == "id" and isinstance(kw.value, ast.Constant):
                identifier = str(kw.value.value)
            if kw.arg == "message":
                message = _summary(kw.value)
        if identifier is not None:
            found.append((node.lineno, identifier, level, message or ""))
    return sorted(found)


def _callee_name(node) -> str:
    function = node.func
    return getattr(function, "id", None) or getattr(function, "attr", None) or "?"


def _summary(node) -> str:
    """A readable one-liner for the registry, from whatever expression it is."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        text = node.value
    elif isinstance(node, ast.JoinedStr):
        text = "".join(
            p.value if isinstance(p, ast.Constant) else "{…}" for p in node.values
        )
    elif isinstance(node, ast.BinOp):
        text = _summary(node.left) + " …"
    elif isinstance(node, ast.Call):
        text = _summary(node.func.value) if isinstance(node.func, ast.Attribute) else "…"
    else:
        text = "…"
    text = " ".join(text.split())
    return (text[:77] + "…") if len(text) > 78 else text


def modules():
    for path in sorted(BIN.rglob("*.py")):
        if "libs" in path.parts or "__pycache__" in path.parts:
            continue
        yield path


START = "<!-- INVENTAIRE:DEBUT -->"
END = "<!-- INVENTAIRE:FIN -->"

#: The levels whose code MUST be explained by hand.
LEVELS_TO_EXPLAIN = {"error", "warn", "warning"}


def build_registry() -> tuple[str, list[str]]:
    lines = [
        START,
        "",
        "# Complete inventory",
        "",
        "> ⚠️ **Generated block — do not edit between the markers.**",
        "> `python tools/checks/log_ids_unique.py --write` rebuilds it.",
        "",
    ]
    findings = []
    total = 0

    for module in modules():
        found = sites(module)
        if not found:
            continue
        total += len(found)
        count = collections.Counter(i for _, i, _, _ in found)
        for identifier, n in sorted(count.items()):
            if n > 1:
                where = [str(l) for l, i, _, _ in found if i == identifier]
                findings.append(
                    f"{module.relative_to(ROOT)}: id={identifier} designates "
                    f"{n} places (lines {', '.join(where)}) -- so it designates none"
                )

        # ⚠️ as_posix(): the inventory is committed and compared byte for byte.
        # A Windows run wrote `\` separators, and every Linux run after it
        # then found the inventory stale -- red CI from a docs refresh.
        lines.append(f"## `{module.relative_to(BIN).as_posix()}`")
        lines.append("")
        lines.append("| id | line | level | message |")
        lines.append("| :--- | ---: | :--- | :--- |")
        for line, identifier, level, message in found:
            message = message.replace("|", "\\|")
            lines.append(f"| `{identifier}` | {line} | {level} | {message} |")
        lines.append("")

    lines.append(f"*{total} call sites.*")
    lines.append("")
    lines.append(END)
    return "\n".join(lines) + "\n", findings


def replace_inventory(document: str, inventory: str) -> str:
    """Substitute the generated block, leaving the explanation untouched."""
    i, j = document.index(START), document.index(END) + len(END)
    return document[:i] + inventory.rstrip("\n") + document[j:]


def acronyms(module: Path) -> set[str]:
    """The prefixes under which this module appears in a rendered line.

    ⚠️ A bare code designates nothing to a reader: `135` means two different
    things depending on the module. The documentation therefore writes it prefixed
    (`THCC-135`), and that is the form the check must accept.
    """
    import re
    return set(re.findall(r'acronym\s*=\s*["\'](\w+)["\']',
                          module.read_text(encoding="utf-8")))


def codes_to_explain() -> list[tuple[str, set[str]]]:
    """(code, acceptable forms) for everything that reports a problem."""
    needed = {}
    for module in modules():
        prefixes = acronyms(module)
        for _, identifier, level, _ in sites(module):
            if level not in LEVELS_TO_EXPLAIN:
                continue
            forms = needed.setdefault(identifier, set())
            forms.add(identifier)
            forms.update(f"{p}-{identifier}" for p in prefixes)
    return sorted(needed.items())


def main() -> int:
    inventory, findings = build_registry()

    if not REGISTRY.is_file():
        print(f"  {REGISTRY.relative_to(ROOT)} is missing")
        return 1
    document = REGISTRY.read_text(encoding="utf-8")
    if START not in document or END not in document:
        print(f"  {REGISTRY.relative_to(ROOT)} has lost its {START} markers")
        return 1

    if "--write" in sys.argv:
        REGISTRY.write_text(replace_inventory(document, inventory), encoding="utf-8")
        print(f"inventory refreshed in {REGISTRY.relative_to(ROOT)}; "
              f"the hand-written part is untouched")
        return 1 if findings else 0

    # ⚠️ The explanation is searched for BEFORE the markers only: a
    # mention in the generated inventory is not an explanation.
    written = document[: document.index(START)]
    for code, forms in codes_to_explain():
        if not any(f"`{f}`" in written for f in forms):
            expected = " or ".join(f"`{f}`" for f in sorted(forms))
            findings.append(
                f"{expected} is logged as an error or a warning but is explained "
                f"nowhere in {REGISTRY.relative_to(ROOT)}: someone will read it "
                f"during an incident with nothing to go on"
            )

    if replace_inventory(document, inventory) != document:
        findings.append(
            f"the generated inventory of {REGISTRY.relative_to(ROOT)} no longer "
            f"matches the code: run `--write`"
        )

    for c in findings:
        print(f"  {c}")
    if findings:
        print()
        print("An identifier that designates two places designates none, and one")
        print("nobody explained is a code you meet for the first time mid-incident.")
        return 1

    print(f"every identifier designates a single place; "
          f"{len(codes_to_explain())} problem code(s) explained; inventory up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
