#!/usr/bin/env python3
"""What the add-on declares, its documentation and its online help announce.

The defect lives in the gap between two files, so neither can cry on its own
(#26). Measured before this check existed: `cortexrefreshanalyzers` was
declared in `commands.conf` but absent from `searchbnf.conf` (no Splunk
online help) and from `docs/commands.md`; `cortex_run_a_new_job` was absent
from the alert action documentation; `docs/installation.md` announced
"Three types of inputs" for six.

Three comparisons:

1. `commands.conf` == the `<name>-command` stanzas of `searchbnf.conf`
   == the `## <name>` sections of `docs/commands.md`;
2. every `alert_actions.conf` stanza is named in
   `docs/alert_actions_and_adaptive_responses.md`;
3. the "<N> types of inputs" sentence of `docs/installation.md` matches the
   input families of `globalConfig.json` (the title before `:`, so a family's
   regular and one-shot services count once).

    python tools/checks/declarations_documented.py

Exit 0 when the three agree.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT = ROOT / "TA-thehive-cortex" / "package" / "default"
DOCS = ROOT / "docs"
NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
           "seven": 7, "eight": 8, "nine": 9, "ten": 10}


def stanzas(path: Path) -> set[str]:
    return set(re.findall(r"^\[([^\]]+)\]", path.read_text(encoding="utf-8"), re.M))


def input_families() -> set[str]:
    config = json.loads((ROOT / "TA-thehive-cortex" / "globalConfig.json")
                        .read_text(encoding="utf-8"))
    return {s["title"].split(":")[0].strip()
            for s in config["pages"]["inputs"]["services"]}


def findings() -> list[str]:
    found = []

    commands = stanzas(DEFAULT / "commands.conf")
    bnf = {s[: -len("-command")] for s in stanzas(DEFAULT / "searchbnf.conf")
           if s.endswith("-command")}
    documented = set(re.findall(r"^## (\S+)\s*$",
                                (DOCS / "commands.md").read_text(encoding="utf-8"), re.M))
    for name in sorted(commands - bnf):
        found.append(f"command '{name}' has no [{name}-command] in searchbnf.conf")
    for name in sorted(bnf - commands):
        found.append(f"searchbnf.conf documents '{name}', which commands.conf does not declare")
    for name in sorted(commands - documented):
        found.append(f"command '{name}' has no '## {name}' section in docs/commands.md")
    for name in sorted(documented - commands):
        found.append(f"docs/commands.md documents '{name}', which commands.conf does not declare")

    alert_doc = (DOCS / "alert_actions_and_adaptive_responses.md").read_text(encoding="utf-8")
    for name in sorted(stanzas(DEFAULT / "alert_actions.conf")):
        if not re.search(rf"\b{re.escape(name)}\b", alert_doc):
            found.append(f"alert action '{name}' is not named in "
                         f"docs/alert_actions_and_adaptive_responses.md")

    families = input_families()
    sentence = re.search(r"\b(\w+) types of inputs are available",
                         (DOCS / "installation.md").read_text(encoding="utf-8"))
    if not sentence:
        found.append("docs/installation.md lost its '<N> types of inputs are available' sentence")
    else:
        word = sentence.group(1).lower()
        announced = NUMBERS.get(word, int(word) if word.isdigit() else -1)
        if announced != len(families):
            found.append(f"docs/installation.md announces {word} types of inputs, "
                         f"globalConfig.json declares {len(families)}: {sorted(families)}")
    return found


def main() -> int:
    found = findings()
    for line in found:
        print(f"  {line}")
    if found:
        print()
        print("A declaration nobody documents is a feature nobody can find.")
        return 1
    print("commands, alert actions and input families agree with their documentation")
    return 0


if __name__ == "__main__":
    sys.exit(main())
