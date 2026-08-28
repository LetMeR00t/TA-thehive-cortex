# encoding = utf-8
#
# Copyright: LGPLv3 (https://www.gnu.org/licenses/lgpl-3.0.txt)
#
"""Reading ONE value: what a Splunk string is worth as a TheHive field.

⚠️ Split out of `field_mapping` (project-management#24) the day that file
crossed its own ceiling. The two halves answer different questions and change
for different reasons:

* `field_mapping` decides what a KEY is -- an observable, a custom field, a TTP;
* this file decides what a VALUE is worth once the key is known.

Adding a TheHive type touches this file only. Adding a kind of field touches
the other only. That is the whole reason for the line between them.
"""

from __future__ import annotations

import datetime
import re


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
