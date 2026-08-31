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
import csv
import datetime
import os
import re
import time

# Third-party imports
from tomark import Tomark

# Local application/library specific imports
from thehive import TheHive4Splunk
from ttp_catalogue import pattern_ids
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



#: The KV store collection behind the `thehive_datatypes` lookup.
KV_DATATYPES_COLLECTION = "kv_thehive_datatypes"

#: Its columns, in the order the shipped seed file carries them.
DATATYPE_FIELDS = ["field_name", "field_type", "datatype", "description"]


def legacy_datatypes_csv():
    """Where this add-on wrote its datatype lookup before the KV store.

    The package still ships that file, so a fresh installation seeds itself
    from it; an existing one is read exactly once, so the rows a user
    customised survive the migration."""

    return os.path.join(
        os.environ["SPLUNK_HOME"],
        "etc",
        "apps",
        "TA-thehive-cortex",
        "lookups",
        "thehive_datatypes.csv",
    )


def datatypes_store(thehive: TheHive4Splunk):
    """The KV store collection holding the datatypes, or None.

    ⚠️ None means "I could not reach it", never "it is empty". The two lead to
    opposite decisions -- an unreachable store must not look like a TheHive
    instance that reports no datatype at all."""

    splunk_client = getattr(thehive, "splunk_client", None)
    if splunk_client is None:
        thehive.logger_file.error(
            id="THC-7",
            message=(
                "no Splunk client carried by the TheHive instance: the "
                "datatype lookup cannot be reached in the KV store"
            ),
        )
        return None
    try:
        return splunk_client.kvstore[KV_DATATYPES_COLLECTION].data
    except Exception as e:
        thehive.logger_file.error(
            id="THC-8",
            message=(
                f"KV store collection '{KV_DATATYPES_COLLECTION}' is not "
                f"reachable: {e}"
            ),
        )
        return None


def seed_rows_from_legacy_csv(thehive: TheHive4Splunk):
    """The rows of the CSV lookup, for the one-shot seeding of the collection."""

    filename = legacy_datatypes_csv()
    if not os.path.exists(filename):
        return []
    rows = list()
    try:
        with open(filename, "rt", newline="") as file_object:
            for row in csv.DictReader(file_object):
                if row.get("field_name"):
                    rows.append(
                        {column: row.get(column) or "" for column in DATATYPE_FIELDS}
                    )
    except IOError:
        thehive.logger_file.warn(
            id="THC-9",
            message="{} exists but could not be read; the collection will be seeded from TheHive only, and rows customised there are lost".format(
                filename
            ),
        )
        return []
    if rows:
        thehive.logger_file.info(
            id="THC-14",
            message="seeding '{}' with {} row(s) migrated from {}".format(
                KV_DATATYPES_COLLECTION, len(rows), filename
            ),
        )
    return rows


def create_datatype_lookup(thehive: TheHive4Splunk, force=False):
    """This function is used to create or refresh a datatype lookup.

    A refresh is non-destructive: every existing row (including user-defined
    custom field mappings) is preserved, only datatypes newly reported by
    TheHive are appended.

    ⚠️ The lookup lives in the KV store and no longer in a CSV under
    `etc/apps/TA-thehive-cortex/lookups`. That directory is **replaced on
    every upgrade of the add-on**: the care this function takes to preserve
    customised rows was undone by the next upgrade. Writing there is also
    refused by Splunk Cloud vetting, and never replicated across a search
    head cluster."""

    dataType_dict = dict()
    store = datatypes_store(thehive)
    if store is None:
        return dataType_dict

    try:
        existing_rows = store.query()
    except Exception as e:
        thehive.logger_file.error(
            id="THC-4",
            message="the datatype collection could not be read ({}), refresh aborted to avoid losing its content".format(
                e
            ),
        )
        return dataType_dict

    # First run after the migration: the collection is empty and the CSV this
    # add-on used to write still holds what the user customised.
    if not existing_rows:
        seed = seed_rows_from_legacy_csv(thehive)
        if seed:
            try:
                store.batch_save(*seed)
                existing_rows = seed
            except Exception as e:
                thehive.logger_file.error(
                    id="THC-17",
                    message="the migrated rows could not be written to '{}': {}".format(
                        KV_DATATYPES_COLLECTION, e
                    ),
                )

    if not (force or not existing_rows):
        return dataType_dict

    known_field_names = {
        row.get("field_name") for row in existing_rows if row.get("field_name")
    }

    # Get the list of datatypes from TheHive itself
    try:
        th_datatypes = thehive.observable_type.list()
        thehive.logger_file.debug(
            id="THC-2", message="Datatypes recovered from TheHive: " + str(th_datatypes)
        )

        # Parse the response, keeping only datatypes not already in the lookup
        new_rows = list()
        for dt in th_datatypes:
            dataType_dict[dt["name"]] = dt["name"]
            if dt["name"] not in known_field_names:
                new_rows.append(
                    {
                        "field_name": dt["name"],
                        "field_type": "observable",
                        "datatype": dt["name"],
                        "description": "",
                    }
                )

        # Only the new rows are written. Nothing existing is ever rewritten,
        # which is what makes a refresh unable to undo a customisation.
        if new_rows:
            try:
                store.batch_save(*new_rows)
            except Exception as e:
                thehive.logger_file.error(
                    id="THC-5",
                    message="FATAL {} new datatype(s) could not be written to '{}': {}".format(
                        len(new_rows), KV_DATATYPES_COLLECTION, e
                    ),
                )
    except Exception as e:
        thehive.logger_file.error(
            id="THC-6",
            message="Could not recover datatypes from TheHive API: " + str(e)
        )
        if not force:
            # If it's not a force refresh, we can't do anything
            raise e

    return dataType_dict


