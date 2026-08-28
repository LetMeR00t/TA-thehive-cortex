# encoding = utf-8
#
# Copyright: LGPLv3 (https://www.gnu.org/licenses/lgpl-3.0.txt)
#
"""How one Splunk field becomes one piece of a TheHive object.

⚠️ This file exists because `parse_events` reached **CC 126** in a single
function: nine sub-responsibilities, five branches with no `else`, three silent
losses. Nobody added complexity to it -- everybody added a field type, one
`elif` at a time, each reasonable on its own day.

The chain that decided what a key *is* lives here, in `FIELD_RULES`. The chain
that decided what a **value** is worth moved to `value_codecs` the day this file
crossed its own line ceiling: adding a TheHive type touches that file only,
adding a kind of field touches this one only.

⚠️ **Order carries meaning in `FIELD_RULES`.** A composite key wins over a plain
datatype, a datatype wins over a custom field, and the catch-all `other` rule
must stay last. Reordering this list changes behaviour silently -- it is the one
thing here that cannot be checked by reading a single entry.

⚠️ This module was extracted under a ticket forbidding functional change, and
the oddities are preserved on purpose: the sub-key that fills an observable's
message is `description` and not `message`; the `THC-106` branch is kept
although it appears unreachable. Each of those is its own ticket. A refactoring
that smuggles in a fix cannot be reviewed, because any difference could be
either. *(The one exception is the `ttp` crash, and it was NOT fixed here: it
went out as #36 and came back as its own commit.)*
"""

from __future__ import annotations

import datetime
import re
from collections import namedtuple

from ttp_catalogue import is_known
from value_codecs import (  # noqa: F401  (re-exported: `modalert_thehive_common` imports them here)
    KNOWN_CUSTOM_TYPES,
    FieldMappingError,
    UnknownCustomFieldType,
    encode_custom_field,
    extract_field,
    str_to_bool,
    str_to_epoch_millis,
)

# ---------------------------------------------------------------------------
# The value maps. They live here rather than in the caller so this module has
# no import back into it -- `modalert_thehive_common` re-exports them, so the
# three helpers that import them from there keep working.
# ---------------------------------------------------------------------------

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

SEVERITY = {
    "low": 1, "medium": 2, "high": 3, "critical": 4,
    "1": 1, "2": 2, "3": 3, "4": 4,
}

#: Separators a single Splunk field may pack several observable values with.
_MULTIVALUE = re.compile(r"[,;|\n]+")

# The dispatch table
# ---------------------------------------------------------------------------

#: `match(ctx, key, value) -> bool` decides whether this rule owns the key;
#: `extract(ctx, key, value) -> None` consumes it. Both take the same triple so
#: a rule can be read on one line.
FieldRule = namedtuple("FieldRule", "name match extract")


class RowContext:
    """Everything one row's dispatch reads and writes.

    Passing this instead of eleven parameters is what keeps a rule readable;
    it is also what makes the rules testable one by one, which the nested chain
    never was.
    """

    def __init__(self, row_sanitized, data_type, custom_fields, alert_args,
                 catalogue, logger_file, helper, ttps, custom_field_values,
                 catalog_name=""):
        self.row_sanitized = row_sanitized
        self.data_type = data_type
        self.custom_fields = custom_fields
        self.alert_args = alert_args
        self.catalogue = catalogue
        self.catalog_name = catalog_name
        self.logger_file = logger_file
        self.helper = helper
        self.observables_data = {}
        # ⚠️ Both lists come from the caller and are MUTATED in place: rows
        # sharing a sourceRef accumulate into the same alert, so a fresh list
        # here would silently drop everything the previous rows contributed.
        self.custom_field_values = custom_field_values
        self.ttps = ttps

    def consume(self, key):
        """Drop a key from the table reinjected into the description.

        ⚠️ Only ever called where the value was actually used. Deleting before
        knowing how to handle a value is what lost it twice -- absent from the
        object AND gone from the table the analyst reads.
        """
        if key in self.row_sanitized:
            del self.row_sanitized[key]

    def enrich_observable(self, field, sub_key, value, datatype):
        entry = self.observables_data.setdefault(field, {})
        entry[sub_key] = value
        entry["datatype"] = datatype


def _match_composite(ctx, key, value):
    return ":" in key


def _extract_composite(ctx, key, value):
    ctx.logger_file.debug(id="THC-91", message=f"composite fieldvalue detected: {key}")
    main_key, sub_key = key.split(":", 1)
    if main_key in ctx.data_type:
        ctx.enrich_observable(main_key, sub_key, value, ctx.data_type[main_key])
        ctx.logger_file.debug(
            id="THC-92",
            message="field: {} enriched with the information {} set to ".format(
                main_key, sub_key, value
            ),
        )
        ctx.consume(key)
    else:
        # ⚠️ The terminal branch that was missing for years. The prefix names no
        # known datatype, so we cannot build an observable -- but the value
        # stays readable in the description table, and the key is NOT consumed.
        ctx.logger_file.warn(
            id="THC-93",
            message=f"composite key '{key}' was NOT mapped: '{main_key}' is "
            f"not a known datatype. The raw value is kept in the description table.",
        )


def _match_datatype(ctx, key, value):
    return key in ctx.data_type


def _extract_datatype(ctx, key, value):
    if not ctx.alert_args["description_results_keep_observable"]:
        ctx.consume(key)
    ctx.logger_file.debug(id="THC-95", message="key is an observable: {} ".format(key))
    ctx.enrich_observable(key, "value", value, ctx.data_type[key])


def _match_custom_field(ctx, key, value):
    return key in ctx.custom_fields


