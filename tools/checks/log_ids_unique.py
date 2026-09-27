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

        # ⚠️ Les identifiants passés en DONNÉE aux aides partagées.
        for kw in noeud.keywords:
            if kw.arg == "ids" and isinstance(kw.value, ast.Dict):
                for cle, valeur in zip(kw.value.keys, kw.value.values):
                    if isinstance(valeur, ast.Constant) and isinstance(cle, ast.Constant):
                        trouves.append(
                            (noeud.lineno, str(valeur.value), "via helper",
                             f"passed as `{cle.value}` to {_nom_appele(noeud)}")
                        )

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


def _nom_appele(noeud) -> str:
    fonction = noeud.func
    return getattr(fonction, "id", None) or getattr(fonction, "attr", None) or "?"


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


DEBUT = "<!-- INVENTAIRE:DEBUT -->"
FIN = "<!-- INVENTAIRE:FIN -->"

#: Les niveaux dont un code DOIT être interprété à la main.
NIVEAUX_A_EXPLIQUER = {"error", "warn", "warning"}


def construire_registre() -> tuple[str, list[str]]:
    lignes = [
        DEBUT,
        "",
        "# Complete inventory",
        "",
        "> ⚠️ **Generated block — do not edit between the markers.**",
        "> `python tools/checks/log_ids_unique.py --write` rebuilds it.",
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

        # ⚠️ as_posix(): the inventory is committed and compared byte for byte.
        # A Windows run wrote `\` separators, and every Linux run after it
        # then found the inventory stale -- red CI from a docs refresh.
        lignes.append(f"## `{module.relative_to(BIN).as_posix()}`")
        lignes.append("")
        lignes.append("| id | line | level | message |")
        lignes.append("| :--- | ---: | :--- | :--- |")
        for ligne, identifiant, niveau, message in trouves:
            message = message.replace("|", "\\|")
            lignes.append(f"| `{identifiant}` | {ligne} | {niveau} | {message} |")
        lignes.append("")

    lignes.append(f"*{total} call sites.*")
    lignes.append("")
    lignes.append(FIN)
    return "\n".join(lignes) + "\n", constats


def remplacer_inventaire(document: str, inventaire: str) -> str:
    """Substitue le bloc généré, en laissant l'interprétation intacte."""
    i, j = document.index(DEBUT), document.index(FIN) + len(FIN)
    return document[:i] + inventaire.rstrip("\n") + document[j:]


def acronymes(module: Path) -> set[str]:
    """Les préfixes sous lesquels ce module apparaît dans une ligne rendue.

    ⚠️ Un code nu ne désigne rien pour un lecteur : `135` veut dire deux choses
    différentes selon le module. La documentation l'écrit donc préfixé
    (`THCC-135`), et c'est cette forme-là que le contrôle doit accepter.
    """
    import re
    return set(re.findall(r'acronym\s*=\s*["\'](\w+)["\']',
                          module.read_text(encoding="utf-8")))


def codes_a_expliquer() -> list[tuple[str, set[str]]]:
    """(code, formes acceptables) pour tout ce qui signale un problème."""
    besoin = {}
    for module in modules():
        prefixes = acronymes(module)
        for _, identifiant, niveau, _ in sites(module):
            if niveau not in NIVEAUX_A_EXPLIQUER:
                continue
            formes = besoin.setdefault(identifiant, set())
            formes.add(identifiant)
            formes.update(f"{p}-{identifiant}" for p in prefixes)
    return sorted(besoin.items())


def main() -> int:
    inventaire, constats = construire_registre()

    if not REGISTRE.is_file():
        print(f"  {REGISTRE.relative_to(RACINE)} is missing")
        return 1
    document = REGISTRE.read_text(encoding="utf-8")
    if DEBUT not in document or FIN not in document:
        print(f"  {REGISTRE.relative_to(RACINE)} has lost its {DEBUT} markers")
        return 1

    if "--write" in sys.argv:
        REGISTRE.write_text(remplacer_inventaire(document, inventaire), encoding="utf-8")
        print(f"inventory refreshed in {REGISTRE.relative_to(RACINE)}; "
              f"the hand-written part is untouched")
        return 1 if constats else 0

    # ⚠️ L'interprétation est cherchée AVANT les marqueurs seulement : une
    # mention dans l'inventaire généré ne vaut pas une explication.
    redige = document[: document.index(DEBUT)]
    for code, formes in codes_a_expliquer():
        if not any(f"`{f}`" in redige for f in formes):
            attendu = " or ".join(f"`{f}`" for f in sorted(formes))
            constats.append(
                f"{attendu} is logged as an error or a warning but is explained "
                f"nowhere in {REGISTRE.relative_to(RACINE)}: someone will read it "
                f"during an incident with nothing to go on"
            )

    if remplacer_inventaire(document, inventaire) != document:
        constats.append(
            f"the generated inventory of {REGISTRE.relative_to(RACINE)} no longer "
            f"matches the code: run `--write`"
        )

    for c in constats:
        print(f"  {c}")
    if constats:
        print()
        print("An identifier that designates two places designates none, and one")
        print("nobody explained is a code you meet for the first time mid-incident.")
        return 1

    print(f"every identifier designates a single place; "
          f"{len(codes_a_expliquer())} problem code(s) explained; inventory up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
