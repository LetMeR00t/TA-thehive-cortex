# encoding = utf-8
# Author: Alexandre Demeyer <letmer00t@gmail.com>
#
# Copyright: LGPLv3 (https://www.gnu.org/licenses/lgpl-3.0.txt)
# Feel free to use the code, but please share the changes you've made

__author__ = "Alexandre Demeyer"
__license__ = "LGPLv3"
__version__ = "4.0.0"
__maintainer__ = "Alexandre Demeyer"
__email__ = "letmer00t@gmail.com"

import ta_thehive_cortex_declare

# Standard library imports
import datetime
import re
import time

# Third-party imports
from tomark import Tomark

# Local application/library specific imports
from thehive import TheHive4Splunk
from ttp_catalogue import pattern_ids
from datatypes import per_execution_invariants
from thehive4py.types.custom_field import InputCustomField
from thehive4py.types.observable import InputObservable
from thehive4py.types.procedure import InputProcedure

__author__ = "Alexandre Demeyer"
__maintainer__ = "Alexandre Demeyer"
__email__ = "letmer00t@gmail.com"

# The value maps and the per-field helpers now live in `field_mapping`, which
# holds the dispatch table that replaced a 126-branch chain. They are re-exported
# here because `modalert_thehive_add_observables_helper` and
# `modalert_thehive_add_timeline_event_helper` import them from this module, and
# moving a name is not a reason to break three callers.
from field_mapping import (  # noqa: F401  (re-exported on purpose)
    SEVERITY,
    KNOWN_CUSTOM_TYPES,
    extract_field,
    str_to_bool,
    str_to_epoch_millis,
    RowContext,
    dispatch_row,
)
# `TLP`/`PAP`/`build_observables` moved to `observable_builder` (field_mapping
# split a second time); still re-exported here for the same three callers.
from observable_builder import TLP, PAP, build_observables  # noqa: F401


def _normalise_row(row, logger_file):
    """Splunk's multivalue fields flattened, every value a string, `__mv_` gone.

    Splunk emits a parallel `__mv_<field>` column for multivalue fields; TheHive
    has no use for it, and a list reaching the API is rejected outright.
    """
    logger_file.debug(id="THC-61", message="Row before pre-processing: " + str(row))
    for key in list(row):
        if (
            not key.startswith("__mv_")
            and "__mv_" + key in row
            and row["__mv_" + key] not in [None, ""]
        ):
            row[key] = [e[1 : len(e) - 1] for e in row["__mv_" + key].split(";")]

    sanitized = dict()
    for key, value in list(row.items()):
        if not key.startswith("__mv_") and key not in ["rid"]:
            if isinstance(value, list):
                sanitized[key] = ", ".join(map(str, value))
            else:
                sanitized[key] = str(value)

    logger_file.debug(id="THC-62", message="Row after pre-processing: " + str(sanitized))
    return sanitized


def _resolve_source_ref(row, helper, alert_args, reference_time, logger_file):
    """The key that decides which alert a row belongs to.

    ⚠️ Rows sharing a sourceRef are MERGED into one alert, so this is also the
    grouping key -- getting it wrong does not create a wrong alert, it silently
    merges or splits alerts that should not be.
    """
    unique_id_field = alert_args.get("unique_id_field")
    es_mode = (
        alert_args.get("alert_mode") == "es_mode"
        or alert_args.get("case_mode") == "es_mode"
    ) and bool(unique_id_field) and unique_id_field not in row

    if es_mode:
        # Coming from Splunk ES, which carries its own identifier.
        source_ref = row["event_id"] if "event_id" in row else helper.sid
    elif unique_id_field and unique_id_field in row:
        new_source = str(row[unique_id_field])
        if new_source not in [None, ""]:
            source_ref = new_source
            del row[unique_id_field]
        else:
            source_ref = helper.sid + reference_time
    else:
        source_ref = helper.sid + reference_time

    if len(source_ref) > 128:
        logger_file.debug(
            id="THC-63",
            message="original sourceRef: {} was cut as it was a string too long (max 128 char).".format(
                source_ref
            ),
        )
        source_ref = source_ref[0:127]

    logger_file.debug(id="THC-64", message="sourceRef: {} ".format(source_ref))
    return source_ref


def _resolve_title(alert, row, helper, alert_args):
    """The alert title, and the field it consumed if it named one."""
    arg_title = alert_args.get("title")
    if arg_title == "<inheritance>":
        if "search_name" in row:
            # Coming from Splunk ES.
            alert["title"] = row["search_name"]
            del row["search_name"]
        else:
            alert["title"] = helper.settings["search_name"]
    elif arg_title:
        alert["title"] = extract_field(row, arg_title)
        if arg_title in row:
            del row[arg_title]
    else:
        alert["title"] = "Notable event"


