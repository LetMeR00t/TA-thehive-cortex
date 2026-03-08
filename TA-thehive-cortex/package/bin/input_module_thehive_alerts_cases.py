
# encoding = utf-8

import time
import sys
import datetime
import json
from thehive import create_thehive_instance_modular_input
from thehive4py.query.filters import Between
from thehive4py.query.sort import Desc
import globals

def validate_input(helper, definition):
    """Implement your own validation logic to validate the input stanza configurations"""
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

    # Get arguments
    types = helper.get_arg("type")
    if types is None:
        types = ["alerts", "cases"]
    
    # We'll use a fixed set of dates to iterate over as in the original script
    # but since UCC might only provide what's selected, we adapt.
    dates = ["_updatedAt", "_createdAt", "startDate"] # Default list to check

    modular_input_args = {
        "max_size_value": int(helper.get_arg("max_size_value")) if helper.get_arg("max_size_value") else 1000,
        "fields_removal": helper.get_arg("fields_removal") or "",
        "additional_information": helper.get_arg("additional_information") or [],
        "extra_data": helper.get_arg("extra_data") or []
    }

    for input_type in types:
        modular_input_args["type"] = input_type
        for date_field in dates:
            modular_input_args["date"] = date_field
            
            date_mode = ""
            if date_field == "_updatedAt": date_mode = "last_updated"
            elif date_field == "_createdAt": date_mode = "last_created"
            elif date_field == "startDate": date_mode = "last_started"
            else: date_mode = date_field

            logger_file.debug(id="36", message=f"Processing type '{input_type}' with date '{date_field}'...")

            sortby = Desc(date_field)
            interval = int(input_stanza[stanza].get("interval", 60))
            now = datetime.datetime.timestamp(datetime.datetime.now())
            d2 = now - now % 60
            d1 = d2 - interval

            filters = Between(date_field, d1 * 1000, d2 * 1000)
            logger_file.debug(id="40", message="This filter will be used: " + str(filters))

            new_events = []
            if input_type == "cases":
                # Filter extra data for cases
                case_extra_data = [ed for ed in modular_input_args["extra_data"] if ed in [
                    "owningOrganisation", "procedureCount", "actionRequired", "status",
                    "observableStats", "taskStats", "alerts", "isOwner", "shareCount",
                    "links", "contributors", "permissions", "computed.handlingDurationInSeconds",
                    "computed.handlingDuration", "computed.handlingDurationInMinutes",
                    "computed.handlingDurationInHours", "computed.handlingDurationInDays",
                    "alertCount", "attachmentCount"
                ]]
                
                (new_events, events_tasks) = thehive.get_cases_events(
                    filters=filters,
                    sortby=sortby,
                    **{**modular_input_args, "extra_data": case_extra_data}
                )

                for task in events_tasks:
                    e = helper.new_event(
                        source="thehive:" + stanza,
                        host=thehive.session.hive_url[8:],
                        index=helper.get_output_index(),
                        sourcetype="thehive:" + date_mode + ":case_tasks",
                        data=json.dumps(task),
                    )
                    ew.write_event(e)

            elif input_type == "alerts":
                alert_extra_data = [ed for ed in modular_input_args["extra_data"] if ed in ["caseNumber", "importDate", "status", "procedureCount"]]
                new_events = thehive.get_alerts_events(
                    filters=filters,
                    **{**modular_input_args, "extra_data": alert_extra_data}
                )

            for event in new_events:
                e = helper.new_event(
                    source="thehive:" + stanza,
                    host=thehive.session.hive_url[8:],
                    index=helper.get_output_index(),
                    sourcetype="thehive:" + date_mode + ":" + input_type,
                    data=json.dumps(event),
                )
                ew.write_event(e)

            logger_file.info(id="70", message=f"{str(len(new_events))} events (type: {input_type}, date: {date_mode}) were recovered.")

    return 0
