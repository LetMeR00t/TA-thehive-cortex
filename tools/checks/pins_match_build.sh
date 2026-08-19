#!/usr/bin/env bash
# Refuse a requirements.txt that does not describe what the build actually ships.
#
# A package installed but NOT pinned floats: two builds a month apart ship
# different code, and nothing anywhere says so. Measured on 2026-08-19 --
# PySocks, defusedxml and sortedcontainers were shipped without being listed,
# sixteen packages installed against thirteen declared.
#
# It is the direct neighbour of the defect recorded in CONTRIBUTE §7: the bare
# `lib/` rule of the standard Python .gitignore was swallowing
# package/lib/requirements.txt itself, so the build was not reproducible from a
# clone and nothing signalled it. Same family: what ships is decided somewhere
# nobody is looking.
#
# ⚠️ Run it with the interpreter the add-on TARGETS. Resolution depends on the
# Python version: splunk-sdk 3.0.0 requires >=3.13 and requests 2.33 requires
# >=3.10, so a 3.13 run and a 3.9 run do not produce the same closure. 3.9 is
# the floor Splunk defaults to, so 3.9 is what this must be judged against.
#
#     PYTHON=python3.9 tools/checks/pins_match_build.sh
#
# Exit 0 when the two sets are equal, 1 otherwise, naming both directions.

set -u

RACINE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PINS="$RACINE/TA-thehive-cortex/package/lib/requirements.txt"
PYTHON="${PYTHON:-python3}"

if [ ! -f "$PINS" ]; then
	echo "requirements.txt not found: $PINS" >&2
	exit 1
fi

CIBLE="$(mktemp -d)"
trap 'rm -rf "$CIBLE"' EXIT

echo "resolving with $("$PYTHON" -V 2>&1) ..."
if ! "$PYTHON" -m pip install -q -r "$PINS" -t "$CIBLE" 2>"$CIBLE/.err"; then
	echo "install failed:" >&2
	tail -5 "$CIBLE/.err" >&2
	exit 1
fi

"$PYTHON" - "$PINS" "$CIBLE" <<'PY'
import pathlib, sys

pins_path, cible = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])

def normaliser(nom):
    return nom.replace("_", "-").lower()

installe = {
    normaliser(d.name[: -len(".dist-info")].rsplit("-", 1)[0])
    for d in cible.glob("*.dist-info")
}
epingle = {
    normaliser(l.split("==")[0].strip())
    for l in pins_path.read_text(encoding="utf-8").splitlines()
    if "==" in l and not l.lstrip().startswith("#")
}

flottants = sorted(installe - epingle)
fantomes = sorted(epingle - installe)

for nom in flottants:
    print(f"  shipped but not pinned: {nom}  -> its version floats between builds")
for nom in fantomes:
    print(f"  pinned but not shipped: {nom}  -> the pin describes nothing")

if flottants or fantomes:
    print()
    print(f"{len(flottants) + len(fantomes)} discrepancy(ies): what ships is not what is declared.")
    raise SystemExit(1)

print(f"{len(epingle)} packages: pinned set and shipped set are identical.")
PY
