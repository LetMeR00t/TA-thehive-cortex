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
import json
import sys
import time

# Third-party imports
from thehive4py.query.filters import Between

# Local application/library specific imports
import globals
from thehive import create_thehive_instance_modular_input

def validate_input(helper, definition):
    """Implement your own validation logic to validate the input stanza configurations"""
    pass

def collect_events(helper, ew):
    """Implement your data collection logic here"""

    globals.initialize_globals()

    # Set the current LOG level
    helper.log_info("[MI-BO-5] LOG level to: " + helper.log_level)
    helper.set_log_level(helper.log_level)

    # Get current stanza information
    input_stanza = helper.get_input_stanza()
    stanza = list(input_stanza.keys())[0]

    helper.log_info(
        '[MI-BO-10] Modular input "{}" for TheHive data started on {}'.format(
            stanza, time.strftime("%D %T")
        )
    )

    # Get the instance connection and initialize settings
    instance_id = helper.get_arg("instance_id")
    helper.log_debug("[MI-BO-15] TheHive instance found: " + str(instance_id))

    modular_input_args = {
        "backfill_start": helper.get_arg("backfill_start"),
        "backfill_end": helper.get_arg("backfill_end"),
        "max_size_value": int(helper.get_arg("max_size_value")) if helper.get_arg("max_size_value") else 1000,
        "fields_removal": helper.get_arg("fields_removal") or ""
    }

    if modular_input_args["backfill_start"] and modular_input_args["backfill_end"]:
        # get the previous search results
        (thehive, configuration, logger_file) = create_thehive_instance_modular_input(
            instance_id=instance_id, helper=helper, acronym="MI-BO"
        )
        logger_file.debug(id="17", message="Arguments recovered: " + str(modular_input_args))

        dates = ["_updatedAt", "_createdAt"]

        for date_field in dates:
            date_mode = ""
            if date_field == "_updatedAt": date_mode = "last_updated"
            elif date_field == "_createdAt": date_mode = "last_created"
            else: date_mode = date_field

            d1 = int(modular_input_args["backfill_start"])
            d2 = int(modular_input_args["backfill_end"])

            filters = Between(date_field, d1 * 1000, d2 * 1000)
            logger_file.debug(id="40", message="This filter will be used: " + str(filters))

            new_events = thehive.get_observables_events(filters=filters, **modular_input_args)

            for event in new_events:
                e = helper.new_event(
                    source="thehive:" + stanza,
                    host=thehive.session.hive_url[8:],
                    index=helper.get_output_index(),
                    sourcetype="thehive:" + date_mode + ":observables",
                    data=json.dumps(event),
                )
                ew.write_event(e)

            logger_file.info(id="70", message=f"{str(len(new_events))} events (date: {date_mode}) were recovered.")
    else:
        logger_file.error(id="80", message="Mandatory parameters for backfill aren't provided")
        return -1
    return 0
