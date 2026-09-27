#!/usr/bin/env python3
"""A panel nobody can ever see, and a comment that breaks the file.

Two failures this repository shipped, both invisible to a reading:

**1. A panel gated on a token nothing sets.** `thehive_statistics.xml` hid two
panels behind `depends="$always_hidden$"`. A hidden panel does not dispatch its
search — and those two searches were the only producers of the tokens the main
chart consumed. The chart therefore waited for input forever, with no error and
no empty-result message. The view was dead for four releases.

**2. A panel invisible for its input's DEFAULT value.** `thehive_alerts.xml`
gated its results panel on a token set by `<condition value="list">`, while the
input's own `<default>` is already `list`. A `<change>` does not fire for the
value an input already has at load, so the panel was absent on arrival and
appeared only after the user moved the input away and back. Its twin
`cases.xml` has no such gate — two files 86 % identical behaving in opposite
ways.

⚠️ Note how narrow that rule is. A token set inside a `<change>` is normal and
usually deliberate: a panel that appears once you pick "CREATE" is the point.
Reporting all of them would be a guard crying wolf, and a guard that cries wolf
gets switched off. Only the mismatch with the DEFAULT value is a defect.

**3. A double dash inside an XML comment.** Illegal, and it makes the whole
view unparseable. Caught twice while writing the fixes above, which is exactly
why it is checked here rather than remembered.

    python tools/checks/views_are_reachable.py

Exit 0 when every view parses and every gated panel can actually appear.
"""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UI = ROOT / "TA-thehive-cortex" / "package" / "default" / "data" / "ui"

#: Tokens Splunk provides itself, never set by the view.
PROVIDED_BY_SPLUNK = re.compile(
    r"^(?:env:|job\.|result\.|click\.|row\.|earliest|latest|form\.)"
)

#: The "CSS-carrying panel" idiom, deliberately invisible.
INVISIBLE_IDIOMS = {"alwaysHideCSSPanel"}


def views():
    for path in sorted(UI.rglob("*.xml")):
        yield path


def tokens_set(text: str) -> set[str]:
    set_tokens = set()
    set_tokens.update(re.findall(r'<set\s+token="([^"]+)"', text))
    set_tokens.update(re.findall(r'<eval\s+token="([^"]+)"', text))
    set_tokens.update(re.findall(r'<input[^>]*\stoken="([^"]+)"', text))
    set_tokens.update(re.findall(r'<unset\s+token="([^"]+)"', text))
    return set_tokens


def tokens_absent_on_load(text: str) -> set[str]:
    """The tokens that no DEFAULT value produces.

    For each input: its default value, then the tokens its `<change>`
    sets for that very value. A token set only for ANOTHER value
    is absent on load, and so is the panel that depends on it.
    """
    absent = set()
    for block in re.findall(r"<input\b.*?</input>", text, re.S):
        default = re.search(r"<default>(.*?)</default>", block, re.S)
        if not default:
            continue
        default_value = default.group(1).strip()
        for condition in re.findall(r"<condition\b([^>]*)>(.*?)</condition>",
                                    block, re.S):
            attributes, body = condition
            targeted = re.search(r'value="([^"]*)"', attributes)
            if not targeted:
                continue
            # ⚠️ ONLY this case is a defect: the condition targets the value the
            # input ALREADY holds, so the panel should be there on arrival
            # -- and it is not, because a <change> does not fire on
            # load.
            #
            # A condition targeting ANOTHER value hides the panel
            # on purpose: that is the whole point of a form with modes.
            # Reporting it would be crying wolf, and a guard that cries wolf
            # ends up switched off.
            if targeted.group(1) == default_value:
                absent |= set(re.findall(r'<set\s+token="([^"]+)"', body))
    outside_change = tokens_set(re.sub(r"<change>.*?</change>", "", text, flags=re.S))
    return absent - outside_change


def main() -> int:
    if not UI.is_dir():
        print(f"views not found: {UI}", file=sys.stderr)
        return 1

    findings = []
    warnings_found = []

    for path in views():
        relative = path.relative_to(ROOT)
        raw = path.read_text(encoding="utf-8")
        # ⚠️ Strip the comments BEFORE looking for a pattern: otherwise the
        # guard denounces itself on the sentence explaining the defect it fixes.
        text = re.sub(r"<!--.*?-->", "", raw, flags=re.S)

        # --- 3. a `--` inside a comment makes the file unreadable -------------
        for body in re.findall(r"<!--(.*?)-->", raw, re.S):
            if "--" in body:
                findings.append(
                    f"{relative}: a comment contains a double dash, which is "
                    f"illegal in XML and makes the whole view unparseable"
                )

        try:
            ET.parse(path)
        except ET.ParseError as e:
            findings.append(f"{relative}: does not parse — {e}")
            continue

        set_tokens = tokens_set(text)
        absent_on_load = tokens_absent_on_load(text)

        # ⚠️ A rule "an input whose token nobody reads" was written
        # here and then REMOVED the same day: it returned 21 findings, about
        # twenty of which described correct behaviour. A mode token
        # (`action`, `view_mode`) is never read through a `$token$` -- its
        # own `<change>` is what uses it -- and a `depths` carried BY an input
        # disappears when the inputs are stripped to look for readers.
        #
        # The starting observation still holds: a control that drives nothing is
        # worse than no control, because the user believes they acted.
        # But it is not detected at that price, and a guard that cries wolf
        # ends up switched off -- taking the three rules above with it.

        # --- 4. a refresh set on the search of an INPUT ----------------------
        # ⚠️ A panel that refreshes is useful; a dropdown that
        # refreshes yanks the selection from under the user's fingers
        # every minute. Seen on my own work: a
        # substitution applied to "every panel search" hit
        # three that fed inputs INSIDE panels.
        for block in re.findall(r"<input\b.*?</input>", text, re.S):
            if "<refresh>" in block:
                label = re.search(r"<label>(.*?)</label>", block, re.S)
                name = label.group(1).strip() if label else "?"
                findings.append(
                    f"{relative}: the input \"{name}\" carries an auto-refresh. "
                    f"Its selection will jump under the user every cycle"
                )

        for attribute in ("depends", "rejects"):
            for expression in re.findall(rf'{attribute}="([^"]+)"', text):
                for token in re.findall(r"\$([^$,]+)\$", expression):
                    if token in INVISIBLE_IDIOMS or PROVIDED_BY_SPLUNK.match(token):
                        continue
                    if token not in set_tokens:
                        findings.append(
                            f"{relative}: a panel is gated on ${token}$, which "
                            f"nothing in this view ever sets. It can never "
                            f"appear, and its searches never run"
                        )
                    elif attribute == "depends" and token in absent_on_load:
                        warnings_found.append(
                            f"{relative}: a panel is gated on ${token}$, set by "
                            f"a <condition> matching an input's DEFAULT value. "
                            f"A <change> does not fire at load, so the panel is "
                            f"absent on arrival until the user moves that input "
                            f"away and back"
                        )

    for a in warnings_found:
        print(f"  ⚠️  {a}")
    for c in findings:
        print(f"  {c}")

    if findings:
        print()
        print("A panel that cannot appear does not report an error: it is simply")
        print("not there, and its searches never run.")
        return 1

    print(f"every view parses; every gated panel can appear"
          + (f" ({len(warnings_found)} reported)" if warnings_found else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
