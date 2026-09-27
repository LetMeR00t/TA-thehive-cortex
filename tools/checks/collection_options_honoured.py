#!/usr/bin/env python3
"""An input option the form offers, the configuration saves, and the run drops.

#37 shipped for years: the alerts & cases input form lists `ttps` under
"Common" -- offered for alerts and cases alike -- the choice is saved in
`inputs.conf`, and at every run the input filtered it out of an alert's
request without a word. Neither side can shout alone: the form is right to
offer what TheHive serves, the code is free to keep what it wants. The defect
lives in the GAP between the two, so this check reads both.

Rules:

1. Every option `globalConfig.json` offers to a type (group "Common" = both,
   "Alerts only", "Cases only") must be kept for that type by
   `ta_thehive_cortex/collection_options.py`, unless it is listed in
   `KNOWN_GAPS` below.
2. `KNOWN_GAPS` is a ratchet: an entry that is no longer a gap fails the
   check too, so the list can only shrink.
3. A form option outside any group has no declared applicability: refused.
4. Each input that collects alerts & cases filters through `options_for`, and
   carries no literal allow-list of its own -- a second copy is how the two
   inputs would drift apart again.

    python tools/checks/collection_options_honoured.py

Exit 0 when every offered option is honoured or knowingly listed.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "TA-thehive-cortex"
BIN = APP / "package" / "bin"
MODULE = BIN / "ta_thehive_cortex" / "collection_options.py"

SERVICES = ("thehive_alerts_cases", "backfill_alerts_cases")
FIELDS = {"additional_information": "ADDITIONAL_INFORMATION", "extra_data": "EXTRA_DATA"}
GROUP_TYPES = {"Common": ("alerts", "cases"), "Alerts only": ("alerts",), "Cases only": ("cases",)}

#: Offered by the form, dropped at run time, and knowingly so. Every entry is
#: an open question for the maintainer (collect it, or stop offering it), not
#: a decision. Remove an entry when its gap closes -- the check insists.
KNOWN_GAPS = {
    ("extra_data", "alerts"): {"procedureCount", "importDate", "relatedCase"},
    ("extra_data", "cases"): {
        "procedureCount", "observableStats", "taskStats", "alertCount",
        "isOwner", "shareCount", "permissions", "actionRequired",
        "attachmentCount", "contributors", "computed.handlingDuration",
        "computed.handlingDurationInSeconds", "computed.handlingDurationInMinutes",
        "computed.handlingDurationInHours", "computed.handlingDurationInDays",
        "links",
    },
}

LITERAL_FILTER = re.compile(r"if item in \[")


def kept_by_code() -> dict[str, dict[str, set[str]]]:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    kept = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            for name in names:
                if name in FIELDS.values():
                    value = ast.literal_eval(node.value)
                    kept[name] = {k: set(v) for k, v in value.items()}
    return kept


def offered_by_form(errors: list[str]) -> dict[tuple[str, str], set[str]]:
    config = json.loads((APP / "globalConfig.json").read_text(encoding="utf-8"))
    offered: dict[tuple[str, str], set[str]] = {}
    services = {s["name"]: s for s in config["pages"]["inputs"]["services"]}
    for service in SERVICES:
        if service not in services:
            errors.append(f"globalConfig.json: service `{service}` not found")
            continue
        for entity in services[service]["entity"]:
            if entity.get("field") not in FIELDS:
                continue
            options = entity["options"]
            grouped = set()
            for group in options.get("groups", []):
                types = GROUP_TYPES.get(group["label"])
                if types is None:
                    errors.append(f"{service}.{entity['field']}: unknown group `{group['label']}`")
                    continue
                for field in group["fields"]:
                    grouped.add(field)
                    for input_type in types:
                        offered.setdefault((entity["field"], input_type), set()).add(field)
            for row in options.get("rows", []):
                if row["field"] not in grouped:
                    errors.append(
                        f"{service}.{entity['field']}: option `{row['field']}` sits in no "
                        "group, so nothing says which type may use it")
    return offered


def main() -> int:
    errors: list[str] = []
    kept = kept_by_code()
    offered = offered_by_form(errors)

    for (field, input_type), options in sorted(offered.items()):
        honoured = kept.get(FIELDS[field], {}).get(input_type, set())
        gaps = options - honoured
        known = KNOWN_GAPS.get((field, input_type), set())
        for option in sorted(gaps - known):
            errors.append(
                f"`{option}` is offered for {input_type} in `{field}` but "
                f"collection_options.py drops it at run time")
        for option in sorted(known - gaps):
            errors.append(
                f"KNOWN_GAPS lists `{option}` ({field}, {input_type}) but it is no "
                "longer a gap: remove it from the list")

    for script in SERVICES:
        source = (BIN / f"{script}.py").read_text(encoding="utf-8")
        if "options_for(" not in source:
            errors.append(f"{script}.py does not filter through collection_options.options_for")
        if LITERAL_FILTER.search(source):
            errors.append(f"{script}.py carries its own literal allow-list")

    if errors:
        print("collection_options_honoured: FAILED")
        for error in errors:
            print(f"  - {error}")
        return 1
    print(f"collection_options_honoured: OK ({sum(len(v) for v in offered.values())} "
          f"offered options checked, {sum(len(v) for v in KNOWN_GAPS.values())} known gaps)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