def _extract_custom_field(ctx, key, value):
    declared_type = ctx.custom_fields[key]["type"]
    ctx.logger_file.debug(
        id="THC-96",
        message="key is a custom field: {}, with type {} ".format(key, declared_type),
    )
    custom_field = encode_custom_field(key, declared_type, value, ctx.logger_file)
    if custom_field is not None:
        ctx.custom_field_values.append(custom_field)
        ctx.consume(key)
    else:
        ctx.logger_file.warn(
            id="THC-117",
            message=f"custom field '{key}' was NOT mapped: type '{declared_type}' is not "
            f"handled, or value '{value}' does not match it. The raw value is kept in "
            f"the description table.",
        )


def _match_ttp(ctx, key, value):
    return key == "ttp"


def _malformed_ttp(ctx, value):
    """Report a `ttp` this add-on cannot read, and let the alert live.

    ⚠️ One unreadable field is a reason to drop that field, never a reason to
    drop the alert -- let alone the other rows of the same batch, which had
    nothing wrong with them.
    """
    ctx.helper.error(
        '[CAA-THC-110-ERROR] ttp field was detected but malformed, expected one '
        'value with the pattern "tactic::patternId::occurDate" with occurDate as '
        '"YYYY-mm-dd", got: {}'.format(value)
    )


def _extract_ttp(ctx, key, value):
    ctx.consume("ttp")
    # Expected pattern is: tactic::patternId::occurDate
    parts = value.split("::")

    # ⚠️ THE LENGTH CHECK COMES FIRST, and that is the whole fix (#36).
    # `parts[2]` used to be read before it, inside a `try` that catches only
    # ValueError -- so a value without `::` raised IndexError and propagated:
    # not this TTP lost, but the WHOLE alert action, every row of the batch
    # with it, in a message naming neither the row nor the field. The degraded
    # path already existed three lines below; the indexed read short-circuited
    # it before it could run.
    if len(parts) != 3:
        _malformed_ttp(ctx, value)
        return

    tactic, pattern_id, occur_date = parts

    try:
        datetime.date.fromisoformat(occur_date)
        date_ok = True
    except ValueError:
        date_ok = False

    # ⚠️ `startswith("T")` accepts `T`, `TOTO` and `T99999` alike. The catalogue
    # is what makes the real check possible.
    if not (pattern_id.startswith("T") and date_ok):
        _malformed_ttp(ctx, value)
        return

    if not is_known(pattern_id, ctx.catalogue):
        # Well formed, but the id is not in the catalogue. Say WHICH one:
        # otherwise the user goes hunting for a typo across the whole row.
        ctx.logger_file.error(
            id="THC-122",
            message=(
                f"ttp '{pattern_id}' is not in the MITRE catalogue "
                f"'{ctx.catalog_name}'; the TTP is dropped rather than sent for "
                f"TheHive to reject. Full value: {value}"
            ),
        )
        return

    new_ttp = {"tactic": tactic, "patternId": pattern_id, "occurDate": occur_date}
    if new_ttp not in ctx.ttps:
        ctx.ttps.append(new_ttp)
        ctx.logger_file.debug(
            id="THC-108",
            message="ttp was parsed correctly and added to the alert: {}".format(value),
        )
    else:
        ctx.logger_file.debug(
            id="THC-109",
            message="ttp already exist, ignoring duplicates: {}".format(value),
        )


def _match_other(ctx, key, value):
    return ctx.alert_args["scope"] is False


def _extract_other(ctx, key, value):
    if key in ctx.row_sanitized:
        ctx.logger_file.debug(
            id="THC-105",
            message="key is added as another observable (scope is False): {}".format(key),
        )
        # As we are taking a field as an "other" datatype, the value is built
        # differently: the analyst needs the field name to read it.
        entry = ctx.observables_data.setdefault(key, {})
        entry["value"] = key + ": " + value
        entry["datatype"] = "other"
        entry["tags"] = "value:" + value
    else:
        # ⚠️ Appears unreachable: every deletion before the loop also removes
        # the key from the snapshot it iterates, and every deletion inside the
        # loop targets the key being processed. Kept because proving dead code
        # dead is a separate ticket, and removing it here would be a behaviour
        # change nobody asked this ticket for.
        ctx.logger_file.warn(
            id="THC-106",
            message='key is used by TheHive as an internal field (scope is False): {}. '
            'Key ignored to be added as an "other" observable.'.format(key),
        )


#: ⚠️ ORDER IS PRIORITY. First match wins, and the catch-all stays last.
FIELD_RULES = [
    FieldRule("composite", _match_composite, _extract_composite),
    FieldRule("datatype", _match_datatype, _extract_datatype),
    FieldRule("custom_field", _match_custom_field, _extract_custom_field),
    FieldRule("ttp", _match_ttp, _extract_ttp),
    FieldRule("other", _match_other, _extract_other),
]


def dispatch_row(ctx, row):
    """Send every non-empty field of the row to the first rule that owns it.

    ⚠️ The iteration is over a SNAPSHOT (`list(row.items())`), and `row` is the
    same object as `ctx.row_sanitized`. A key consumed before this call is
    therefore not visited at all -- which is why several branches below can look
    reachable and never be.
    """
    for key, value in list(row.items()):
        if value == "":
            continue
        ctx.logger_file.debug(id="THC-90", message=f"field to process: {key}")
        for rule in FIELD_RULES:
            if rule.match(ctx, key, value):
                rule.extract(ctx, key, value)
                break


# ---------------------------------------------------------------------------
# Observables
# ---------------------------------------------------------------------------


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
        sightedAt=str_to_epoch_millis(data.get("sighted_at")),
        ignoreSimilarity=str_to_bool(data.get("ignore_similarity"), False),
    )

    return [dict(common, data=value) for value in values]
