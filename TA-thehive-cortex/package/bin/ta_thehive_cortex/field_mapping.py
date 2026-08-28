# encoding = utf-8
#
# Copyright: LGPLv3 (https://www.gnu.org/licenses/lgpl-3.0.txt)
#
"""How one Splunk field becomes one piece of a TheHive object.

⚠️ This file exists because `parse_events` reached **CC 126** in a single
function: nine sub-responsibilities, five branches with no `else`, three silent
losses. Nobody added complexity to it -- everybody added a field type, one
`elif` at a time, each reasonable on its own day.

The chain that decided what a key *is* now lives in `FIELD_RULES`, and the
chain that decided how a custom field's **value** is encoded lives in
`CUSTOM_FIELD_CODECS`. Both are ordered data rather than nested branches, which
means the next field type is a line in a table and not a deeper `elif`.

⚠️ **Order carries meaning in `FIELD_RULES`.** A composite key wins over a plain
datatype, a datatype wins over a custom field, and the catch-all `other` rule
must stay last. Reordering this list changes behaviour silently -- it is the one
thing here that cannot be checked by reading a single entry.

⚠️ Nothing in this module fixes anything. It was extracted under a ticket that
forbids functional change, and the oddities are preserved on purpose: the
sub-key that fills an observable's message is `description` and not `message`;
a `ttp` value without `::` still raises; the `THC-106` branch is kept although
it appears unreachable. Each of those is its own ticket. A refactoring that
smuggles in a fix cannot be reviewed, because any difference could be either.
"""

from __future__ import annotations

import datetime
import re
from collections import namedtuple

from ttp_catalogue import is_known

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

#: The custom field types this add-on knows how to encode.
#: ⚠️ Used ONLY to decide whether an unmappable value is "a type we do not
#: know" (forward it as text) or "a value that does not fit its declared type"
#: (drop it, and say so). Freezing this list as the list of types TheHive
#: supports is what made GitHub #133: every type TheHive added vanished here.
KNOWN_CUSTOM_TYPES = ("string", "url", "boolean", "integer", "float", "date")

_TRUE = re.compile("^(1|y|Y|t|T|true|True)$")
_FALSE = re.compile("^(0|n|N|f|F|false|False)$")
_EPOCH10 = re.compile("^[0-9]{10}$")
_EPOCH13 = re.compile("^[0-9]{13}$")

#: Separators a single Splunk field may pack several observable values with.
_MULTIVALUE = re.compile(r"[,;|\n]+")


class FieldMappingError(Exception):
    """Anything this module refuses to map, with the field that caused it."""


class UnknownCustomFieldType(FieldMappingError):
    """A custom field whose declared type is not in `KNOWN_CUSTOM_TYPES`.

    ⚠️ Raised nowhere today, and that is deliberate: the current behaviour is to
    forward such a value as text rather than refuse it, because TheHive is the
    authority on its own schema. The type exists so a caller that WANTS to be
    strict has something to catch, instead of re-deriving the condition.
    """

    def __init__(self, field, declared_type, known=KNOWN_CUSTOM_TYPES):
        self.field = field
        self.declared_type = declared_type
        self.known = known
        super().__init__(
            f"custom field '{field}' declares type '{declared_type}', "
            f"which is none of {', '.join(known)}"
        )


# ---------------------------------------------------------------------------
# Value helpers, moved verbatim from the caller
# ---------------------------------------------------------------------------


def extract_field(row, field):
    """The value of `field` in the row, or the field name itself.

    ⚠️ Returning the name is not a fallback, it is a feature: it is what lets an
    argument double as fixed text when it names no column.
    """
    result = field
    if field in row:
        new_value = str(row[field])
        if new_value not in [None, ""]:
            result = new_value
    return result


