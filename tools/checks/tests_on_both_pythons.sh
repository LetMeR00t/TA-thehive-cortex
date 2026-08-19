#!/usr/bin/env bash
# Run the unit suite on BOTH interpreters Splunk can serve, locally.
#
# ⚠️ Green on one of the two proves nothing about the other, and this add-on
# runs on both: `globalConfig.json` declares
# `supportedPythonVersion: ["3.9","3.13"]` and `commands.conf` ships
# `python.required = 3.9, 3.13`. Splunk <= 10.1 serves 3.9 ONLY, and 10.2 keeps
# 3.9 as its default while offering 3.13 as an opt-in.
#
# The risk is dated, not hypothetical: the vendored thehive4py declares
# `Requires-Python >=3.10`. It runs on 3.9 today -- measured -- but upstream has
# announced it will stop. The day it does, a 3.13-only run stays green and the
# Splunk fleet falls silently.
#
# ⚠️ Portability is the other half. A test written on one machine says nothing
# about the other: `os.geteuid` does not exist on Windows, and a decorator is
# evaluated at IMPORT time, so one inline call made a whole module fail to load
# on the PC while staying green on the pod. The end-to-end campaign runs on the
# PC.
#
# The CI does the same thing in a matrix; this is its local counterpart, so the
# answer is known before pushing rather than after.
#
#     tools/checks/tests_on_both_pythons.sh
#
# Interpreters are looked up in this order: PYTHON39 / PYTHON313 from the
# environment, then `uv python find`, then the PATH. A missing interpreter is
# reported as SKIPPED, never silently ignored -- a version that was not run must
# not look like a version that passed.

set -u

RACINE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
V=$'\033[32m'; R=$'\033[31m'; B=$'\033[1m'; D=$'\033[2m'; Z=$'\033[0m'

trouver() {
	local version="$1" var="$2"
	if [ -n "${!var:-}" ] && [ -x "${!var}" ]; then echo "${!var}"; return; fi
	if command -v uv >/dev/null 2>&1; then
		local p; p="$(uv python find "$version" 2>/dev/null)"
		[ -n "$p" ] && [ -x "$p" ] && { echo "$p"; return; }
	fi
	command -v "python$version" 2>/dev/null || true
}

echo "${B}Suite unitaire sur les deux interpréteurs servis par Splunk${Z}"
echo

total_echecs=0
total_sautes=0

for couple in "3.9:PYTHON39" "3.13:PYTHON313"; do
	version="${couple%%:*}"; var="${couple##*:}"
	interp="$(trouver "$version" "$var")"

	if [ -z "$interp" ]; then
		echo " ${D}SAUTÉ${Z}  Python $version introuvable — posez ${var}=/chemin/vers/python"
		total_sautes=$((total_sautes + 1))
		continue
	fi

	reel="$("$interp" -c 'import sys;print(".".join(map(str,sys.version_info[:3])))' 2>/dev/null)"
	sortie="$(cd "$RACINE" && "$interp" -m unittest discover -s tests -p "test_*.py" 2>&1)"
	code=$?
	resume="$(echo "$sortie" | grep -E '^(Ran|OK|FAILED)' | tr '\n' ' ')"

	if [ "$code" -eq 0 ]; then
		echo " ${V}ok${Z}     Python $reel  $resume"
	else
		echo " ${R}ÉCHEC${Z}  Python $reel  $resume"
		echo "$sortie" | grep -E '^(ERROR|FAIL):' | sed 's/^/          /' | head -10
		total_echecs=$((total_echecs + 1))
	fi
done

echo
if [ "$total_sautes" -eq 2 ]; then
	echo "${R}Aucun interpréteur trouvé : rien n'a été vérifié.${Z}"
	exit 1
fi
if [ "$total_sautes" -gt 0 ]; then
	echo "${D}⚠️ Une version n'a pas été exécutée. Ce n'est pas un succès sur cette version.${Z}"
fi
if [ "$total_echecs" -gt 0 ]; then
	echo "${R}$total_echecs interpréteur(s) en échec.${Z}"
	exit 1
fi
echo "${V}Les deux interpréteurs sont verts.${Z}"
