#!/usr/bin/env python3
"""Every log file the add-on writes must be matched by a props.conf stanza.

⚠️ **The defect lives in the gap between two files, so neither can shout on its
own.** `ta_logging.py` renamed the log files in v4.0.0; `props.conf` still
enumerated the v3.x names. Both files were internally valid. The search
commands silently lost their sourcetype for three minor versions, and the
symptom was *misleading*: the four `*_modalert` stanzas kept matching, so the
file looked alive and only some searches were broken.

Two naming schemes coexist, and the check models BOTH:

* `ta_logging.setup_logging(name)`  -> ``TA-thehive-cortex_<name>.log``
* `solnlib` `Logs().get_logger(n)`  -> ``<n>.log`` (no namespace is set here),
  and alert actions pass ``<alert>_modalert``

    python tools/checks/log_sourcetype_covered.py

Exit 0 when every produced name is covered, 1 otherwise, naming the file and
the stanza that should have covered it.

⚠️ The check also fails when the *shape* of a name stops matching the model
above. A guard that keeps validating an obsolete pattern is worse than none:
it reports a coverage that no longer means anything.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
PAQUET = RACINE / "TA-thehive-cortex" / "package"
BIN = PAQUET / "bin"
DEFAULT = PAQUET / "default"

REPERTOIRE_JOURNAL = "/opt/splunk/var/log/splunk/"
SOURCETYPE = "tathehivecortex:log"


# --------------------------------------------------------------------------
# 1. What names does the code actually produce?
# --------------------------------------------------------------------------

def modele_ta_logging() -> str:
    """Read the file-name template out of ta_logging.py, instead of assuming it.

    Returns the prefix, e.g. ``TA-thehive-cortex_``. Raises when the source no
    longer builds the name the way this check believes.
    """
    source = (BIN / "ta_logging.py").read_text(encoding="utf-8")
    arbre = ast.parse(source)
    ta_name = None
    gabarit_vu = False
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Assign) and len(noeud.targets) == 1:
            cible = noeud.targets[0]
            if not isinstance(cible, ast.Name):
                continue
            if cible.id == "ta_name" and isinstance(noeud.value, ast.Constant):
                ta_name = noeud.value.value
            if cible.id == "LOGGING_FILE_NAME":
                # ta_name + "_" + name + ".log" -- we only need the constants.
                # ⚠️ ast.walk is breadth-first, so the constants come out in
                # tree order, not source order. Compare the SET.
                constantes = {
                    n.value for n in ast.walk(noeud.value)
                    if isinstance(n, ast.Constant) and isinstance(n.value, str)
                }
                if constantes == {"_", ".log"}:
                    gabarit_vu = True
    if ta_name is None or not gabarit_vu:
        raise SystemExit(
            "ta_logging.py no longer builds the log file name as "
            '`ta_name + "_" + name + ".log"`. This check models a shape that '
            "no longer exists -- update it before trusting its verdict."
        )
    return f"{ta_name}_"


def noms_de_commandes() -> set[str]:
    """Every literal name handed to setup_logging, directly or via logger_name."""
    noms: set[str] = set()
    for fichier in sorted(BIN.rglob("*.py")):
        try:
            arbre = ast.parse(fichier.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for noeud in ast.walk(arbre):
            # setup_logging("thehive_audit")
            if isinstance(noeud, ast.Call):
                fonction = noeud.func
                nom = getattr(fonction, "id", None) or getattr(fonction, "attr", None)
                if nom == "setup_logging" and noeud.args:
                    if isinstance(noeud.args[0], ast.Constant):
                        noms.add(noeud.args[0].value)
                # initialize_thehive_instances(..., logger_name="thehive_get_case")
                for kw in noeud.keywords:
                    if kw.arg == "logger_name" and isinstance(kw.value, ast.Constant):
                        noms.add(kw.value.value)
            # def initialize_...(..., logger_name="script") -- the default is a
            # real file the day a caller forgets the argument.
            if isinstance(noeud, ast.FunctionDef):
                for arg, defaut in zip(
                    noeud.args.args[-len(noeud.args.defaults):] if noeud.args.defaults else [],
                    noeud.args.defaults,
                ):
                    if arg.arg == "logger_name" and isinstance(defaut, ast.Constant):
                        noms.add(defaut.value)
    return noms


def noms_d_alert_actions() -> set[str]:
    """Alert actions log through solnlib, under `<alert>_modalert`."""
    base = (BIN / "ta_thehive_cortex" / "alert_actions_base.py").read_text(encoding="utf-8")
    if '_logger_name = alert_name + "_modalert"' not in base:
        raise SystemExit(
            "alert_actions_base.py no longer names its logger "
            '`alert_name + "_modalert"`. Update this check before trusting it.'
        )
    conf = (DEFAULT / "alert_actions.conf").read_text(encoding="utf-8")
    return {f"{nom}_modalert" for nom in re.findall(r"^\[([^\]]+)\]", conf, re.M)}


def verifier_absence_de_namespace() -> str | None:
    """solnlib prefixes the file ONLY when a namespace is set via set_context.

    Proven on solnlib's source: `Logs._get_log_file` returns `<name>.log` when
    `_default_namespace` is None. If the add-on ever calls `set_context`, the
    alert action files gain a prefix and the stanzas below stop matching --
    exactly the v4.0.0 defect, in the other direction.
    """
    for fichier in BIN.rglob("*.py"):
        if "set_context" in fichier.read_text(encoding="utf-8"):
            return (
                f"{fichier.relative_to(RACINE)} calls solnlib's set_context: the "
                "alert action log files are now namespaced, so their props.conf "
                "stanzas need the prefix too."
            )
    return None


# --------------------------------------------------------------------------
# 2. What does props.conf cover?
# --------------------------------------------------------------------------

def motifs_de_source() -> list[tuple[str, re.Pattern[str]]]:
    """Translate Splunk `[source::...]` stanzas into regexes.

    Splunk's rules: `...` matches anything including path separators, `*`
    matches anything except a path separator.
    """
    texte = (DEFAULT / "props.conf").read_text(encoding="utf-8")
    motifs = []
    stanza = None
    for ligne in texte.splitlines():
        nu = ligne.strip()
        if nu.startswith("[") and nu.endswith("]"):
            stanza = nu[1:-1]
            continue
        if not stanza or not stanza.startswith("source::"):
            continue
        if nu.replace(" ", "").lower() == f"sourcetype={SOURCETYPE}":
            motif = stanza[len("source::"):]
            regex = ""
            i = 0
            while i < len(motif):
                if motif.startswith("...", i):
                    regex += ".*"
                    i += 3
                elif motif[i] == "*":
                    regex += r"[^/\\]*"
                    i += 1
                else:
                    regex += re.escape(motif[i])
                    i += 1
            motifs.append((stanza, re.compile(f"^{regex}$")))
    return motifs


def sourcetype_defini() -> bool:
    """The sourcetype was assigned everywhere and defined nowhere until v4.2.3."""
    texte = (DEFAULT / "props.conf").read_text(encoding="utf-8")
    return any(l.strip() == f"[{SOURCETYPE}]" for l in texte.splitlines())


# --------------------------------------------------------------------------

def main() -> int:
    if not PAQUET.is_dir():
        print(f"package not found: {PAQUET}", file=sys.stderr)
        return 1

    prefixe = modele_ta_logging()
    attendus = {f"{prefixe}{n}.log" for n in noms_de_commandes()}
    attendus |= {f"{n}.log" for n in noms_d_alert_actions()}

    motifs = motifs_de_source()
    if not motifs:
        print(f"props.conf assigns {SOURCETYPE} from no [source::] stanza at all.")
        return 1

    constats = []
    derive = verifier_absence_de_namespace()
    if derive:
        constats.append(derive)

    for fichier in sorted(attendus):
        chemin = REPERTOIRE_JOURNAL + fichier
        if not any(rx.match(chemin) for _, rx in motifs):
            constats.append(
                f"{fichier} is written by the add-on, but no [source::] stanza "
                f"of props.conf assigns it {SOURCETYPE}. Splunk will auto-learn "
                f"a sourcetype from the file name instead."
            )

    if not sourcetype_defini():
        constats.append(
            f"[{SOURCETYPE}] is assigned by {len(motifs)} stanza(s) and defined "
            f"by none: line breaking and timestamping fall back to Splunk's "
            f"defaults on a format that starts with an ISO date."
        )

    for c in constats:
        print(f"  {c}")

    if constats:
        print()
        print("Both files are individually valid; the break is between them.")
        return 1

    print(f"{len(attendus)} log file name(s) produced, all covered by "
          f"{len(motifs)} stanza(s); [{SOURCETYPE}] is defined.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
