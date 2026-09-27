#!/usr/bin/env bash
# Refuse a shipped dependency with a known vulnerability nobody has accepted.
#
# Dependabot only runs on GitHub; on Gitea nothing watched the libraries the
# .spl ships, and requests 2.32.3 (CVE-2024-47081) sat pinned unnoticed
# (#39). This audits package/lib/requirements.txt EXACTLY as pinned:
# --no-deps --disable-pip, because the file already lists the whole closure
# (pins_match_build.sh guarantees it), so no resolution and no interpreter
# dependence.
#
# Accepted advisories live in dependency_audit_accepted.txt, each with a date
# and the blocker that prevents the fix. Anything else fails.
#
#     PIP_AUDIT=pip-audit tools/checks/dependency_audit.sh
#
# ⚠️ Needs network access to the advisory database. On Windows, run with
# PYTHONUTF8=1: pip-audit otherwise dies in a cp1252 decode.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REQS="$ROOT/TA-thehive-cortex/package/lib/requirements.txt"
ACCEPTED="$ROOT/tools/checks/dependency_audit_accepted.txt"
PIP_AUDIT="${PIP_AUDIT:-pip-audit}"

ignores=()
while read -r id _; do
	case "$id" in "" | \#*) continue ;; esac
	ignores+=(--ignore-vuln "$id")
done <"$ACCEPTED"

echo "auditing $(grep -c '==' "$REQS") pins, $((${#ignores[@]} / 2)) accepted advisories"
"$PIP_AUDIT" --no-deps --disable-pip --progress-spinner off -r "$REQS" "${ignores[@]}"
