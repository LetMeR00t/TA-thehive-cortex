# encoding = utf-8
#
# Copyright: LGPLv3 (https://www.gnu.org/licenses/lgpl-3.0.txt)
#
"""Read the alert action form into the arguments both creators need.

⚠️ These ~110 lines existed twice, in the case and the alert helper, and the
pattern `helper.get_param(x) if helper.get_param(x) else default` was written
out about twenty-five times per copy -- calling `get_param` **twice** for every
single field.

Two defaulting rules are in play and they are NOT interchangeable, which is
exactly why writing them out by hand fifty times is a bad idea:

* `if value` -- an EMPTY string falls back to the default. Used for form
  fields, where "not filled in" arrives as "".
* `if value is not None` -- an empty string is KEPT. Used for global settings,
  where "" is a deliberate value.

The functions below name the two rules, so the choice is visible at each field
instead of hiding in the shape of a ternary.
"""

import re
import time


def default_if_blank(value, defaut):
    """Form field: an empty string means "not filled in"."""
    return value if value else defaut


def default_if_none(value, defaut):
    """Global setting: only None means "not set"; "" is a real value."""
    return defaut if value is None else value


def as_int(value, defaut):
    return int(value) if value is not None else defaut


def event_timestamp(champ):
    """The event date, in milliseconds.

    ⚠️ Preserved exactly, including its rough edge: a value that is neither
    empty nor a 10-digit epoch is passed through as the RAW STRING, and blows
    up later in whoever converts it. Fixing that belongs to the parse_events
    work, not here -- this module must not change behaviour while it removes
    duplication.
    """
    if not champ:
        return int(time.time() * 1000)
    if re.match("^[0-9]{10}$", champ) is not None:
        return int(champ) * 1000
    return champ


def split_tags(raw):
    """Comma separated, order preserved, duplicates removed."""
    return list(dict.fromkeys(raw.split(","))) if raw else []


def common_args(helper, logger_file):
    """Every argument the case and the alert creators share.

    Each caller adds what only it has: `case_mode` on one side, `alert_mode`,
    `type` and `dashboard` on the other.
    """
    args = {}
    args["unique_id_field"] = default_if_blank(helper.get_param("unique_id_field"), "oneEvent")
    args["caseTemplate"] = default_if_blank(helper.get_param("case_template"), None)
    args["source"] = default_if_blank(helper.get_param("source"), "splunk")
    args["timestamp"] = event_timestamp(helper.get_param("timestamp_field"))
    args["splunk_sanitize_backslashes"] = default_if_none(
        helper.get_global_setting("splunk_sanitize_backslashes"), "ENABLED"
    )
    args["title"] = default_if_blank(helper.get_param("title"), None)
    args["description"] = default_if_blank(
        helper.get_param("description"), "No description provided"
    )
    if args["splunk_sanitize_backslashes"] == "ENABLED":
        args["description"] = (
            args["description"].replace("\\n", "\n").replace("\\r", "\r")
        )
    args["tags"] = split_tags(helper.get_param("tags"))
    logger_file.debug(id="50", message="scope: {} ".format(helper.get_param("scope")))
    args["scope"] = True if int(helper.get_param("scope")) == 0 else False
    args["severity"] = as_int(helper.get_param("severity"), 2)
    args["tlp"] = as_int(helper.get_param("tlp"), 2)
    args["pap"] = as_int(helper.get_param("pap"), 2)
    args["splunk_es_alerts_index"] = default_if_none(
        helper.get_global_setting("splunk_es_alerts_index"), "summary"
    )
    args["description_results_enable"] = (
        True if int(helper.get_param("description_results_enable")) == 1 else False
    )
    args["description_results_keep_observable"] = (
        True
        if int(helper.get_param("description_results_keep_observable")) == 1
        else False
    )
    args["attach_results"] = int(helper.get_param("attach_results"))
    args["attach_format"] = int(helper.get_param("attach_format"))
    return args


# --- Bootstrap shared by every alert action ---------------------------------

def prepare_instances(helper, acronym):
    """Set the log level and open one TheHive connection per configured id.

    ⚠️ Only the two creator actions (case, alert) call this. The other three
    TheHive actions (run_function, add_observables, add_timeline_event) open
    their instance through `create_thehive_instance` directly and repeat the
    ~4 lines of bootstrap this function wraps (log level, `globals.
    initialize_globals()`, splitting `thehive_instance_id`) inline instead --
    a leftover from #22 flagged again in #32, not yet folded in.

    ⚠️ `create_thehive_instance` lives in `thehive`, NOT in
    `modalert_thehive_common`. Getting that wrong is an ImportError raised on
    the first useful line of both creation alert actions -- and no test caught
    it, because none of them executed this function at all.

    It is imported lazily: importing it at module level would drag the whole
    TheHive stack into this module, which the tests read for its pure
    defaulting rules alone.
    """
    import globals
    from thehive import create_thehive_instance

    globals.initialize_globals()

    helper.log_info(f"[CAA-{acronym}-35] LOG level to: " + helper.log_level)
    helper.set_log_level(helper.log_level)

    instance_ids = helper.get_param("thehive_instance_id").split(",")
    helper.log_debug(f"[CAA-{acronym}-40] TheHive instances found: " + str(instance_ids))

    return [
        create_thehive_instance(
            instance_id=instance_id,
            settings=helper.settings,
            logger=helper._logger,
            acronym=acronym,
            exec_id=helper.exec_id,
        )
        for instance_id in instance_ids
    ]
