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

    # Set the current LOG level
    helper.log_info("[CAA-RNJ-40] LOG level to: " + helper.log_level)
    helper.set_log_level(helper.log_level)

    helper.log_info(
        "[CAA-RNJ-41] Alert action cortex_run_a_new_job started on {}".format(
            time.time()
        )
    )

    # Get the instance connection and initialize settings
    instance_id = helper.get_param("cortex_instance_id")
    helper.log_debug("[CAA-RNJ-42] Cortex instance found: " + str(instance_id))

    (cortex, configuration, defaults, logger_file) = create_cortex_instance(
        instance_id=instance_id,
        settings=helper.settings,
        logger=helper._logger,
        acronym="RNJ",
    )

    logger_file.debug(
        id="43", message="Cortex connection is ready. Processing job parameters..."
    )

    # Get job arguments
    job_args = {}
    job_args["data"] = (
        helper.get_param("data_field_name")
        if helper.get_param("data_field_name")
        else "data"
    )
    job_args["datatype"] = (
        helper.get_param("datatype_field_name")
        if helper.get_param("datatype_field_name")
        else "datatype"
    )
    job_args["analyzers"] = (
        helper.get_param("analyzers") if helper.get_param("analyzers") else None
    )
    job_args["tlp"] = (
        int(helper.get_param("tlp")) if helper.get_param("tlp") is not None else 2
    )
    job_args["pap"] = (
        int(helper.get_param("pap")) if helper.get_param("pap") is not None else 2
    )

    logger_file.debug(id="44", message="Arguments recovered: " + str(job_args))

    # Create the job
    logger_file.info(id="45", message="Job preparation is finished. Running the job...")
    run_job(helper, cortex, job_args)
    logger_file.info(id="46", message="Job creation is done.")
    return 0


def run_job(helper, cortex_api, job_args):
    """This function is used to create a new job using the API, settings and search results"""

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

        cortex_api.addJob(data, datatype, tlp, pap, analyzers)
        helper.log_debug("[CAA-RNJ-55] Adding a new job")
    jobs = cortex_api.runJobs()

    return 0
