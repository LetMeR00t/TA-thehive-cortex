# encoding = utf-8
#
# Copyright: LGPLv3 (https://www.gnu.org/licenses/lgpl-3.0.txt)
#
"""Turn what `field_mapping.dispatch_row` collected into TheHive observables.

⚠️ Split out of `field_mapping` (project-management#24) the day that file
crossed its own line ceiling a second time. The dispatch chain that decides
what a Splunk KEY *is* -- an observable, a custom field, a TTP -- stays there;
assembling the actual observable dicts from what that chain collected into
`ctx.observables_data` is a separate responsibility, moved here without
changing behaviour.
"""

from __future__ import annotations

import re

from value_codecs import str_to_bool, epoch_millis

TLP = {
    "W": 0, "G": 1, "A": 2, "AS": 3, "R": 4,
    "0": 0, "1": 1, "2": 2, "3": 3, "4": 4,
    "WHITE": 0, "GREEN": 1, "AMBER": 2, "AMBER+STRICT": 3, "RED": 4,
}

PAP = {
    "W": 0, "G": 1, "A": 2, "R": 3,
    "0": 0, "1": 1, "2": 2, "3": 3,
    "WHITE": 0, "GREEN": 1, "AMBER": 2, "RED": 3,
}

#: Separators a single Splunk field may pack several observable values with.
_MULTIVALUE = re.compile(r"[,;|\n]+")


def build_observables(ctx, observables):
    """Add what the rules collected to `observables`, in place.

    ⚠️ The list is passed in, and the de-duplication below is against ALL of it,
    not against the observables of the current field. Two different fields
    yielding the same value produce ONE observable -- that was the behaviour,
    and scoping the check per field would quietly start sending duplicates.
    """
    for field, data in ctx.observables_data.items():
        ctx.logger_file.debug(
            id="THC-111",
            message="Processing observable data: {} ({})".format(field, data),
        )
        if "value" not in data:
            ctx.logger_file.warn(
                id="THC-113",
                message="Observable '{0}' doesn't have any value set (no field '{0}' or "
                "'{0}:value' was detected), ignored.".format(field),
            )
            continue
        for observable in _observables_of(ctx, field, data):
            if observable not in observables:
                observables.append(observable)
    return observables


def _sighted_at_millis(ctx, field, raw):
    """`sighted_at` as milliseconds, and a word when it cannot be read.

    ⚠️ This used to be a bare `str_to_epoch_millis(...)`: an unreadable date
    became `None` and the observable was created without it, with nothing in
    the log. The custom field path already reported the same failure as
    THC-117; only this one stayed quiet, so the two halves of the same event
    disagreed about whether anything had gone wrong.
    """
    if raw in (None, ""):
        return None
    millis = epoch_millis(raw)
    if millis is None:
        ctx.logger_file.warning(
            id="THC-123",
            message=(
                f"Unreadable sighted_at for {field}: '{raw}' is not an epoch in "
                "seconds or milliseconds; the observable is created without a "
                "sighting date."
            ),
        )
    return millis


def _observables_of(ctx, field, data):
    """Every observable one collected field yields, one per packed value."""
    datatype = data.get("datatype", "other")
    raw = str(data["value"])
    values = [v.strip() for v in _MULTIVALUE.split(raw) if v.strip()]
    ctx.logger_file.debug(
        id="THC-112",
        message=f"Multi-value split for {field}: '{raw}' -> {str(values)}",
    )

    message = data.get("description", "No description provided for this observable")
    tags_raw = data.get("tags", "")
    if isinstance(tags_raw, list):
        tags = [str(t) for t in tags_raw]
    else:
        tags = [t.strip() for t in str(tags_raw).split(",") if t.strip()]
    tags.append("field:" + field)
    tags = [t[:128] for t in tags]

    # Sub-field names follow the documented snake_case convention and arrive as
    # strings, so they must be coerced to the native types TheHive expects.
    common = dict(
        dataType=datatype,
        message=message,
        tags=tags,
        tlp=TLP.get(str(data.get("tlp")), TLP["AMBER"]),
        pap=PAP.get(str(data.get("pap")), PAP["AMBER"]),
        ioc=str_to_bool(data.get("is_ioc"), False),
        sighted=str_to_bool(data.get("sighted"), True),
        sightedAt=_sighted_at_millis(ctx, field, data.get("sighted_at")),
        ignoreSimilarity=str_to_bool(data.get("ignore_similarity"), False),
    )

    return [dict(common, data=value) for value in values]
