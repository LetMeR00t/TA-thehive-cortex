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
    helper.log_info("[MI-THAC-5] LOG level to: " + helper.log_level)
    helper.set_log_level(helper.log_level)

    # Get current stanza information
    input_stanza = helper.get_input_stanza()
    stanza = list(input_stanza.keys())[0]

    helper.log_info(
        '[MI-THAC-10] Modular input "{}" for TheHive data started on {}'.format(
            stanza, time.strftime("%D %T")
        )
    )

    # Get the instance connection and initialize settings
    instance_id = helper.get_arg("instance_id")
    helper.log_debug("[MI-THAC-15] TheHive instance found: " + str(instance_id))

    # get the previous search results
    (thehive, configuration, logger_file) = create_thehive_instance_modular_input(
        instance_id=instance_id, helper=helper, acronym="MI-THAC"
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

    # Get alert arguments
    modular_input_args = {}
    # Get string values from the input form
    for type_object in helper.get_arg("type"):
        modular_input_args["type"] = type_object
        for date in helper.get_arg("date"):
            modular_input_args["date"] = date
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
            modular_input_args["additional_information"] = helper.get_arg(
                "additional_information"
            )
            modular_input_args["extra_data"] = (
                helper.get_arg("extra_data")
                if helper.get_arg("extra_data") is not None
                and helper.get_arg("extra_data") != ""
                else []
            )
            input_type = modular_input_args["type"]
            logger_file.debug(
                id="30", message="Arguments recovered: " + str(modular_input_args)
            )

            date_mode = None
            if modular_input_args["date"] == "_updatedAt":
                date_mode = "last_updated"
            elif modular_input_args["date"] == "_createdAt":
                date_mode = "last_created"
            elif modular_input_args["date"] == "startDate":
                date_mode = "last_started"
            else:
                date_mode = modular_input_args["date"]
            # Retrieve the data
            logger_file.debug(
                id="35", message="Configuration is ready. Collecting the data..."
            )

            # Retrieve the data
            logger_file.debug(id="36", message=f"Processing type '{input_type}'...")

            # Prepare to store the new events
            new_events = []
            sortby = Desc(modular_input_args["date"])

            # Check the interval set
            interval = int(input_stanza[stanza]["interval"])

            # Calculate d2 which is the latest date
            now = datetime.datetime.timestamp(datetime.datetime.now())

            ## Round it to the minute
            d2 = now - now % 60

            # Calculate d1 which is the earliest date
            d1 = d2 - interval

            # Multiply by 1,000 for TheHive
            filters = Between(modular_input_args["date"], d1 * 1000, d2 * 1000)
            logger_file.debug(
                id="40", message="This filter will be used: " + str(filters)
            )

            if modular_input_args["type"] == "cases":
                ## CASES ##
                # Filter extra data only for cases
                modular_input_args["extra_data"] = [
                    ed
                    for ed in modular_input_args["extra_data"]
                    if ed
                    in [
                        "owningOrganisation",
                        "procedureCount",
                        "actionRequired",
                        "status",
                        "observableStats",
                        "taskStats",
                        "alerts",
                        "isOwner",
                        "shareCount",
                        "links",
                        "contributors",
                        "permissions",
                        "computed.handlingDurationInSeconds",
                        "computed.handlingDuration",
                        "computed.handlingDurationInMinutes",
                        "computed.handlingDurationInHours",
                        "computed.handlingDurationInDays",
                        "alertCount",
                        "attachmentCount",
                        "contributors",
                    ]
                ]
                (new_events, events_tasks) = thehive.get_cases_events(
                    filters=filters,
                    sortby=sortby,
                    **modular_input_args,
                )

                # Store the events accordingly
                for task in events_tasks:
                    # Index the event
                    e = helper.new_event(
                        source="thehive:" + stanza,
                        host=thehive.session.hive_url[8:],
                        index=helper.get_output_index(),
                        sourcetype="thehive:" + date_mode + ":tasks",
                        data=json.dumps(task),
                    )
                    ew.write_event(e)

            elif modular_input_args["type"] == "alerts":
                ## ALERTS ##
                # Filter extra data only for alerts
                modular_input_args["extra_data"] = [
                    ed
                    for ed in modular_input_args["extra_data"]
                    if ed in ["caseNumber", "importDate", "status", "procedureCount"]
                ]
                new_events = thehive.get_alerts_events(
                    filters=filters,
                    **modular_input_args,
                )

            # Store the events accordingly
            for event in new_events:
                # Index the event
                e = helper.new_event(
                    source="thehive:" + stanza,
                    host=thehive.session.hive_url[8:],
                    index=helper.get_output_index(),
                    sourcetype="thehive:"
                    + date_mode
                    + ":"
                    + modular_input_args["type"],
                    data=json.dumps(event),
                )
                ew.write_event(e)

            logger_file.info(
                id="70",
                message=f"{str(len(new_events))} events (type: {type_object}, date: {date_mode}) were recovered.",
            )

    return 0