def _resolve_description(alert, row, alert_args):
    arg_description = alert_args.get("description")
    if arg_description:
        alert["description"] = extract_field(row, arg_description)
        if arg_description in row:
            del row[arg_description]
    elif "description" in row:
        alert["description"] = row["description"]
        del row["description"]
    else:
        alert["description"] = "No description provided"


def _resolve_scale(alert, row, alert_args, key, field, mapping, fold):
    """One of severity / TLP / PAP, read from the row or from the argument.

    ⚠️ The three were three near-identical eleven-line blocks differing only in
    the map and in `.lower()` versus `.upper()`. That is how the second one
    drifted from the first without anybody noticing.
    """
    raw = row.get(field)
    if raw in mapping:
        alert[key] = mapping[raw]
    elif raw is not None and fold(str(raw)) in mapping:
        alert[key] = mapping[fold(str(raw))]
    else:
        # ⚠️ The row value we could not read stays in the table: the analyst
        # should see what we refused, not just the default we applied.
        alert[key] = alert_args.get(key, 2)
        return
    del row[field]


def _resolve_scales(alert, row, alert_args):
    _resolve_scale(alert, row, alert_args, "severity", "th_severity", SEVERITY, str.lower)
    _resolve_scale(alert, row, alert_args, "tlp", "th_tlp", TLP, str.upper)
    _resolve_scale(alert, row, alert_args, "pap", "th_pap", PAP, str.upper)


def _resolve_timestamp(alert, row, alert_args, logger_file):
    """The alert timestamp in milliseconds, falling back to now.

    ⚠️ Two shapes used to fail the WHOLE alert rather than this one field: a
    non-numeric value ("2026-01-01", which is what a Splunk strftime produces)
    raised ValueError on float(); and a numeric value that is neither ten nor
    thirteen digits left `alert["timestamp"]` unassigned while the log line
    below read it -- a KeyError on a key the code had just failed to write.
    """
    arg_timestamp = alert_args.get("timestamp")
    if not (arg_timestamp and arg_timestamp in row):
        if arg_timestamp:
            logger_file.warn(
                id="THC-86",
                message=f"timestamp_field '{arg_timestamp}' missing; falling back to current time",
            )
        alert["timestamp"] = int(time.time() * 1000)
        return

    raw = row.pop(arg_timestamp)
    epoch = _read_epoch(raw, arg_timestamp, logger_file)
    if epoch is not None:
        alert["timestamp"] = epoch
    else:
        alert["timestamp"] = int(time.time() * 1000)
    logger_file.debug(
        id="THC-85", message="alert timestamp: {} ".format(alert["timestamp"])
    )


def _read_epoch(raw, field_name, logger_file):
    """Milliseconds from a ten or thirteen digit epoch, or None with a reason."""
    try:
        digits = str(int(float(raw)))
    except (TypeError, ValueError):
        logger_file.warn(
            id="THC-87",
            message=f"timestamp_field '{field_name}' holds a non-numeric value "
            f"('{raw}'); falling back to current time",
        )
        return None

    logger_file.debug(id="THC-80", message="new Timestamp from row: {} ".format(digits))
    if re.match("^[0-9]{13}$", digits):
        return int(float(digits))
    if re.match("^[0-9]{10}$", digits):
        return int(float(digits)) * 1000

    logger_file.warn(
        id="THC-88",
        message=f"timestamp_field '{field_name}' is neither a 10 nor a "
        f"13 digit epoch ('{digits}'); falling back to current time",
    )
    return None


def _resolve_ttps(alert, row, ttps):
    """TTPs given explicitly, or failing that the ones Splunk ES annotated."""
    if len(ttps) > 0:
        alert["ttps"] = [InputProcedure(ttp) for ttp in ttps]
        return
    if not (
        "annotations.mitre_attack.mitre_tactic" in row
        and "annotations.mitre_attack" in row
    ):
        return

    tactics = row["annotations.mitre_attack.mitre_tactic"]
    technics = row["annotations.mitre_attack"]
    if not isinstance(tactics, list):
        tactics = [tactics]
    if not isinstance(technics, list):
        technics = [technics]

    date = datetime.datetime.fromtimestamp(
        int(float(row.get("_time", time.time())))
    ).strftime("%Y-%m-%d")

    # Iterate on the shorter of the two: unaligned lists must not raise.
    alert["ttps"] = [
        InputProcedure(
            {"tactic": tactics[i], "patternId": technics[i], "occurDate": date}
        )
        for i in range(min(len(tactics), len(technics)))
    ]


