# encoding = utf-8
#!/usr/bin/env python
# Generate TheHive cases
#
# Author: Alexandre Demeyer <letmer00t@gmail.com>
# Inspired by: Remi Seguy <remg427@gmail.com>
#
# Copyright: LGPLv3 (https://www.gnu.org/licenses/lgpl-3.0.txt)
# Feel free to use the code, but please share the changes you've made

import time
from thehive import TheHive, create_thehive_instance

__author__ = "Alexandre Demeyer"
__maintainer__ = "Alexandre Demeyer"
__email__ = "letmer00t@gmail.com"


def process_event(helper, *args, **kwargs):
    """
    # IMPORTANT
    # Do not remove the anchor macro:start and macro:end lines.
    # These lines are used to generate sample code. If they are
    # removed, the sample code will not be updated when configurations
    # are updated.

    [sample_code_macro:start]

    # The following example gets and sets the log level
    helper.set_log_level(helper.log_level)

    # The following example gets account information
    user_account = helper.get_user_credential("<account_name>")

    # The following example gets the setup parameters and prints them to the log
    cortex_max_jobs = helper.get_global_setting("cortex_max_jobs")
    helper.log_info("cortex_max_jobs={}".format(cortex_max_jobs))
    cortex_sort_jobs = helper.get_global_setting("cortex_sort_jobs")
    helper.log_info("cortex_sort_jobs={}".format(cortex_sort_jobs))
    thehive_default_instance = helper.get_global_setting("thehive_default_instance")
    helper.log_info("thehive_default_instance={}".format(thehive_default_instance))
    thehive_max_cases = helper.get_global_setting("thehive_max_cases")
    helper.log_info("thehive_max_cases={}".format(thehive_max_cases))
    thehive_sort_cases = helper.get_global_setting("thehive_sort_cases")
    helper.log_info("thehive_sort_cases={}".format(thehive_sort_cases))
    thehive_max_alerts = helper.get_global_setting("thehive_max_alerts")
    helper.log_info("thehive_max_alerts={}".format(thehive_max_alerts))
    thehive_sort_alerts = helper.get_global_setting("thehive_sort_alerts")
    helper.log_info("thehive_sort_alerts={}".format(thehive_sort_alerts))
    splunk_es_alerts_index = helper.get_global_setting("splunk_es_alerts_index")
    helper.log_info("splunk_es_alerts_index={}".format(splunk_es_alerts_index))

    # The following example gets the alert action parameters and prints them to the log
    thehive_instance_id = helper.get_param("thehive_instance_id")
    helper.log_info("thehive_instance_id={}".format(thehive_instance_id))

    alert_mode = helper.get_param("alert_mode")
    helper.log_info("alert_mode={}".format(alert_mode))

    unique_id_field = helper.get_param("unique_id_field")
    helper.log_info("unique_id_field={}".format(unique_id_field))

    case_template = helper.get_param("case_template")
    helper.log_info("case_template={}".format(case_template))

    type = helper.get_param("type")
    helper.log_info("type={}".format(type))

    source = helper.get_param("source")
    helper.log_info("source={}".format(source))

    timestamp_field = helper.get_param("timestamp_field")
    helper.log_info("timestamp_field={}".format(timestamp_field))

    title = helper.get_param("title")
    helper.log_info("title={}".format(title))

    description = helper.get_param("description")
    helper.log_info("description={}".format(description))

    tags = helper.get_param("tags")
    helper.log_info("tags={}".format(tags))

    scope = helper.get_param("scope")
    helper.log_info("scope={}".format(scope))

    severity = helper.get_param("severity")
    helper.log_info("severity={}".format(severity))

    tlp_ = helper.get_param("tlp_")
    helper.log_info("tlp_={}".format(tlp_))

    pap_ = helper.get_param("pap_")
    helper.log_info("pap_={}".format(pap_))


    # The following example adds two sample events ("hello", "world")
    # and writes them to Splunk
    # NOTE: Call helper.writeevents() only once after all events
    # have been added
    helper.addevent("hello", sourcetype="sample_sourcetype")
    helper.addevent("world", sourcetype="sample_sourcetype")
    helper.writeevents(index="summary", host="localhost", source="localhost")

    # The following example gets the events that trigger the alert
    events = helper.get_events()
    for event in events:
        helper.log_info("event={}".format(event))

    # helper.settings is a dict that includes environment configuration
    # Example usage: helper.settings["server_uri"]
    helper.log_info("server_uri={}".format(helper.settings["server_uri"]))
    [sample_code_macro:end]
    """
    # Set the current LOG level
    helper.log_info("[CAA-THRF-35] LOG level to: " + helper.log_level)
    helper.set_log_level(helper.log_level)

    helper.log_info("[CAA-THRF-36] Alert action thehive_create_a_new_alert started at {}".format(time.time()))

    # Get the instance connection and initialize settings
    instance_id = helper.get_param("thehive_instance_id")
    helper.log_debug("[CAA-THRF-40] TheHive instance found: " + str(instance_id))

    (thehive, configuration, defaults, logger) = create_thehive_instance(instance_id=instance_id, settings=helper.settings, logger=helper._logger)

    helper.log_debug("[CAA-THRF-41] TheHive URL instance used after retrieving the configuration: " + str(thehive.session.hive_url))
    helper.log_debug("[CAA-THRF-45] TheHive connection is ready. Processing alert parameters...")

    # Get alert arguments
    alert_args = {}
    # Get string values from alert form
    alert_args["name"] = helper.get_param("name") if helper.get_param("name") else None
    helper.log_debug("[CAA-THRF-55] Arguments recovered: " + str(alert_args))

    # Create the alert
    helper.log_info("[CAA-THRF-56] Configuration is ready. Running the function...")
    run_function(helper, thehive, alert_args)
    return 0


def run_function(helper, thehive: TheHive, alert_args):
    """ This function is used to run a function using the API, settings and search results """
 
    events = []

    for row in helper.get_events():
        # Splunk makes a bunch of dumb empty multivalue fields
        # replace value by multivalue if required
        helper.log_debug("[CAA-THRF-65] Row before pre-processing: " + str(row))
        for key, value in row.items():
            if not key.startswith("__mv_") and "__mv_" + key in row and row["__mv_" + key] not in [None, '']:
                row[key] = [e[1:len(e) - 1] for e in row["__mv_" + key].split(";")]
        # we filter those out here
        row = {key: value for key, value in row.items() if not key.startswith("__mv_") and key not in ["rid"]}
        helper.log_debug("[CAA-THRF-66] Row after pre-processing: " + str(row))
        events.append(row)

    # Prepare the query
    input = {"events": events}

    helper.log_debug("[CAA-THRF-70] Run function \"{}\" with the events: ".format(alert_args["name"]))

    # Get API and create the case
    response = thehive.function.run(function_name=alert_args["name"], input=input)

    if "result" in response:
        helper.log_info("[CAA-THRF-75] Function was run on the events: {}".format(response))
    else:
        helper.log_info("[CAA-THRF-76-ERROR] Function didn't run correctly on the events: {}".format(response))
