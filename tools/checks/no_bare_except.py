#!/usr/bin/env python3
"""Refuse the exception handlers that cannot report anything.

Two shapes are caught, and they fail for the same reason: whatever went wrong
leaves no trace, so the defect is indistinguishable from correct behaviour.

  except:            -- also swallows KeyboardInterrupt and SystemExit
  except ...: pass   -- swallows the cause and says nothing

Measured precedent in this add-on: `except Exception: pass` around the log
level resolution meant a user could configure DEBUG, keep receiving INFO, and
find no explanation anywhere. The fallback was fine; being unable to observe
it was not.

Generated files are skipped: they come from ucc-gen / the Splunk AOB and are
rewritten at every build, so a finding there cannot be acted upon here.

    python tools/checks/no_bare_except.py

Exit code 0 when clean, 1 otherwise, naming file, line and shape.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCES = ROOT / "TA-thehive-cortex" / "package" / "bin"

#: Vendored third-party libraries: not ours to fix.
EXCLUDED_DIRS = {"libs", "__pycache__"}

#: Emitted by ucc-gen / the Splunk Add-on Builder and rewritten at every build.
#: Listing them by name rather than guessing keeps the check honest: a NEW
#: generated file must be added here deliberately, not slip through a pattern.
EXCLUDED_FILES = {
    "cim_actions.py",
    "alert_actions_base.py",
    "ta_thehive_cortex_declare.py",
    "logging_helper.py",
}


def _is_pass_only(handler: ast.ExceptHandler) -> bool:
    """A body that is exactly `pass`, possibly preceded by a docstring."""
    body = [n for n in handler.body if not (isinstance(n, ast.Expr)
                                             and isinstance(n.value, ast.Constant)
                                             and isinstance(n.value.value, str))]
    return len(body) == 1 and isinstance(body[0], ast.Pass)


#: An `except ...: pass` is defensible when the SURROUNDING code reports the
#: failure anyway -- typically a best-effort enrichment of a message that is
#: logged just below. Such a case must say so ON THE LINE, with its reason:
#:
#:     except ValueError:  # silent-except: reported by THC-117 below
#:         pass
#:
#: The waiver is deliberately local and motivated. A distant tolerance list is
#: how a guard ends up covering the very defect it was built to catch, long
#: after the reason was forgotten.
EXEMPTION = "silent-except:"


def analyse(path: Path) -> list[tuple[int, str]]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    tree = ast.parse(text, filename=str(path))
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue

        # A bare `except:` is never waivable: it swallows KeyboardInterrupt and
        # SystemExit, which no reason can justify.
        if node.type is None:
            found.append((node.lineno, "bare `except:` — also catches KeyboardInterrupt and SystemExit"))
            continue

        if not _is_pass_only(node):
            continue

        # The waiver may sit on the `except` line or on the `pass` line.
        scope = range(node.lineno - 1, min(node.lineno + len(node.body), len(lines)))
        if any(EXEMPTION in lines[i] for i in scope):
            continue
        found.append((node.lineno, "`except ...: pass` — the cause is discarded without a trace"))
    return found


def main() -> int:
    if not SOURCES.is_dir():
        print(f"sources not found: {SOURCES}", file=sys.stderr)
        return 1

    total = 0
    for path in sorted(SOURCES.rglob("*.py")):
        if EXCLUDED_DIRS & set(path.relative_to(SOURCES).parts):
            continue
        if path.name in EXCLUDED_FILES:
            continue
        for line, form in analyse(path):
            print(f"{path.relative_to(ROOT)}:{line}: {form}")
            total += 1

    if total:
        print()
        print(f"{total} exception handler(s) that cannot report anything.")
        print("Catch a named exception and log it. A swallowed error is a defect")
        print("that looks exactly like working code.")
        return 1

    print("no silent exception handler in the add-on sources.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