def _store_alert(alert, row, observables, ctx, source_ref, logger_file):
    """Fold one row's harvest into the alert it belongs to."""
    if observables:
        alert["observables"] = [InputObservable(o) for o in observables]
        logger_file.debug(
            id="THC-115", message="observables found for an alert: " + str(observables)
        )
    else:
        alert["observables"] = []
        logger_file.debug(
            id="THC-116",
            message=f"No observable found in current row (sourceRef={source_ref}).",
        )

    alert["customFields"] = [InputCustomField(cf) for cf in ctx.custom_field_values]
    _resolve_ttps(alert, row, ctx.ttps)

    alert["events"] = alert["events"] + [row] if "events" in alert else [row]
    alert["events_keys"] = (
        list(set(alert["events_keys"] + list(row.keys())))
        if "events_keys" in alert
        else list(row.keys())
    )


def _drop_columns_empty_everywhere(alert):
    """A column empty in EVERY event of the alert is noise in the table."""
    for key in list(alert["events_keys"]):
        empty = sum(1 for event in alert["events"] if key not in event or event[key] == "")
        if empty == len(alert["events"]):
            for event in list(alert["events"]):
                if key in event:
                    del event[key]


def _append_results_table(parsed_events, alert_args, logger_file):
    """Reinject the raw events as a Markdown table under the description.

    ⚠️ `events` is always deleted afterwards, whether or not it was rendered:
    it is working state, and handing it back to the caller would put the raw
    Splunk rows into an object nobody expects to carry them.
    """
    for source_ref in parsed_events:
        if alert_args["description_results_enable"]:
            _drop_columns_empty_everywhere(parsed_events[source_ref])
            logger_file.debug(
                id="THC-77", message="Append results to description as markdown table"
            )
            parsed_events[source_ref]["description"] += (
                "\r\n\r\n-----\r\nRaw events:\r\n\r\n"
                + Tomark.table(parsed_events[source_ref]["events"])
            )
        del parsed_events[source_ref]["events"]


def parse_events(helper, thehive: TheHive4Splunk, alert_args):
    """Turn the search results into the alerts or cases to send to TheHive.

    ⚠️ This function used to be 540 lines at **CC 126**, holding nine
    responsibilities at once. It now reads as the sequence it always was: read
    the row, decide which alert it joins, fill the header, dispatch the fields,
    fold the harvest in. The branching that decided what a field *is* lives in
    `field_mapping.FIELD_RULES`, where the next field type is a table entry
    rather than a deeper `elif`.

    Behaviour is unchanged, and that is checked rather than claimed:
    `tests/test_parse_events_characterisation_unit.py` pins it, oddities
    included.
    """
    data_type, custom_fields = per_execution_invariants(thehive)
    # ⚠️ Once per execution, never per row: the catalogue does not change while
    # a batch is being sent, and re-reading it per row would be one HTTP
    # round-trip per row.
    catalogue = pattern_ids(
        thehive, getattr(thehive, "ttp_catalog_name", None), thehive.logger_file
    )
    reference_time = str(int(time.time()))
    parsed_events = dict()

    for raw_row in helper.get_events():
        row = _normalise_row(raw_row, thehive.logger_file)
        source_ref = _resolve_source_ref(
            row, helper, alert_args, reference_time, thehive.logger_file
        )

        # Rows sharing a sourceRef accumulate into one alert, so the harvest of
        # the previous rows is resumed rather than restarted.
        alert = parsed_events.get(source_ref, dict())
        observables = list(alert.get("observables", []))
        ttps = list(alert.get("ttps", []))
        custom_field_values = list(alert.get("customFields", []))

        _resolve_title(alert, row, helper, alert_args)
        _resolve_description(alert, row, alert_args)
        _resolve_scales(alert, row, alert_args)
        _resolve_timestamp(alert, row, alert_args, thehive.logger_file)

        context = RowContext(
            row_sanitized=row,
            data_type=data_type,
            custom_fields=custom_fields,
            alert_args=alert_args,
            catalogue=catalogue,
            logger_file=thehive.logger_file,
            helper=helper,
            ttps=ttps,
            custom_field_values=custom_field_values,
            catalog_name=getattr(thehive, "ttp_catalog_name", "") or "",
        )
        dispatch_row(context, row)
        build_observables(context, observables)

        _store_alert(alert, row, observables, context, source_ref, thehive.logger_file)
        parsed_events[source_ref] = alert

    _append_results_table(parsed_events, alert_args, thehive.logger_file)
    return parsed_events
