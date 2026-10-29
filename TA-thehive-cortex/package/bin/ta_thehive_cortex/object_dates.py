# encoding = utf-8
#
# Copyright: LGPLv3 (https://www.gnu.org/licenses/lgpl-3.0.txt)
#
"""The dates of ONE object collected from TheHive: seconds, and which one is the event time.

TheHive leaves a date out of the JSON when it has no value -- an object that was
never updated carries no ``_updatedAt`` -- and production has shown audit
entries without ``_createdAt`` as well. Every collector indexed those keys
directly, so a single such object raised ``KeyError`` and the run lost the whole
pull with it: the objects already processed, and the time window, which no
later run asks for again.

No logger here: the caller decides how to report the names returned.
"""

from __future__ import annotations

#: The dates every collected object may carry, in epoch milliseconds.
COMMON_DATES = ("_createdAt", "_updatedAt")


def stamp(event: dict, date_field: str, extra_dates: tuple = (), now: float = 0.0) -> list:
    """Convert the object's dates to seconds in place and set ``event["_time"]``.

    ``_time`` is taken from ``date_field``, else ``_createdAt``, else
    ``_updatedAt``, else ``now``. Only the dates named in ``COMMON_DATES`` and
    ``extra_dates`` are converted; a ``date_field`` outside them is used as the
    caller already left it.

    Returns the names, among ``date_field`` and ``_createdAt``, that were absent
    or empty -- in that order, without repeats -- so the caller can say so.
    Nothing is invented in the object itself: a missing date stays missing.
    """
    for name in COMMON_DATES + tuple(extra_dates):
        if event.get(name) is not None:
            event[name] = event[name] / 1000
    missing = [name for name in dict.fromkeys((date_field, "_createdAt")) if event.get(name) is None]
    for name in (date_field, "_createdAt", "_updatedAt"):
        if event.get(name) is not None:
            event["_time"] = int(event[name])
            return missing
    event["_time"] = int(now)
    return missing
