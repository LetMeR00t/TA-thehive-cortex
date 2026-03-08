
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
    helper.log_info("[MI-BAC-5] LOG level to: " + helper.log_level)
    helper.set_log_level(helper.log_level)

    # Get current stanza information
    input_stanza = helper.get_input_stanza()
    stanza = list(input_stanza.keys())[0]

    helper.log_info(
        '[MI-BAC-10] Modular input "{}" for TheHive data started on {}'.format(
            stanza, time.strftime("%D %T")
        )
    )

    # Get the instance connection and initialize settings
    instance_id = helper.get_arg("instance_id")
    helper.log_debug("[MI-BAC-15] TheHive instance found: " + str(instance_id))

    # get the previous search results
    (thehive, configuration, logger_file) = create_thehive_instance_modular_input(
        instance_id=instance_id, helper=helper, acronym="MI-BAC"
    )

    modular_input_args = {
        "backfill_start": str(helper.get_arg("backfill_start")),
        "backfill_end": str(helper.get_arg("backfill_end")),
        "max_size_value": int(helper.get_arg("max_size_value")) if helper.get_arg("max_size_value") else 1000,
        "fields_removal": helper.get_arg("fields_removal") or "",
        "additional_information": helper.get_arg("additional_information") or [],
        "extra_data": helper.get_arg("extra_data") or []
    }

    types = helper.get_arg("type") or ["alerts", "cases"]
    dates = ["_updatedAt", "_createdAt", "startDate"]

    if modular_input_args["backfill_start"] and modular_input_args["backfill_end"]:
        for input_type in types:
            modular_input_args["type"] = input_type
            for date_field in dates:
                modular_input_args["date"] = date_field
                
                date_mode = ""
                if date_field == "_updatedAt": date_mode = "last_updated"
                elif date_field == "_createdAt": date_mode = "last_created"
                elif date_field == "startDate": date_mode = "last_started"
                else: date_mode = date_field

                logger_file.debug(id="36", message=f"Backfilling type '{input_type}' with date '{date_field}'...")

                sortby = Desc(date_field)
                
                d1 = int(modular_input_args["backfill_start"])
                d2 = int(modular_input_args["backfill_end"])

                filters = Between(date_field, d1 * 1000, d2 * 1000)
                logger_file.debug(id="40", message="This filter will be used: " + str(filters))

                new_events = []
                if input_type == "cases":
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
    else:
        logger_file.error(id="80", message="Mandatory parameters for backfill aren't provided")
        return -1
    return 0
