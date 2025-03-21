# encoding = utf-8

import time
import sys
import datetime
import json
from thehive import create_thehive_instance_modular_input
from thehive4py.query.filters import Between
from thehive4py.query.page import Paginate
from thehive4py.query.sort import Desc
import globals

"""
    IMPORTANT
    Edit only the validate_input and collect_events functions.
    Do not edit any other part in this file.
    This file is generated only once when creating the modular input.
"""
"""
# For advanced users, if you want to create single instance mod input, uncomment this method.
def use_single_instance_mode():
    return True
"""


def validate_input(helper, definition):
    """Implement your own validation logic to validate the input stanza configurations"""
    # This example accesses the modular input variable
    # instance_id = definition.parameters.get('instance_id', None)
    # type = definition.parameters.get('type', None)
    # date = definition.parameters.get('date', None)
    pass


def collect_events(helper, ew):
    """Implement your data collection logic here"""

    globals.initialize_globals()

    # Set the current LOG level
    helper.log_info("[MI-BA-5] LOG level to: " + helper.log_level)
    helper.set_log_level(helper.log_level)

    # Get current stanza information
    input_stanza = helper.get_input_stanza()
    stanza = list(input_stanza.keys())[0]

    helper.log_info(
        '[MI-BA-10] Modular input "{}" for TheHive data started on {}'.format(
            stanza, time.strftime("%D %T")
        )
    )

    # Get the instance connection and initialize settings
    instance_id = helper.get_arg("instance_id")
    helper.log_debug("[MI-BA-15] TheHive instance found: " + str(instance_id))

    modular_input_args = {}
    modular_input_args["backfill_start"] = helper.get_arg("backfill_start")
    modular_input_args["backfill_end"] = helper.get_arg("backfill_end")
    if (
        modular_input_args["backfill_start"] is not None
        and modular_input_args["backfill_end"] is not None
    ):
        modular_input_args["max_size_value"] = (
            int(helper.get_arg("max_size_value"))
            if helper.get_arg("max_size_value") is not None
            and helper.get_arg("max_size_value") != ""
            else 1000
        )
        modular_input_args["fields_removal"] = (
            helper.get_arg("fields_removal")
            if helper.get_arg("fields_removal") is not None
            and helper.get_arg("fields_removal") != ""
            else ""
        )

        # get the previous search results
        (thehive, configuration, logger_file) = create_thehive_instance_modular_input(
            instance_id=instance_id, helper=helper, acronym="MI-BA"
        )
        logger_file.debug(
            id="17", message="Arguments recovered: " + str(modular_input_args)
        )

        logger_file.debug(
            id="20",
            message="TheHive URL instance used after retrieving the configuration: "
            + str(thehive.session.hive_url),
        )
        logger_file.debug(
            id="25",
            message="TheHive connection is ready. Processing modular input parameters...",
        )

        # Retrieve the data
        logger_file.debug(id="36", message=f"Processing type 'audit'...")

        # Prepare to store the new events
        new_events = []

        # Check the interval set
        interval = int(input_stanza[stanza]["interval"])

        if interval == -1:
            # Set the start/end date from parameters
            d1 = int(modular_input_args["backfill_start"])
            d2 = int(modular_input_args["backfill_end"])

            # Multiply by 1,000 for TheHive
            filters = Between("_createdAt", d1 * 1000, d2 * 1000)
            logger_file.debug(
                id="40", message="This filter will be used: " + str(filters)
            )

            new_events = thehive.get_audit_logs_events(
                filters=filters, **modular_input_args
            )

            # Store the events accordingly
            for event in new_events:
                # Index the event
                e = helper.new_event(
                    source="thehive:" + stanza,
                    host=thehive.session.hive_url[8:],
                    index=helper.get_output_index(),
                    sourcetype="thehive:last_created:audit",
                    data=json.dumps(event),
                )
                ew.write_event(e)

            logger_file.info(
                id="70", message=str(len(new_events)) + " events were recovered."
            )
        else:
            logger_file.error(
                id="75",
                message="Interval must be set to -1 (run only once at startup) for backfills",
            )
    else:
        logger_file.error(
            id="80", message="Mandatory parameters for backfill aren't provided"
        )
        return -1
    return 0
