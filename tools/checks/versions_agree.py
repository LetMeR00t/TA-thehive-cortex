#!/usr/bin/env python3
"""The add-on carries ONE version, and it is not behind the latest tag.

⚠️ **The build hides the drift, so nothing else ever shows it.** `ucc-gen build
--ta-version X` rewrites `globalConfig.json` and `app.manifest` alike, so the
archive is always consistent -- while the sources keep whatever each file was
last given. `app.manifest` sat at 4.0.0 (copied from an old build) next to a
`globalConfig.json` at 5.0.0 and a latest tag of v4.2.2 (#42): three answers to
"which version is this?", and a reader picks whichever file they open first.

What must agree:

- `globalConfig.json` `meta.version` and `package/app.manifest` `info.id.version`;
- `release_notes/v<version>.md` exists (notes are written as the work lands);
- the version is not lower than the highest `v*` tag reachable in this clone.
  A clone without tags (shallow CI checkout) SKIPS that rule and says so: a
  skipped rule is not a passed one.

    python tools/checks/versions_agree.py

Exit 0 when the version is single and plausible, 1 otherwise.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UCC = ROOT / "TA-thehive-cortex"
GLOBAL_CONFIG = UCC / "globalConfig.json"
MANIFEST = UCC / "package" / "app.manifest"
RELEASE_NOTES = ROOT / "release_notes"

_SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def _parse(version: str) -> tuple[int, int, int] | None:
    match = _SEMVER.match(version)
    return tuple(int(part) for part in match.groups()) if match else None  # type: ignore[return-value]


def _latest_tag() -> tuple[str, tuple[int, int, int]] | None:
    try:
        out = subprocess.run(["git", "tag", "--list", "v*"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    tags = [(t, _parse(t[1:])) for t in out.split()]
    tags = [(t, v) for t, v in tags if v is not None]
    return max(tags, key=lambda item: item[1]) if tags else None


def main() -> int:
    errors: list[str] = []
    config_version = json.loads(GLOBAL_CONFIG.read_text(encoding="utf-8"))["meta"]["version"]
    manifest_version = json.loads(MANIFEST.read_text(encoding="utf-8"))["info"]["id"]["version"]

    if config_version != manifest_version:
        errors.append(f"globalConfig.json meta.version is {config_version}, "
                      f"package/app.manifest info.id.version is {manifest_version}")

    parsed = _parse(config_version)
    if parsed is None:
        errors.append(f"globalConfig.json meta.version {config_version!r} is not X.Y.Z")
    elif not (RELEASE_NOTES / f"v{config_version}.md").is_file():
        errors.append(f"release_notes/v{config_version}.md is missing")

    latest = _latest_tag()
    if latest is None:
        print("⚠️ SKIPPED: no v* tag in this clone, the 'not behind the latest tag' rule was not checked")
    elif parsed is not None and parsed < latest[1]:
        errors.append(f"version {config_version} is lower than the latest tag {latest[0]}")

    for error in errors:
        print(f"❌ {error}")
    if errors:
        print("Fix the sources by hand: ucc-gen only aligns the ARCHIVE, never these files.")
        return 1
    print(f"✅ one version: {config_version}" + (f" (latest tag {latest[0]})" if latest else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
