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

RACINE = Path(__file__).resolve().parents[2]
SOURCES = RACINE / "TA-thehive-cortex" / "package" / "bin"

#: Vendored third-party libraries: not ours to fix.
EXCLUS_REPERTOIRES = {"libs", "__pycache__"}

#: Emitted by ucc-gen / the Splunk Add-on Builder and rewritten at every build.
#: Listing them by name rather than guessing keeps the check honest: a NEW
#: generated file must be added here deliberately, not slip through a pattern.
EXCLUS_FICHIERS = {
    "cim_actions.py",
    "alert_actions_base.py",
    "ta_thehive_cortex_declare.py",
    "logging_helper.py",
}


def _est_pass_seul(handler: ast.ExceptHandler) -> bool:
    """A body that is exactly `pass`, possibly preceded by a docstring."""
    corps = [n for n in handler.body if not (isinstance(n, ast.Expr)
                                             and isinstance(n.value, ast.Constant)
                                             and isinstance(n.value.value, str))]
    return len(corps) == 1 and isinstance(corps[0], ast.Pass)


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
DEROGATION = "silent-except:"


def analyser(chemin: Path) -> list[tuple[int, str]]:
    texte = chemin.read_text(encoding="utf-8")
    lignes = texte.splitlines()
    arbre = ast.parse(texte, filename=str(chemin))
    trouves: list[tuple[int, str]] = []
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.ExceptHandler):
            continue

        # A bare `except:` is never waivable: it swallows KeyboardInterrupt and
        # SystemExit, which no reason can justify.
        if noeud.type is None:
            trouves.append((noeud.lineno, "bare `except:` — also catches KeyboardInterrupt and SystemExit"))
            continue

        if not _est_pass_seul(noeud):
            continue

        # The waiver may sit on the `except` line or on the `pass` line.
        portee = range(noeud.lineno - 1, min(noeud.lineno + len(noeud.body), len(lignes)))
        if any(DEROGATION in lignes[i] for i in portee):
            continue
        trouves.append((noeud.lineno, "`except ...: pass` — the cause is discarded without a trace"))
    return trouves


def main() -> int:
    if not SOURCES.is_dir():
        print(f"sources not found: {SOURCES}", file=sys.stderr)
        return 1

    total = 0
    for chemin in sorted(SOURCES.rglob("*.py")):
        if EXCLUS_REPERTOIRES & set(chemin.relative_to(SOURCES).parts):
            continue
        if chemin.name in EXCLUS_FICHIERS:
            continue
        for ligne, forme in analyser(chemin):
            print(f"{chemin.relative_to(RACINE)}:{ligne}: {forme}")
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
