#!/usr/bin/env python3
"""Rebuild the vendored thehive4py from upstream + the local patch series.

The point is not convenience, it is **detection**. A vendored library carries no
sign of what is ours: an upgrade overwrites local work in silence, and this
repository has already paid for that once -- the UCC migration erased
`cortex4py/__init__.py` and nobody noticed for years.

So this script replays the series against a pristine upstream and refuses to
finish if a graft did not land. A patch that no longer applies is not a
nuisance to be forced through: it means upstream changed the same lines, and
somebody has to look.

    python tools/vendoring/replay_thehive4py.py --check
    python tools/vendoring/replay_thehive4py.py --upstream 2.1.0 --write

`--check` (default) rebuilds in a temporary directory and compares with what is
vendored today: it is the guard, and it needs no network beyond the wheel.
`--write` replaces the vendored tree, for an actual upgrade.

⚠️ Run the test suite on BOTH 3.9 and 3.13 afterwards
(`tools/checks/tests_on_both_pythons.sh`). Upstream declares
`Requires-Python >=3.10` while Splunk serves 3.9 by default: it works today,
upstream does not promise it will.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

V = "\033[32m"
R = "\033[31m"
B = "\033[1m"
D = "\033[2m"
Z = "\033[0m"

RACINE = Path(__file__).resolve().parents[2]
LIBS = RACINE / "TA-thehive-cortex" / "package" / "bin" / "ta_thehive_cortex" / "libs"
VENDORISE = LIBS / "thehive4py"
# ⚠️ OUTSIDE package/. `ucc-gen` copies package/bin verbatim, so a patch series
# left in there ships inside the .spl -- development material delivered to every
# user, and extra surface for AppInspect to chew on.
PATCHES = RACINE / "tools" / "vendoring" / "patches" / "thehive4py"

#: Upstream release the series is written against.
BASE = "2.1.0"

#: Files that exist ONLY here. They are not patches: upstream has no such file,
#: so there is nothing to diff against. `function.py` backs TheHive Functions,
#: which `modalert_thehive_run_function_helper.py` depends on.
PROPRES = ["endpoints/function.py", "types/catalog.py", "types/pattern.py"]

#: Grafted methods that MUST exist once the replay is done. This is the actual
#: safety net: a patch can apply with fuzz, or apply to the wrong place, and
#: still leave the method missing. Checking the RESULT beats checking the
#: process.
INTERPRETEUR = [sys.executable]

ATTENDUS = {
    "endpoints.procedure:ProcedureEndpoint": ["find_list_catalog", "get_catalog"],
    "endpoints.task:TaskEndpoint": ["get_tasks", "count_case_tasks", "get_case_tasks"],
    "endpoints.observable_type:ObservableTypeEndpoint": ["list"],
    "endpoints.alert:AlertEndpoint": [
        "count_observables", "get_alert_observables",
        "count_attachments", "get_alert_attachments",
    ],
    "endpoints.case:CaseEndpoint": ["count_pages", "get_case_pages"],
    "endpoints.function:FunctionEndpoint": ["run"],
}


def _telecharger(version: str, ou: Path) -> Path:
    # ⚠️ --ignore-requires-python: 2.1.0 declares `>=3.10`, so pip on 3.9 --
    # the interpreter this repository builds with -- answers "no matching
    # distribution", and the guard died before replaying anything. The copy
    # is vendored, not installed: Requires-Python does not bind it (decision
    # of 2026-08-19: Python 3.9 is kept), and the test matrix proves 3.9.
    subprocess.run(
        [sys.executable, "-m", "pip", "download", f"thehive4py=={version}",
         "--no-deps", "--ignore-requires-python", "-q", "-d", str(ou)],
        check=True, capture_output=True, text=True,
    )
    roue = next(ou.glob("thehive4py-*.whl"))
    with zipfile.ZipFile(roue) as z:
        z.extractall(ou / "amont")
    return ou / "amont" / "thehive4py"


def _appliquer(arbre: Path) -> list[str]:
    echecs = []
    for patch in sorted(PATCHES.glob("*.patch")):
        rendu = subprocess.run(
            ["git", "apply", "--3way", str(patch)],
            cwd=arbre, capture_output=True, text=True,
        )
        if rendu.returncode != 0:
            rendu = subprocess.run(
                ["git", "apply", str(patch)], cwd=arbre, capture_output=True, text=True
            )
        if rendu.returncode != 0:
            echecs.append(patch.name)
    return echecs


def _verifier_greffes(arbre: Path) -> list[str]:
    """Import the rebuilt tree and check every grafted method is really there."""
    script = "\n".join([
        "import importlib, sys",
        f"sys.path.insert(0, {str(arbre.parent)!r})",
        "manque = []",
        f"for cle, methodes in {ATTENDUS!r}.items():",
        "    module, classe = cle.split(':')",
        "    try:",
        "        m = importlib.import_module('thehive4py.' + module)",
        "    except Exception as e:",
        "        manque.append(cle + ' (import: ' + type(e).__name__ + ': ' + str(e) + ')'); continue",
        "    obj = getattr(m, classe, None)",
        "    if obj is None:",
        "        manque.append(cle + ' (class missing)'); continue",
        "    for meth in methodes:",
        "        if not hasattr(obj, meth):",
        "            manque.append(cle + '.' + meth)",
        "print('\\n'.join(manque))",
    ])
    rendu = subprocess.run([INTERPRETEUR[0], "-c", script], capture_output=True, text=True)
    if rendu.returncode != 0:
        return [f"could not import the rebuilt tree: {rendu.stderr.strip()[:200]}"]
    return [l for l in rendu.stdout.splitlines() if l.strip()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--upstream", default=BASE)
    ap.add_argument("--write", action="store_true")
    # ⚠️ `--check` is the DEFAULT, and it exists as a flag only because the
    # docstring documented it before the parser did: anyone following the
    # instructions got `error: unrecognized arguments: --check`. A tool whose
    # documented invocation fails teaches people not to trust the document.
    ap.add_argument("--check", action="store_true",
                    help="rebuild in a temporary directory and compare (the default)")
    ap.add_argument("--python", default=sys.executable,
                    help="interpreter used to VERIFY the rebuilt tree; it needs "
                         "the runtime dependencies installed")
    args = ap.parse_args()

    # ⚠️ Pre-flight, and it earns its place: without it, an interpreter lacking
    # `requests` reports every graft as LOST. A missing dependency and a lost
    # graft are entirely different problems, and one message for both sends the
    # reader hunting in the wrong place.
    sonde = subprocess.run(
        [args.python, "-c", "import requests, typing_extensions"],
        capture_output=True, text=True,
    )
    if sonde.returncode != 0:
        print(f" {R}cannot VERIFY{Z}: {args.python} lacks the runtime "
              f"dependencies ({sonde.stderr.strip().splitlines()[-1] if sonde.stderr else '?'})")
        print(f"        {D}this is NOT a lost graft -- install "
              f"package/lib/requirements.txt, or pass --python{Z}")
        return 1

    INTERPRETEUR[0] = args.python
    print(f"{B}Replaying thehive4py {args.upstream} + {len(list(PATCHES.glob('*.patch')))} grafts{Z}")

    with tempfile.TemporaryDirectory() as tmp:
        chantier = Path(tmp)
        try:
            amont = _telecharger(args.upstream, chantier)
        except Exception as err:  # noqa: BLE001
            print(f" {R}upstream download failed{Z}: {err}")
            return 1
        print(f" {V}ok{Z}     upstream {args.upstream} fetched")

        echecs = _appliquer(amont)
        if echecs:
            print(f" {R}FAIL{Z}   grafts that did not apply: {', '.join(echecs)}")
            print(f"        {D}upstream changed the same lines -- look at it, do not force it{Z}")
            return 1
        print(f" {V}ok{Z}     graft series applied")

        for propre in PROPRES:
            source = VENDORISE / propre
            if not source.is_file():
                print(f" {R}FAIL{Z}   fork-only file missing: {propre}")
                return 1
            (amont / propre).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, amont / propre)
        print(f" {V}ok{Z}     {len(PROPRES)} fork-only file(s) copied")

        perdues = _verifier_greffes(amont)
        if perdues:
            print(f" {R}FAIL{Z}   grafts lost despite the patches applying:")
            for p in perdues:
                print(f"          {p}")
            return 1
        print(f" {V}ok{Z}     every graft is present at arrival")

        if args.write:
            shutil.rmtree(VENDORISE)
            shutil.copytree(amont, VENDORISE)
            print(f" {V}ok{Z}     vendored tree replaced")
            print(f"{D}        now run tools/checks/tests_on_both_pythons.sh{Z}")
        else:
            print(f"{D}        (--check: the vendored tree was not touched){Z}")

    print(f"\n{V}The replay rebuilds the library without losing a graft.{Z}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
