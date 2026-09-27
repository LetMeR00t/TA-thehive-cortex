#!/usr/bin/env bash
# Build the add-on archive the one way that ships what we think it ships.
#
#     PYTHON=/path/to/python3.9 tools/build.sh 5.0.0
#
# ⚠️ Every step below used to be a line of prose in a document, to be
# remembered by whoever built. Measured on a real Windows build of 5.0.0 that
# skipped them: 209 compiled Python files and 3 Windows binaries in the
# archive (#10). A rule that must be REMEMBERED is not applied; a script is.
#
#   1. `ucc-gen` copies package/bin VERBATIM, so every __pycache__ left by a
#      local test run ships -- and pip itself compiles what it builds from
#      source. The output is purged of compiled Python AFTER the build and
#      BEFORE the archive, never "before building".
#   2. On Windows, pip installs Windows wheels: charset_normalizer arrives as
#      two `.cp39-win_amd64.pyd` extensions. Forcing its pure-Python source
#      distribution gives the same package the Linux build ships minus the
#      platform code. Only on Windows -- the Linux build is left as it is.
#   3. pip writes console-script launchers into lib/bin (`normalizer.exe` on
#      Windows). Splunk never runs them; a `.exe` in an add-on only fails
#      vetting.
#   4. `ucc-gen` must be told which interpreter to call: without
#      --python-binary-name it runs `python3`, which on Windows is the
#      Microsoft Store alias -- exit 9009, reported as a UnicodeDecodeError.
#   5. The archive, not the folder, is then inspected by
#      tools/checks/package_contents.sh. A red check fails the build.
#
# The version is an ARGUMENT, never inferred: without --ta-version ucc-gen
# takes it from `git describe` and happily builds `0.0.0+<sha>`.

set -euo pipefail

VERSION="${1:-}"
if [ -z "$VERSION" ]; then
	echo "usage: PYTHON=<python3.9> $0 <version>   (e.g. 5.0.0)" >&2
	exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT="$ROOT/TA-thehive-cortex"
PYTHON="${PYTHON:-python3.9}"

# The interpreter is named, never inherited: ucc-gen wants 3.9, and a
# machine's bare `python3` is often something else (3.11 on the workspace pod,
# a Store alias on Windows).
PY_VERSION="$("$PYTHON" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
if [ "$PY_VERSION" != "3.9" ]; then
	echo "ucc-gen must run on Python 3.9; $PYTHON is $PY_VERSION." >&2
	exit 2
fi
PY_EXE="$("$PYTHON" -c 'import sys; print(sys.executable)')"
IS_WINDOWS="$("$PYTHON" -c 'import os; print(int(os.name == "nt"))')"

BUILD_ARGS=(build --source package --ta-version "$VERSION" --python-binary-name "$PY_EXE")
if [ "$IS_WINDOWS" = "1" ]; then
	BUILD_ARGS+=("--pip-custom-flag=--no-binary=charset_normalizer")
fi

cd "$PROJECT"
rm -f TA-thehive-cortex-*.tar.gz
echo "building $VERSION with $PY_EXE (windows=$IS_WINDOWS)"
"$PYTHON" -m splunk_add_on_ucc_framework.main "${BUILD_ARGS[@]}"

APP="output/TA-thehive-cortex"
# ucc-gen can crash and still exit 0 (measured in CI): the output is the proof.
if [ ! -f "$APP/app.manifest" ]; then
	echo "ucc-gen produced no add-on in $APP -- the build failed." >&2
	exit 1
fi

find "$APP" -type d -name '__pycache__' -prune -exec rm -rf {} +
find "$APP" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete
if [ -d "$APP/lib/bin" ]; then
	find "$APP/lib/bin" -type f -name '*.exe' -delete
fi

"$PYTHON" -m splunk_add_on_ucc_framework.main package --path "$APP"
ARCHIVE="$(ls "$PROJECT"/TA-thehive-cortex-*.tar.gz)"

bash "$ROOT/tools/checks/package_contents.sh" "$ARCHIVE"
echo "archive: $ARCHIVE"
