#!/usr/bin/env python3
"""Every log identifier must designate exactly one place.

⚠️ An identifier that names two call sites names none -- and it is precisely
what someone reaches for when a production incident has to be traced back to a
line. Measured before this check existed: **15 ambiguous identifiers** across
five modules, including `135` labelling a TTPs success AND an observable
failure in the same file, and `140` labelling a TTPs failure AND the start of
attachment processing.

Scope, deliberately: a rendered line reads `[serial][<command_id>-<id>]`, and
`command_id` already namespaces the identifier per command. So uniqueness is
required **within a module**, not across the whole add-on. Demanding global
uniqueness would mean renumbering ~340 call sites and breaking every saved
search built on one -- for an ambiguity that does not exist.

    python tools/checks/log_ids_unique.py            # verify
    python tools/checks/log_ids_unique.py --write    # regenerate the registry

⚠️ The registry is GENERATED, never hand-maintained. A registry written by hand
drifts from the code within a release, and then documents a past state while
looking authoritative.
"""

from __future__ import annotations

import ast
import collections
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
BIN = RACINE / "TA-thehive-cortex" / "package" / "bin"
REGISTRE = RACINE / "docs" / "log_ids.md"

NIVEAUX = {"debug", "info", "warn", "warning", "error", "critical"}


def sites(module: Path):
    """Every (id, niveau, message) logged by this module, in source order."""
    try:
        arbre = ast.parse(module.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    trouves = []
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.Call):
            continue
        niveau = getattr(noeud.func, "attr", None)
        if niveau not in NIVEAUX:
            continue
        identifiant = message = None
        for kw in noeud.keywords:
            if kw.arg == "id" and isinstance(kw.value, ast.Constant):
                identifiant = str(kw.value.value)
            if kw.arg == "message":
                message = _resume(kw.value)
        if identifiant is not None:
            trouves.append((noeud.lineno, identifiant, niveau, message or ""))
    return sorted(trouves)


def _resume(noeud) -> str:
    """A readable one-liner for the registry, from whatever expression it is."""
    if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str):
        texte = noeud.value
    elif isinstance(noeud, ast.JoinedStr):
        texte = "".join(
            p.value if isinstance(p, ast.Constant) else "{…}" for p in noeud.values
        )
    elif isinstance(noeud, ast.BinOp):
        texte = _resume(noeud.left) + " …"
    elif isinstance(noeud, ast.Call):
        texte = _resume(noeud.func.value) if isinstance(noeud.func, ast.Attribute) else "…"
    else:
        texte = "…"
    texte = " ".join(texte.split())
    return (texte[:77] + "…") if len(texte) > 78 else texte


def modules():
    for chemin in sorted(BIN.rglob("*.py")):
        if "libs" in chemin.parts or "__pycache__" in chemin.parts:
            continue
        yield chemin


def construire_registre() -> tuple[str, list[str]]:
    lignes = [
        "# Log identifiers",
        "",
        "> ⚠️ **Generated file — do not edit.**",
        "> `python tools/checks/log_ids_unique.py --write` rebuilds it, and the CI",
        "> fails when it no longer matches the code. A registry maintained by hand",
        "> drifts within a release, and then documents a past state while looking",
        "> authoritative.",
        "",
        "A rendered line reads `[serial][<command_id>-<id>]`. `command_id` namespaces",
        "the identifier per command, so an identifier must be unique **within its",
        "module** -- which is exactly what the check enforces.",
        "",
    ]
    constats = []
    total = 0

    for module in modules():
        trouves = sites(module)
        if not trouves:
            continue
        total += len(trouves)
        compte = collections.Counter(i for _, i, _, _ in trouves)
        for identifiant, n in sorted(compte.items()):
            if n > 1:
                ou = [str(l) for l, i, _, _ in trouves if i == identifiant]
                constats.append(
                    f"{module.relative_to(RACINE)}: id={identifiant} designates "
                    f"{n} places (lines {', '.join(ou)}) -- so it designates none"
                )

        lignes.append(f"## `{module.relative_to(BIN)}`")
        lignes.append("")
        lignes.append("| id | line | level | message |")
        lignes.append("| :--- | ---: | :--- | :--- |")
        for ligne, identifiant, niveau, message in trouves:
            message = message.replace("|", "\\|")
            lignes.append(f"| `{identifiant}` | {ligne} | {niveau} | {message} |")
        lignes.append("")

    lignes.append(f"*{total} call sites.*")
    return "\n".join(lignes) + "\n", constats


def main() -> int:
    contenu, constats = construire_registre()

    if "--write" in sys.argv:
        REGISTRE.parent.mkdir(parents=True, exist_ok=True)
        REGISTRE.write_text(contenu, encoding="utf-8")
        print(f"registry written: {REGISTRE.relative_to(RACINE)}")
        return 1 if constats else 0

    for c in constats:
        print(f"  {c}")

    if not REGISTRE.is_file():
        print(f"  {REGISTRE.relative_to(RACINE)} is missing: run with --write")
        return 1
    if REGISTRE.read_text(encoding="utf-8") != contenu:
        print(f"  {REGISTRE.relative_to(RACINE)} no longer matches the code: "
              f"run `python tools/checks/log_ids_unique.py --write`")
        constats.append("registry stale")

    if constats:
        print()
        print("An identifier that designates two places designates none.")
        return 1

    print("every log identifier designates a single place, registry up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
