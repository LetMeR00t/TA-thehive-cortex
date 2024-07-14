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
import globals
from thehive import TheHive, create_thehive_instance

__author__ = "Alexandre Demeyer"
__maintainer__ = "Alexandre Demeyer"
__email__ = "letmer00t@gmail.com"


def process_event(helper, *args, **kwargs):

    globals.initialize_globals()

    # Set the current LOG level
    helper.log_info("[CAA-THRF-35] LOG level to: " + helper.log_level)
    helper.set_log_level(helper.log_level)

    helper.log_info("[CAA-THRF-36] Alert action thehive_create_a_new_alert started at {}".format(time.time()))

    # Get the instance connection and initialize settings
    instances_id = helper.get_param("thehive_instance_id").split(",")
    helper.log_debug("[CAA-THRF-40] TheHive instances found: " + str(instances_id))

    instances = []
    for instance_id in instances_id:
        instances.append(create_thehive_instance(instance_id=instance_id, settings=helper.settings, logger=helper._logger, acronym="THRF"))

    # Get alert arguments
    alert_args = {}
    # Get string values from alert form
    alert_args["name"] = helper.get_param("name") if helper.get_param("name") else None
    helper.log_debug("[CAA-THRF-55] Arguments recovered: " + str(alert_args))

    for (thehive, configuration, defaults, logger_file, instance_id) in instances:
        # Execute the function
        logger_file.info(id="56",message="Configuration is ready. Running the function...")
        logger_file.debug(id="57",message="TheHive URL instance used after retrieving the configuration: " + str(thehive.session.hive_url))
        logger_file.debug(id="58",message="Processing following instance ID: " + str(instance_id))
        run_function(helper, thehive, alert_args)
    return 0


def run_function(helper, thehive: TheHive, alert_args):
    """ This function is used to run a function using the API, settings and search results """
 
    events = []

    for row in helper.get_events():
        # Splunk makes a bunch of dumb empty multivalue fields
        # replace value by multivalue if required
        thehive.logger_file.debug(id="65",message="Row before pre-processing: " + str(row))
        for key, value in row.items():
            if not key.startswith("__mv_") and "__mv_" + key in row and row["__mv_" + key] not in [None, '']:
                row[key] = [e[1:len(e) - 1] for e in row["__mv_" + key].split(";")]
        # we filter those out here
        row = {key: value for key, value in row.items() if not key.startswith("__mv_") and key not in ["rid"]}
        thehive.logger_file.debug(id="66",message="Row after pre-processing: " + str(row))
        events.append(row)

    # Prepare the query
    input = {"events": events}

    thehive.logger_file.debug(id="70",message="Run function \"{}\" with the events: ".format(alert_args["name"]))

    # Get API and create the case
    response = thehive.function.run(function_name=alert_args["name"], input=input)

    if "result" in response:
        thehive.logger_file.info(id="75",message="Function was run on the events: {}".format(response))
    else:
        thehive.logger_file.error(id="80",message="Function didn't run correctly on the events: {}".format(response))
