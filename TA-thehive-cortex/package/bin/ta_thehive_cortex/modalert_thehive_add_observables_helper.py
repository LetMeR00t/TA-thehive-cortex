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

# Third-party imports
from thehive4py.errors import TheHiveError
from thehive4py.types.observable import InputObservable

# Local application/library specific imports
import globals
from modalert_thehive_common import parse_events, TLP, PAP, extract_field
from thehive import TheHive4Splunk, create_thehive_instance

__author__ = "Alexandre Demeyer"
__maintainer__ = "Alexandre Demeyer"
__email__ = "letmer00t@gmail.com"


def process_event(helper, *args, **kwargs):

    globals.initialize_globals()

    # Set the current LOG level
    helper.log_info("[CAA-THAO-10] LOG level to: " + helper.log_level)
    helper.set_log_level(helper.log_level)

    # Get the instance connection and initialize settings
    instance_id = helper.get_param("thehive_instance_id")
    thehive, configuration, defaults, logger_file, instance_id = create_thehive_instance(
        instance_id=instance_id,
        settings=helper.settings,
        logger=helper._logger,
        acronym="THAO",
        exec_id=helper.exec_id,
    )

    # Get alert arguments for parse_events
    alert_args = {}
    alert_args["scope"] = True if int(helper.get_param("scope")) == 0 else False
    alert_args["description_results_enable"] = False
    alert_args["description_results_keep_observable"] = True

    # Parse events to get observables
    # We call parse_events which will return observables found in the rows
    parsed_events = parse_events(helper, thehive, alert_args)

    # Iterate over each search result
    events = helper.get_events()
    # Since parse_events might group events by sourceRef, but here we want to process row by row
    # and match them with their specific target IDs.
    
    # Actually, parse_events returns a dict of sourceRef -> alert_dict
    # We need to map back which row corresponds to which sourceRef.
    # But wait, if we have multiple rows, parse_events might have grouped them.
    # For "Add observables", we usually want to process each row independently if the target ID is in the row.
    
    # Let's re-read the rows and for each row, find its observables from the parsed_events.
    # To do this safely, we can call parse_events for each row separately.

    for row in events:
        # Resolve target IDs
        id_field_raw = helper.get_param("id_field")
        target_ids_str = extract_field(row, id_field_raw)
        target_ids = [tid.strip() for tid in target_ids_str.split(",") if tid.strip()]
        
        # Resolve target type
        target_type_raw = helper.get_param("target_type_field")
        target_type = extract_field(row, target_type_raw).lower() if target_type_raw else "alert"
        if target_type not in ["alert", "case"]:
            logger_file.warning(id="THAO-20", message=f"Invalid target type '{target_type}', defaulting to 'alert'")
            target_type = "alert"

        # Resolve case IDs if needed
        if target_type == "case":
            target_ids = [thehive.resolve_case_id(tid) for tid in target_ids]

        # Resolve metadata
        tags_raw = helper.get_param("tags_field")
        tags_str = extract_field(row, tags_raw) if tags_raw else ""
        override_tags = [t.strip() for t in tags_str.split(",") if t.strip()]

        tlp_raw = helper.get_param("tlp_field")
        tlp_val = extract_field(row, tlp_raw) if tlp_raw else "AMBER"
        override_tlp = TLP.get(str(tlp_val).upper(), TLP.get(str(tlp_val), TLP["AMBER"]))

        pap_raw = helper.get_param("pap_field")
        pap_val = extract_field(row, pap_raw) if pap_raw else "AMBER"
        override_pap = PAP.get(str(pap_val).upper(), PAP.get(str(pap_val), PAP["AMBER"]))

        ioc_raw = helper.get_param("ioc_field")
        ioc_val = str(extract_field(row, ioc_raw)).lower() if ioc_raw else "false"
        override_ioc = ioc_val in ["true", "1", "yes", "y", "t"]

        sighted_raw = helper.get_param("sighted_field")
        sighted_val = str(extract_field(row, sighted_raw)).lower() if sighted_raw else "false"
        override_sighted = sighted_val in ["true", "1", "yes", "y", "t"]

        sighted_date_raw = helper.get_param("sighted_date_field")
        sighted_date_val = extract_field(row, sighted_date_raw) if sighted_date_raw else None
        
        override_sighted_at = None
        if override_sighted:
            if sighted_date_val:
                try:
                    # Convert Splunk epoch (s) to ms
                    override_sighted_at = int(float(sighted_date_val) * 1000)
                except (ValueError, TypeError):
                    logger_file.warning(id="THAO-25", message=f"Invalid sighted date value '{sighted_date_val}', defaulting to now().")
                    override_sighted_at = int(time.time() * 1000)
            else:
                # No date provided but sighted is true, use now
                override_sighted_at = int(time.time() * 1000)

        # Get observables for THIS row
        # We temporarily mock the events in the helper to only return the current row
        original_get_events = helper.get_events
        helper.get_events = lambda: [row]
        row_parsed = parse_events(helper, thehive, alert_args)
        helper.get_events = original_get_events # Restore

        observables = []
        for srcRef in row_parsed:
            observables.extend(row_parsed[srcRef].get("observables", []))

        if not observables:
            logger_file.info(id="THAO-30", message="No observables found in current row, skipping.")
            continue

        # Process each target ID
        for tid in target_ids:
            # Validate format ^~[0-9]+$
            if not re.match(r"^~[0-9]+$", tid):
                logger_file.error(id="THAO-35", message=f"Invalid target ID format: '{tid}'. Must match ^~[0-9]+$. Skipping this ID.")
                continue

            # For each observable found in the row
            for obs in observables:
                # obs is an InputObservable (from thehive4py)
                # We need to apply overrides if they were provided in the alert action
                
                # InputObservable stores data in a dict internally or as attributes depending on version
                # In thehive4py v2 (used here), it's a dict-like object
                
                if tags_raw:
                    obs["tags"] = override_tags
                if tlp_raw:
                    obs["tlp"] = override_tlp
                if pap_raw:
                    obs["pap"] = override_pap
                if ioc_raw:
                    obs["ioc"] = override_ioc
                if sighted_raw:
                    obs["sighted"] = override_sighted
                if sighted_date_raw and override_sighted_at:
                    obs["sightedAt"] = override_sighted_at

                # Reinforced Audit
                logger_file.info(id="THAO-40", message=f"Adding observable to {target_type} {tid}: Type={obs.get('dataType')}, Data={obs.get('data')}, TLP={obs.get('tlp')}, PAP={obs.get('pap')}, IOC={obs.get('ioc')}, Sighted={obs.get('sighted')}")

                try:
                    if target_type == "alert":
                        thehive.alert.create_observable(alert_id=tid, observable=obs)
                    else:
                        thehive.case.create_observable(case_id=tid, observable=obs)
                    logger_file.info(id="THAO-50", message=f"Successfully added observable to {target_type} {tid}")
                except Exception as e:
                    # Catch 400 "already exists" and log as WARNING
                    # We check: message text, status_code attribute, or response object status_code
                    status_code = getattr(e, 'status_code', None)
                    if status_code is None and hasattr(e, 'response'):
                        status_code = getattr(e.response, 'status_code', None)
                    
                    error_msg = str(e).lower()
                    is_duplicate = "already exists" in error_msg or "duplicate" in error_msg or status_code in [400, 409]
                    
                    if is_duplicate:
                        logger_file.warning(id="THAO-60", message=f"Observable already exists in {target_type} {tid} (Status={status_code}). Skipping.")
                    else:
                        # Log the full error context for debugging
                        response_text = ""
                        if hasattr(e, 'response'):
                            try:
                                response_text = f" | Response: {e.response.text}"
                            except: pass
                        logger_file.error(id="THAO-70", message=f"Failed to add observable to {target_type} {tid}: {str(e)}{response_text}")

    return 0
