# encoding = utf-8
# Author: Alexandre Demeyer <letmer00t@gmail.com>
#
# Copyright: LGPLv3 (https://www.gnu.org/licenses/lgpl-3.0.txt)
# Feel free to use the code, but please share the changes you've made

"""The `thehive_datatypes` lookup: which Splunk field maps to which TheHive
observable type, kept in the KV store and read at most once per execution.

Split out of `modalert_thehive_common` (#24). ⚠️ Tests that replace one of
these functions must patch THIS module: `per_execution_invariants` looks
`get_datatype_dict` up here, so a patch on `modalert_thehive_common` would be
silently inert -- which is why nothing here is re-exported from there.
"""

# Standard library imports
import csv
import os

# Local application/library specific imports
from thehive import TheHive4Splunk


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
