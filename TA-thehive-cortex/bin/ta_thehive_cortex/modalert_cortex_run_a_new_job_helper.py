# encoding = utf-8
#!/usr/bin/env python
# Generate Cortex jobs
#
# Author: Alexandre Demeyer <letmer00t@gmail.com>
# Inspired by: Remi Seguy <remg427@gmail.com>
#
# Copyright: LGPLv3 (https://www.gnu.org/licenses/lgpl-3.0.txt)
# Feel free to use the code, but please share the changes you've made

import sys
import time
from cortex import Cortex, create_cortex_instance

__author__ = "Alexandre Demeyer"
__license__ = "LGPLv3"
__version__ = "2.0.0"
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
    cortex_instance_id = helper.get_param("cortex_instance_id")
    helper.log_info("cortex_instance_id={}".format(cortex_instance_id))

    data_field_name = helper.get_param("data_field_name")
    helper.log_info("data_field_name={}".format(data_field_name))

    datatype_field_name = helper.get_param("datatype_field_name")
    helper.log_info("datatype_field_name={}".format(datatype_field_name))

    analyzers = helper.get_param("analyzers")
    helper.log_info("analyzers={}".format(analyzers))

    tlp = helper.get_param("tlp")
    helper.log_info("tlp={}".format(tlp))

    pap = helper.get_param("pap")
    helper.log_info("pap={}".format(pap))


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
    helper.log_info("[CAA-RNJ-40] LOG level to: " + helper.log_level)
    helper.set_log_level(helper.log_level)

    helper.log_info("[CAA-RNJ-41] Alert action cortex_run_a_new_job started at {}".format(time.time()))

    # Get the instance connection and initialize settings
    instance_id = helper.get_param("cortex_instance_id")
    helper.log_debug("[CAA-RNJ-42] Cortex instance found: " + str(instance_id))

    (cortex, configuration, defaults, logger) = create_cortex_instance(instance_id=instance_id, settings=helper.settings, logger=helper._logger)

    helper.log_debug("[CAA-RNJ-43] Cortex connection is ready. Processing job parameters...")

    # Get job arguments
    job_args = {}
    job_args["data"] = helper.get_param("data_field_name") if helper.get_param("data_field_name") else "data"
    job_args["datatype"] = helper.get_param("datatype_field_name") if helper.get_param("datatype_field_name") else "datatype"
    job_args["analyzers"] = helper.get_param("analyzers") if helper.get_param("analyzers") else None
    job_args["tlp"] = int(helper.get_param("tlp")) if helper.get_param("tlp") is not None else 2
    job_args["pap"] = int(helper.get_param("pap")) if helper.get_param("pap") is not None else 2

    helper.log_debug("[CAA-RNJ-44] Arguments recovered: "+str(job_args))

    # Create the job
    helper.log_info("[CAA-RNJ-45] Job preparation is finished. Running the job...")
    run_job(helper, cortex, job_args)
    helper.log_info("[CAA-RNJ-46] Job creation is done.")
    return 0


def run_job(helper, cortex_api, job_args):
    """ This function is used to create a new job using the API, settings and search results """

    app_name = "TA-thehive-cortex"
    jobs = dict()
    analyzers = job_args["analyzers"]
    tlp = job_args["tlp"]
    pap = job_args["pap"]

    events = helper.get_events()
    for row in events:
        # Initialize values
        data = None
        datatype = None
        # Get values of current row
        try:
            data = row[job_args["data"]]
            datatype = row[job_args["datatype"]]
        except Exception as e:
            helper.log_warning(e)
            sys.exit(1)

        cortex_api.addJob(data,datatype,tlp,pap,analyzers)
        helper.log_debug("[CAA-RNJ-55] Adding a new job")
    jobs = cortex_api.runJobs()

    return 0
