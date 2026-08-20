# encoding = utf-8
#
# Copyright: LGPLv3 (https://www.gnu.org/licenses/lgpl-3.0.txt)
#
"""Check a MITRE ``patternId`` against the catalogue TheHive actually holds.

⚠️ Two halves of the same hole, and each hid the other:

* the setting `thehive_ttp_catalog_name` was exposed on the configuration page,
  read, handed over in `defaults` — and consumed by nobody. Changing it did
  nothing at all.
* a TTP's `patternId` was validated by `values[1].startswith("T")`, which
  accepts `T`, `TOTO` and `T99999` alike. A wrong id was accepted here and
  rejected by TheHive later, in a message that names neither the row nor the
  field it came from.

The setting that was doing nothing existed precisely for the check that was
missing.

⚠️ On failure to reach the catalogue, this **lets the TTP through** with a
warning. Blocking would mean an unreachable catalogue silently dropping
legitimate TTPs — punishing the user for our own outage. We refuse only what we
have positively proven wrong.
"""

# ⚠️ Required. `set | None` in an annotation is an expression EVALUATED at
# import, and `|` between types only exists from Python 3.10. Splunk <= 10.1
# serves 3.9 only. Without this line the module raises TypeError while loading
# — and it does not fall alone: everything importing modalert_thehive_common
# goes with it, which is four test modules and both creation alert actions.
from __future__ import annotations

#: Filled once per execution. The catalogue does not change while a batch is
#: being sent, and re-reading it per row would be one HTTP round-trip per row.
_CACHE: dict[str, set] = {}


def reset_cache():
    """For the tests, and for a process outliving a single execution."""
    _CACHE.clear()


def pattern_ids(thehive, catalogue, logger_file) -> set | None:
    """Les known_ids du catalogue, ou None si on n'a pas pu le lire.

    ⚠️ `None` et l'ensemble vide ne veulent pas dire la même chose : `None`
    signifie « je n'ai pas pu vérifier », l'ensemble vide « le catalogue existe
    et il est vide ». Le premier laisse passer, le second refuse tout — et
    confondre les deux transformerait une panne réseau en rejet massif.
    """
    if not catalogue:
        return None
    if catalogue in _CACHE:
        return _CACHE[catalogue]

    try:
        patterns = thehive.procedure.get_catalog(catalogue)
    except Exception as e:
        logger_file.warn(
            id="THC-120",
            message=(
                f"the MITRE catalogue '{catalogue}' could not be read ({e}); "
                f"pattern ids are forwarded unchecked this time"
            ),
        )
        return None

    known_ids = {
        m["patternId"] for m in patterns
        if isinstance(m, dict) and m.get("patternId")
    }
    logger_file.debug(
        id="THC-121",
        message=f"MITRE catalogue '{catalogue}': {len(known_ids)} pattern id(s) loaded",
    )
    _CACHE[catalogue] = known_ids
    return known_ids


def is_known(pattern_id, known_ids) -> bool:
    """True when we could not check, or when the id is in the catalogue."""
    if known_ids is None:
        return True
    return pattern_id in known_ids
