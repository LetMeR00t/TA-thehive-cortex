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


def si_vide(valeur, defaut):
    """Form field: an empty string means "not filled in"."""
    return valeur if valeur else defaut


def si_absent(valeur, defaut):
    """Global setting: only None means "not set"; "" is a real value."""
    return defaut if valeur is None else valeur


def entier(valeur, defaut):
    return int(valeur) if valeur is not None else defaut


def horodatage(champ):
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


def etiquettes(brut):
    """Comma separated, order preserved, duplicates removed."""
    return list(dict.fromkeys(brut.split(","))) if brut else []


def common_args(helper, logger_file):
    """Every argument the case and the alert creators share.

    Each caller adds what only it has: `case_mode` on one side, `alert_mode`,
    `type` and `dashboard` on the other.
    """
    args = {}
    args["unique_id_field"] = si_vide(helper.get_param("unique_id_field"), "oneEvent")
    args["caseTemplate"] = si_vide(helper.get_param("case_template"), None)
    args["source"] = si_vide(helper.get_param("source"), "splunk")
    args["timestamp"] = horodatage(helper.get_param("timestamp_field"))
    args["splunk_sanitize_backslashes"] = si_absent(
        helper.get_global_setting("splunk_sanitize_backslashes"), "ENABLED"
    )
    args["title"] = si_vide(helper.get_param("title"), None)
    args["description"] = si_vide(
        helper.get_param("description"), "No description provided"
    )
    if args["splunk_sanitize_backslashes"] == "ENABLED":
        args["description"] = (
            args["description"].replace("\\n", "\n").replace("\\r", "\r")
        )
    args["tags"] = etiquettes(helper.get_param("tags"))
    logger_file.debug(id="50", message="scope: {} ".format(helper.get_param("scope")))
    args["scope"] = True if int(helper.get_param("scope")) == 0 else False
    args["severity"] = entier(helper.get_param("severity"), 2)
    args["tlp"] = entier(helper.get_param("tlp"), 2)
    args["pap"] = entier(helper.get_param("pap"), 2)
    args["splunk_es_alerts_index"] = si_absent(
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

    ⚠️ These ~20 lines opened all six alert actions, identical except for the
    four-letter acronym woven into two log prefixes. Six copies of a preamble
    is six places to forget when the bootstrap changes.

    `create_thehive_instance` is imported lazily: importing it at module level
    would drag the whole TheHive stack into this module, which the tests read
    for its pure defaulting rules alone.
    """
    import globals
    from modalert_thehive_common import create_thehive_instance

    globals.initialize_globals()

    helper.log_info(f"[CAA-{acronym}-35] LOG level to: " + helper.log_level)
    helper.set_log_level(helper.log_level)

    instances_id = helper.get_param("thehive_instance_id").split(",")
    helper.log_debug(f"[CAA-{acronym}-40] TheHive instances found: " + str(instances_id))

    return [
        create_thehive_instance(
            instance_id=instance_id,
            settings=helper.settings,
            logger=helper._logger,
            acronym=acronym,
            exec_id=helper.exec_id,
        )
        for instance_id in instances_id
    ]