def str_to_bool(value, default):
    """Coerce a search-result value (always a string after sanitization) into a
    real boolean. TheHive expects native booleans for fields such as `ioc`,
    `sighted` and `ignoreSimilarity`; sending the raw string "1"/"0" makes the
    API reject the whole payload with "Invalid json"."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip()
    if _TRUE.match(text):
        return True
    if _FALSE.match(text):
        return False
    return default


def str_to_epoch_millis(value):
    """A sighting date as milliseconds, or None when it cannot be read."""
    if value is None:
        return None
    text = str(value).strip()
    if _EPOCH13.match(text):
        return int(text)
    if _EPOCH10.match(text):
        return int(text) * 1000
    return None


# ---------------------------------------------------------------------------
# Custom field codecs — one entry per type, instead of one `elif` per type
# ---------------------------------------------------------------------------
#
# A codec takes the raw string and returns `(mapped, value)`. `mapped` False
# means "this value does not fit this type"; the caller decides what to do with
# that, and today it keeps the value readable in the reinjected table.


def _codec_text(value):
    return True, str(value)


def _codec_boolean(value):
    if _TRUE.match(value):
        return True, True
    if _FALSE.match(value):
        return True, False
    return False, None


def _codec_integer(value):
    try:
        return True, int(value)
    except ValueError:  # silent-except: the caller reports it as THC-117
        return False, None


def _codec_float(value):
    try:
        return True, float(value)
    except ValueError:  # silent-except: the caller reports it as THC-117
        return False, None


def _codec_date(value):
    if _EPOCH13.match(value):
        return True, int(value)
    if _EPOCH10.match(value):
        return True, int(value) * 1000
    # ISO-8601 is what a Splunk strftime produces, so it is the most likely
    # shape after an epoch -- and it was the one shape rejected.
    try:
        iso = datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return True, int(iso.timestamp() * 1000)
    except ValueError:  # silent-except: the caller reports it as THC-117
        return False, None


CUSTOM_FIELD_CODECS = {
    "string": _codec_text,
    # "url" (TheHive >= 5.1) carries a plain string value, so it is handled
    # exactly like "string".
    "url": _codec_text,
    "boolean": _codec_boolean,
    "integer": _codec_integer,   # for TheHive4 only
    "float": _codec_float,       # for TheHive4 only
    "date": _codec_date,
}


def encode_custom_field(name, declared_type, value, logger_file):
    """The custom field to send, or None when the value cannot be mapped.

    ⚠️ The two failure modes are NOT the same, and telling them apart is the
    whole point of this function:

    * a type we do not know -> forward the raw value as text (`THC-118`), so a
      type TheHive added after this add-on shipped is not silently dropped;
    * a KNOWN type whose value does not fit it -> return None. The caller keeps
      the key in the reinjected table, which is then the only place the analyst
      can still read the value.
    """
    codec = CUSTOM_FIELD_CODECS.get(declared_type)
    if codec is not None:
        mapped, encoded = codec(value)
        if mapped:
            return {"name": name, "value": encoded}

    if declared_type not in KNOWN_CUSTOM_TYPES:
        logger_file.warn(
            id="THC-118",
            message=f"custom field '{name}' has type '{declared_type}', which this "
            f"add-on does not map; forwarding the raw value as text",
        )
        return {"name": name, "value": str(value)}

    return None


# ---------------------------------------------------------------------------
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


def _extract_ttp(ctx, key, value):
    ctx.consume("ttp")
    # Expected pattern is: tactic::patternId::occurDate
    parts = value.split("::")
    # ⚠️ `parts[2]` is read before any length check, exactly as it always was.
    # A value without `::` raises IndexError and takes the WHOLE alert with it.
    # Preserved verbatim: fixing it here would make this refactoring
    # unreviewable. It has its own ticket.
    try:
        datetime.date.fromisoformat(parts[2])
        date_ok = True
    except ValueError:
        date_ok = False

    # ⚠️ `startswith("T")` accepts `T`, `TOTO` and `T99999` alike. The catalogue
    # is what makes the real check possible.
    known = is_known(parts[1], ctx.catalogue) if len(parts) == 3 else False

    if len(parts) == 3 and parts[1].startswith("T") and date_ok and known:
        new_ttp = {"tactic": parts[0], "patternId": parts[1], "occurDate": parts[2]}
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
    elif len(parts) == 3 and parts[1].startswith("T") and date_ok and not known:
        # Well formed, but the id is not in the catalogue. Say WHICH one:
        # otherwise the user goes hunting for a typo across the whole row.
        ctx.logger_file.error(
            id="THC-122",
            message=(
                f"ttp '{parts[1]}' is not in the MITRE catalogue "
                f"'{ctx.catalog_name}'; the TTP is dropped rather than sent for "
                f"TheHive to reject. Full value: {value}"
            ),
        )
    else:
        ctx.helper.error(
            '[CAA-THC-110-ERROR] ttp field was detected but malformed, expected one '
            'value with the pattern "tactic::patternId::occurDate" with occurDate as '
            '"YYYY-mm-dd", got: {}'.format(value)
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
