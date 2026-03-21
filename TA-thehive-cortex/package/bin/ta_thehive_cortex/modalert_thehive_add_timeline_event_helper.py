# encoding = utf-8
# Author: Alexandre Demeyer <letmer00t@gmail.com>
#
# Copyright: LGPLv3 (https://www.gnu.org/licenses/lgpl-3.0.txt)
# Feel free to use the code, but please share the changes you've made

__author__ = "Alexandre Demeyer"
__license__ = "LGPLv3"
__version__ = "4.1.0"
__maintainer__ = "Alexandre Demeyer"
__email__ = "letmer00t@gmail.com"

import ta_thehive_cortex_declare

# Standard library imports
import os
import re
import time

# Local application/library specific imports
import globals
from modalert_thehive_common import extract_field
from thehive import create_thehive_instance

def process_event(helper, *args, **kwargs):

    globals.initialize_globals()

    # Set the current LOG level
    helper.log_info("[CAA-THTE-10] LOG level to: " + helper.log_level)
    helper.set_log_level(helper.log_level)

    # Get the instance connection and initialize settings
    instance_id = helper.get_param("thehive_instance_id")
    thehive, configuration, defaults, logger_file, instance_id = create_thehive_instance(
        instance_id=instance_id,
        settings=helper.settings,
        logger=helper._logger,
        acronym="THTE",
        exec_id=helper.exec_id,
    )

    # Iterate over each search result
    events = helper.get_events()

    for row in events:
        # Resolve Case ID (internal ID or number)
        case_id_raw = helper.get_param("case_id")
        case_id_input = extract_field(row, case_id_raw)
        case_id = thehive.resolve_case_id(case_id_input)
        
        if not case_id:
            logger_file.warning(id="THTE-20", message="No case ID resolved for result, skipping.")
            continue

        # Resolve Title
        title_raw = helper.get_param("event_title")
        if title_raw == "<inheritance>":
            title = row.get("search_name", helper.settings.get("search_name", "Splunk Event"))
        else:
            title = extract_field(row, title_raw)

        # Resolve Description
        description_raw = helper.get_param("event_description")
        description = extract_field(row, description_raw)

        # Resolve Dates (Splunk often provides Epoch seconds, TheHive expects Epoch ms)
        def resolve_date(param_name):
            val_raw = helper.get_param(param_name)
            if not val_raw: return None
            val = extract_field(row, val_raw)
            if not val or val == val_raw: # If extract_field returned the input because not in row
                # Check if the input itself is a date
                pass
            
            try:
                # If it looks like 10 digits, it's seconds
                if re.match(r"^\d{10}$", str(val)):
                    return int(val) * 1000
                # If it looks like 13 digits, it's ms
                if re.match(r"^\d{13}$", str(val)):
                    return int(val)
                # Float support
                return int(float(val) * 1000)
            except (ValueError, TypeError):
                # Only log warning if it was NOT the raw parameter name (which might be empty or just a label)
                if val and not re.match(r"^[a-zA-Z_]+$", str(val)):
                    logger_file.warning(id="THTE-30", message=f"Invalid date format for {param_name}: {val}")
                return None

        date = resolve_date("event_date")
        endDate = resolve_date("event_endDate")

        try:
            thehive.create_custom_timeline_event(
                case_id=case_id,
                title=title,
                description=description,
                date=date,
                endDate=endDate
            )
        except Exception as e:
            logger_file.error(id="THTE-ERR", message=f"Failed to create timeline event for case {case_id}: {str(e)}")
