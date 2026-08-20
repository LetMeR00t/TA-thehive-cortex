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

RACINE = Path(__file__).resolve().parents[2]
PAQUET = RACINE / "TA-thehive-cortex" / "package"
CONF = PAQUET / "default" / "alert_actions.conf"
HELPERS = PAQUET / "bin" / "ta_thehive_cortex"

#: Réglages GLOBAUX, lus par `get_global_setting` ou par la configuration, pas
#: passés en `param.*`. Les déclarer serait faux.
HORS_FORMULAIRE = {
    "splunk_sanitize_backslashes", "splunk_es_alerts_index",
}

#: Fournis par Splunk à toute action, jamais déclarés par l'add-on.
FOURNIS_PAR_SPLUNK = {"search_name", "sid", "results_file", "results_link"}


def declares() -> dict[str, set[str]]:
    """Stanza -> paramètres déclarés."""
    par_stanza: dict[str, set[str]] = {}
    stanza = None
    for ligne in CONF.read_text(encoding="utf-8").splitlines():
        nu = ligne.strip()
        if nu.startswith("[") and nu.endswith("]"):
            stanza = nu[1:-1]
            par_stanza[stanza] = set()
        elif stanza and nu.startswith("param.") and "=" in nu:
            nom = nu.split("=", 1)[0].strip()[len("param."):]
            if not nom.startswith("_"):
                par_stanza[stanza].add(nom)
    return par_stanza


def lus(stanza: str) -> set[str] | None:
    """Paramètres réellement lus par le helper de cette action."""
    helper = HELPERS / f"modalert_{stanza}_helper.py"
    if not helper.is_file():
        return None
    sources = [helper.read_text(encoding="utf-8")]
    # Le code commun lit lui aussi des paramètres pour le compte de l'action.
    for commun in ("modalert_args.py",):
        chemin = HELPERS / commun
        if chemin.is_file() and commun.replace(".py", "") in sources[0]:
            sources.append(chemin.read_text(encoding="utf-8"))

    noms = set()
    for source in sources:
        try:
            arbre = ast.parse(source)
        except SyntaxError:
            continue

        # Les fonctions locales qui transmettent leur argument à get_param :
        # `def resolve_date(param_name): … helper.get_param(param_name) …`
        relais = _fonctions_relais(arbre)

        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.Call):
                continue
            appele = getattr(noeud.func, "attr", None) or getattr(noeud.func, "id", None)
            if appele == "get_param" and noeud.args:
                if isinstance(noeud.args[0], ast.Constant):
                    noms.add(noeud.args[0].value)
            elif appele in relais and noeud.args:
                position = relais[appele]
                if position < len(noeud.args) and isinstance(noeud.args[position], ast.Constant):
                    noms.add(noeud.args[position].value)
    return noms


def _fonctions_relais(arbre) -> dict[str, int]:
    """Nom -> position de l'argument transmis à `get_param`.

    ⚠️ Sans ça, un paramètre lu par un tour de passe-passe d'une ligne passe
    pour mort. Le nom du paramètre n'est pas toujours collé à `get_param`.
    """
    relais: dict[str, int] = {}
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        arguments = [a.arg for a in noeud.args.args]
        for interne in ast.walk(noeud):
            if not isinstance(interne, ast.Call) or not interne.args:
                continue
            appele = getattr(interne.func, "attr", None)
            premier = interne.args[0]
            if appele == "get_param" and isinstance(premier, ast.Name):
                if premier.id in arguments:
                    relais[noeud.name] = arguments.index(premier.id)
    return relais


def main() -> int:
    if not CONF.is_file():
        print(f"not found: {CONF}", file=sys.stderr)
        return 1

    constats = []
    for stanza, declaration in sorted(declares().items()):
        lecture = lus(stanza)
        if lecture is None:
            continue  # pas d'aide dédiée : rien à comparer

        for nom in sorted(lecture - declaration - FOURNIS_PAR_SPLUNK - HORS_FORMULAIRE):
            constats.append(
                f"[{stanza}] reads `{nom}` and declares it nowhere. Splunk does "
                f"not pass an undeclared parameter, so the code gets None — for "
                f"a field the form may well call required"
            )
        for nom in sorted(declaration - lecture - HORS_FORMULAIRE):
            constats.append(
                f"[{stanza}] declares `param.{nom}` and nothing reads it. The "
                f"user is shown a field that does nothing"
            )

    for c in constats:
        print(f"  {c}")
    if constats:
        print()
        print("The declaration, the form and the code are three independent")
        print("statements about the same parameter, and nothing else compares them.")
        return 1

    print("every alert action declares what it reads, and reads what it declares.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