#: Per-execution memo. See `per_execution_invariants` below for why.
_DATATYPES_MEMO: dict = {}

#: Same, for the custom field definitions TheHive holds.
_CUSTOM_FIELDS_MEMO: dict = {}


def reset_per_execution_cache():
    """Forget what was memoised. For the tests, and for a long-lived process."""
    _DATATYPES_MEMO.clear()
    _CUSTOM_FIELDS_MEMO.clear()


def per_execution_invariants(thehive: TheHive4Splunk):
    """The datatypes and the custom field definitions, read at most once.

    ⚠️ Neither changes while a batch of results is being sent, yet both were
    re-read for every row by the "add observables" action, which calls
    parse_events once per row. Measured on the shipped code, for 1000 rows:
    ~1000 extra HTTP round-trips to TheHive for the custom fields, ~1000 full
    re-reads of the datatypes CSV — and, when that file is more than 24 hours
    old, ~1000 attempts to rewrite it under $SPLUNK_HOME/etc/apps from a
    worker.

    The memo is keyed on the instance's URL: a search may address several
    TheHive instances in one execution, and they do not share a catalogue.
    """
    key = getattr(getattr(thehive, "session", None), "hive_url", "?")
    if key not in _DATATYPES_MEMO:
        _DATATYPES_MEMO[key] = get_datatype_dict(thehive)
    if key not in _CUSTOM_FIELDS_MEMO:
        _CUSTOM_FIELDS_MEMO[key] = {
            cf["name"]: cf for cf in thehive.custom_field.list()
        }
    return _DATATYPES_MEMO[key], _CUSTOM_FIELDS_MEMO[key]


def get_datatype_dict(thehive: TheHive4Splunk):
    """This function is used to recover information from a lookup that contain datatypes

    ⚠️ The 24-hour "smart sync" disappeared with the file whose age it read:
    a KV store document carries no modification time. The refresh now happens
    once per execution instead -- `per_execution_invariants` memoises this
    call, so the cost is one extra round-trip to TheHive per search, exactly
    like the custom field definitions read beside it. A datatype added in
    TheHive is therefore visible on the next search rather than the next day."""

    dataType_dict = dict()
    store = datatypes_store(thehive)
    if store is None:
        return dataType_dict

    try:
        create_datatype_lookup(thehive, force=True)
    except Exception as e:
        # An unreachable API is not a reason to lose the mapping already
        # stored: it is only a reason not to enrich it this time.
        thehive.logger_file.warn(
            id="THC-12",
            message=f"API refresh failed ({e}). Falling back to the rows already in the collection."
        )

    try:
        rows = store.query()
    except Exception as e:
        thehive.logger_file.error(
            id="THC-16",
            message=f"collection '{KV_DATATYPES_COLLECTION}' is empty, malformed or not readable: {e}",
        )
        return dataType_dict

    if not rows:
        thehive.logger_file.error(
            id="THC-13",
            message=f"API refresh failed and collection '{KV_DATATYPES_COLLECTION}' holds no datatype."
        )
        return dataType_dict

    for row in rows:
        if row.get("field_type") == "observable" and row.get("field_name"):
            dataType_dict[row["field_name"]] = row.get("datatype")
    thehive.logger_file.debug(
        id="THC-15",
        message="dataType_dict built from '{}' ({} datatype(s))".format(
            KV_DATATYPES_COLLECTION, len(dataType_dict)
        ),
    )
    return dataType_dict


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
