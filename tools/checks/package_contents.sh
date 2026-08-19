#!/usr/bin/env bash
# Check what the .spl ACTUALLY contains, not what the source tree suggests.
#
# ⚠️ The archive is the only thing that matters, and it is not the folder. The
# difference is where this repository has been bitten: `ucc-gen` copies
# `package/bin` verbatim, so a `__pycache__` left by a local test run ships
# inside the .spl and fails Splunk Cloud vetting -- while `output/` and the
# source tree both look perfectly clean.
#
#     tools/checks/package_contents.sh path/to/TA-thehive-cortex.spl
#
# With no argument it looks for a single .spl at the repository root.
#
# ⚠️ It REFUSES to run when it cannot find an archive, instead of passing. A
# check that goes green because it had nothing to inspect is worse than no
# check: it reports a verification that never happened.

set -u

RACINE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
V=$'\033[32m'; R=$'\033[31m'; D=$'\033[2m'; Z=$'\033[0m'

ARCHIVE="${1:-}"
if [ -z "$ARCHIVE" ]; then
	mapfile -t trouvees < <(find "$RACINE" -maxdepth 2 -name '*.spl' 2>/dev/null)
	case "${#trouvees[@]}" in
		0) echo "${R}no .spl found.${Z} Build one first (CONTRIBUTE §2), then pass its path." >&2
		   echo "${D}Refusing to report success on an archive that does not exist.${Z}" >&2
		   exit 1 ;;
		1) ARCHIVE="${trouvees[0]}" ;;
		*) echo "${R}several .spl found${Z} — name the one to inspect:" >&2
		   printf '  %s\n' "${trouvees[@]}" >&2; exit 1 ;;
	esac
fi

if [ ! -f "$ARCHIVE" ]; then
	echo "${R}archive not found:${Z} $ARCHIVE" >&2
	exit 1
fi

echo "inspecting $(basename "$ARCHIVE")"
CONTENU="$(tar -tzf "$ARCHIVE" 2>/dev/null)" || { echo "${R}cannot read the archive${Z}" >&2; exit 1; }
echo "${D}  $(echo "$CONTENU" | wc -l) entries${Z}"

echecs=0

refuser() {
	local motif="$1" quoi="$2"
	local n; n="$(echo "$CONTENU" | grep -cE "$motif" || true)"
	if [ "$n" -gt 0 ]; then
		echo " ${R}KO${Z}  $quoi ($n)"
		echo "$CONTENU" | grep -E "$motif" | head -5 | sed 's/^/       /'
		echecs=$((echecs + 1))
	else
		echo " ${V}ok${Z}  $quoi: absent"
	fi
}

exiger() {
	local motif="$1" quoi="$2"
	if echo "$CONTENU" | grep -qE "$motif"; then
		echo " ${V}ok${Z}  $quoi: present"
	else
		echo " ${R}KO${Z}  $quoi: MISSING from the archive"
		echecs=$((echecs + 1))
	fi
}

# Compiled Python: reborn on every local test run, and copied verbatim by ucc-gen.
refuser '\.pyc$|/__pycache__/' "compiled Python"
# Windows binaries have no business in a Splunk Cloud package.
refuser '\.(exe|pyd|dll)$' "Windows binaries"
# UCC scaffold left in production: get_data_from_api() returned {"line1": "hello"}.
refuser 'bin/thehive_cortex_helper\.py$' "UCC scaffold residue"

# ⚠️ Zero bytes, and load-bearing. Without it cortex4py becomes a namespace
# package and another add-on can shadow its root modules -- which is exactly
# what cortex.py imports. A file this size is the first casualty of a cleanup,
# and nothing about it says it matters.
exiger 'libs/cortex4py/__init__\.py$' "cortex4py/__init__.py (0 bytes, load-bearing)"

echo
if [ "$echecs" -gt 0 ]; then
	echo "${R}$echecs problem(s) in the archive.${Z}"
	exit 1
fi
echo "${V}the archive contains what it should, and nothing it should not.${Z}"
