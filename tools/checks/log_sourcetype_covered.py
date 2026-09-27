#!/usr/bin/env python3
"""Every log file the add-on writes must be matched by a props.conf stanza.

⚠️ **The defect lives in the gap between two files, so neither can shout on its
own.** `ta_logging.py` renamed the log files in v4.0.0; `props.conf` still
enumerated the v3.x names. Both files were internally valid. The search
commands silently lost their sourcetype for three minor versions, and the
symptom was *misleading*: the four `*_modalert` stanzas kept matching, so the
file looked alive and only some searches were broken.

Two naming schemes coexist, and the check models BOTH:

* `ta_logging.setup_logging(name)`  -> ``TA-thehive-cortex_<name>.log``
* `solnlib` `Logs().get_logger(n)`  -> ``<n>.log`` (no namespace is set here),
  and alert actions pass ``<alert>_modalert``

    python tools/checks/log_sourcetype_covered.py

Exit 0 when every produced name is covered, 1 otherwise, naming the file and
the stanza that should have covered it.

⚠️ The check also fails when the *shape* of a name stops matching the model
above. A guard that keeps validating an obsolete pattern is worse than none:
it reports a coverage that no longer means anything.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "TA-thehive-cortex" / "package"
BIN = PACKAGE / "bin"
DEFAULT = PACKAGE / "default"

LOG_DIR = "/opt/splunk/var/log/splunk/"
SOURCETYPE = "tathehivecortex:log"


# --------------------------------------------------------------------------
# 1. What names does the code actually produce?
# --------------------------------------------------------------------------

def ta_logging_template() -> str:
    """Read the file-name template out of ta_logging.py, instead of assuming it.

    Returns the prefix, e.g. ``TA-thehive-cortex_``. Raises when the source no
    longer builds the name the way this check believes.
    """
    source = (BIN / "ta_logging.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    ta_name = None
    template_seen = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if not isinstance(target, ast.Name):
                continue
            if target.id == "ta_name" and isinstance(node.value, ast.Constant):
                ta_name = node.value.value
            if target.id == "LOGGING_FILE_NAME":
                # ta_name + "_" + name + ".log" -- we only need the constants.
                # ⚠️ ast.walk is breadth-first, so the constants come out in
                # tree order, not source order. Compare the SET.
                constants = {
                    n.value for n in ast.walk(node.value)
                    if isinstance(n, ast.Constant) and isinstance(n.value, str)
                }
                if constants == {"_", ".log"}:
                    template_seen = True
    if ta_name is None or not template_seen:
        raise SystemExit(
            "ta_logging.py no longer builds the log file name as "
            '`ta_name + "_" + name + ".log"`. This check models a shape that '
            "no longer exists -- update it before trusting its verdict."
        )
    return f"{ta_name}_"


def command_names() -> set[str]:
    """Every literal name handed to setup_logging, directly or via logger_name."""
    names: set[str] = set()
    for source_file in sorted(BIN.rglob("*.py")):
        try:
            tree = ast.parse(source_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            # setup_logging("thehive_audit")
            if isinstance(node, ast.Call):
                function = node.func
                name = getattr(function, "id", None) or getattr(function, "attr", None)
                if name == "setup_logging" and node.args:
                    if isinstance(node.args[0], ast.Constant):
                        names.add(node.args[0].value)
                # initialize_thehive_instances(..., logger_name="thehive_get_case")
                for kw in node.keywords:
                    if kw.arg == "logger_name" and isinstance(kw.value, ast.Constant):
                        names.add(kw.value.value)
            # def initialize_...(..., logger_name="script") -- the default is a
            # real file the day a caller forgets the argument.
            if isinstance(node, ast.FunctionDef):
                for arg, default in zip(
                    node.args.args[-len(node.args.defaults):] if node.args.defaults else [],
                    node.args.defaults,
                ):
                    if arg.arg == "logger_name" and isinstance(default, ast.Constant):
                        names.add(default.value)
    return names


def alert_action_names() -> set[str]:
    """Alert actions log through solnlib, under `<alert>_modalert`."""
    base = (BIN / "ta_thehive_cortex" / "alert_actions_base.py").read_text(encoding="utf-8")
    if '_logger_name = alert_name + "_modalert"' not in base:
        raise SystemExit(
            "alert_actions_base.py no longer names its logger "
            '`alert_name + "_modalert"`. Update this check before trusting it.'
        )
    conf = (DEFAULT / "alert_actions.conf").read_text(encoding="utf-8")
    return {f"{name}_modalert" for name in re.findall(r"^\[([^\]]+)\]", conf, re.M)}


def check_no_namespace() -> str | None:
    """solnlib prefixes the file ONLY when a namespace is set via set_context.

    Proven on solnlib's source: `Logs._get_log_file` returns `<name>.log` when
    `_default_namespace` is None. If the add-on ever calls `set_context`, the
    alert action files gain a prefix and the stanzas below stop matching --
    exactly the v4.0.0 defect, in the other direction.
    """
    for source_file in BIN.rglob("*.py"):
        if "set_context" in source_file.read_text(encoding="utf-8"):
            return (
                f"{source_file.relative_to(ROOT)} calls solnlib's set_context: the "
                "alert action log files are now namespaced, so their props.conf "
                "stanzas need the prefix too."
            )
    return None


# --------------------------------------------------------------------------
# 2. What does props.conf cover?
# --------------------------------------------------------------------------

def source_patterns() -> list[tuple[str, re.Pattern[str]]]:
    """Translate Splunk `[source::...]` stanzas into regexes.

    Splunk's rules: `...` matches anything including path separators, `*`
    matches anything except a path separator.
    """
    text = (DEFAULT / "props.conf").read_text(encoding="utf-8")
    patterns = []
    stanza = None
    for line in text.splitlines():
        bare = line.strip()
        if bare.startswith("[") and bare.endswith("]"):
            stanza = bare[1:-1]
            continue
        if not stanza or not stanza.startswith("source::"):
            continue
        if bare.replace(" ", "").lower() == f"sourcetype={SOURCETYPE}":
            pattern = stanza[len("source::"):]
            regex = ""
            i = 0
            while i < len(pattern):
                if pattern.startswith("...", i):
                    regex += ".*"
                    i += 3
                elif pattern[i] == "*":
                    regex += r"[^/\\]*"
                    i += 1
                else:
                    regex += re.escape(pattern[i])
                    i += 1
            patterns.append((stanza, re.compile(f"^{regex}$")))
    return patterns


def sourcetype_defined() -> bool:
    """The sourcetype was assigned everywhere and defined nowhere until v4.2.3."""
    text = (DEFAULT / "props.conf").read_text(encoding="utf-8")
    return any(l.strip() == f"[{SOURCETYPE}]" for l in text.splitlines())


# --------------------------------------------------------------------------

def main() -> int:
    if not PACKAGE.is_dir():
        print(f"package not found: {PACKAGE}", file=sys.stderr)
        return 1

    prefix = ta_logging_template()
    expected = {f"{prefix}{n}.log" for n in command_names()}
    expected |= {f"{n}.log" for n in alert_action_names()}

    patterns = source_patterns()
    if not patterns:
        print(f"props.conf assigns {SOURCETYPE} from no [source::] stanza at all.")
        return 1

    findings = []
    derived = check_no_namespace()
    if derived:
        findings.append(derived)

    for source_file in sorted(expected):
        path = LOG_DIR + source_file
        if not any(rx.match(path) for _, rx in patterns):
            findings.append(
                f"{source_file} is written by the add-on, but no [source::] stanza "
                f"of props.conf assigns it {SOURCETYPE}. Splunk will auto-learn "
                f"a sourcetype from the file name instead."
            )

    if not sourcetype_defined():
        findings.append(
            f"[{SOURCETYPE}] is assigned by {len(patterns)} stanza(s) and defined "
            f"by none: line breaking and timestamping fall back to Splunk's "
            f"defaults on a format that starts with an ISO date."
        )

    for c in findings:
        print(f"  {c}")

    if findings:
        print()
        print("Both files are individually valid; the break is between them.")
        return 1

    print(f"{len(expected)} log file name(s) produced, all covered by "
          f"{len(patterns)} stanza(s); [{SOURCETYPE}] is defined.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
