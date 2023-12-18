# encoding = utf-8
#!/usr/bin/env python
# Generate TheHive cases
#
# Author: Alexandre Demeyer <letmer00t@gmail.com>
# Inspired by: Remi Seguy <remg427@gmail.com>
#
# Copyright: LGPLv3 (https://www.gnu.org/licenses/lgpl-3.0.txt)
# Feel free to use the code, but please share the changes you've made

import re
import time
from  modalert_thehive_common import parse_events
from thehive import TheHive, create_thehive_instance
from thehive4py.types.case import InputCase
from thehive4py.errors import TheHiveError

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
    helper.log_info("[CAA-THCC-35] LOG level to: " + helper.log_level)
    helper.set_log_level(helper.log_level)

    # Get the instance connection and initialize settings
    instance_id = helper.get_param("thehive_instance_id")
    helper.log_debug("[CAA-THCC-40] TheHive instance found: " + str(instance_id))

    (thehive, configuration, defaults, logger) = create_thehive_instance(instance_id=instance_id, settings=helper.settings, logger=helper._logger)

    helper.log_debug("[CAA-THCC-41] TheHive URL instance used after retrieving the configuration: " + str(thehive.session.hive_url))
    helper.log_debug("[CAA-THCC-45] TheHive connection is ready. Processing alert parameters...")

    # Get alert arguments
    alert_args = {}
    # Get string values from alert form
    alert_args["case_mode"] = helper.get_param("case_mode") if helper.get_param("case_mode") else "es_mode" 
    alert_args["unique_id_field"] = helper.get_param("unique_id_field") if helper.get_param("unique_id_field") else "oneEvent" 
    alert_args["caseTemplate"] = helper.get_param("case_template") if helper.get_param("case_template") else None
    alert_args["source"] = helper.get_param("source") if helper.get_param("source") else "splunk"
    if not helper.get_param("timestamp_field"):
        alert_args['timestamp'] = int(time.time() * 1000)
    else:
        alert_args['timestamp'] = helper.get_param("timestamp_field")
        epoch10 = re.match("^[0-9]{10}$", alert_args['timestamp'])
        if epoch10 is not None:
            alert_args['timestamp'] = int(alert_args['timestamp']) * 1000

    alert_args["title"] = helper.get_param("title") if helper.get_param("title") else None
    alert_args["description"] = helper.get_param("description") if helper.get_param("description") else "No description provided"
    alert_args["tags"] = list(dict.fromkeys(helper.get_param("tags").split(","))) if helper.get_param("tags") else []
    helper.log_debug("[CAA-THCC-50] scope: {} ".format(helper.get_param("scope")))
    alert_args["scope"] = True if int(helper.get_param("scope")) == 0 else False
    # Get numeric values from alert form
    alert_args["severity"] = int(helper.get_param("severity")) if helper.get_param("severity") is not None else 2
    alert_args["tlp"] = int(helper.get_param("tlp")) if helper.get_param("tlp") is not None else 2
    alert_args["pap"] = int(helper.get_param("pap")) if helper.get_param("pap") is not None else 2
    alert_args["splunk_es_alerts_index"] = helper.get_global_setting("splunk_es_alerts_index") if helper.get_global_setting("splunk_es_alerts_index") is not None else "summary"
    alert_args["description_results_enable"] = True if int(helper.get_param("description_results_enable")) == 1 else False
    alert_args["description_results_keep_observable"] = True if int(helper.get_param("description_results_keep_observable")) == 1 else False
    helper.log_debug("[CAA-THCC-55] Arguments recovered: " + str(alert_args))

    # Create the alert
    helper.log_info("[CAA-THCC-56] Configuration is ready. Creating the alert...")
    create_case(helper, thehive, configuration, alert_args)
    return 0



def create_case(helper, thehive: TheHive, configuration, alert_args):
    """ This function is used to create the alert using the API, settings and search results """
 
    # Parse events
    cases = parse_events(helper, thehive, configuration, alert_args)

    # actually send the request to create the alert; fail gracefully
    for srcRef in cases.keys():
        # Create the Alert object
        case = InputCase(
            title=cases[srcRef]['title'],
            date=int(cases[srcRef]['timestamp']),
            description=cases[srcRef]['description'],
            tags=alert_args['tags'],
            severity=cases[srcRef]['severity'],
            tlp=cases[srcRef]['tlp'],
            pap=cases[srcRef]['pap'],
            customFields=cases[srcRef]['customFields'],
            source=alert_args['source'],
            caseTemplate=alert_args['caseTemplate'],
            sourceRef=srcRef,
            externalLink=helper.settings["results_link"]
        )

        helper.log_debug("[CAA-THCC-120] Processing case: " + str(case))
        # Get API and create the case
        new_case = None
        try:
            new_case = thehive.case.create(case)
        except TheHiveError as e:
            helper.log_error(
                "[CAA-THCC-126-ERROR] TheHive case creation has failed. "
                "url={}, data={}, content={}, error={}"
                .format(thehive.session.hive_url, str(case), str(new_case), str(e))
            )

        if new_case is not None:
            if "_id" in new_case:
                # log response status
                helper.log_info(
                    "[CAA-THCC-125] TheHive case #{} is successfully created on url={}".format(new_case["number"],thehive.session.hive_url)
                )

            else:
                # somehow we got a bad response code from thehive
                helper.log_error(
                    "[CAA-THCC-126-ERROR] TheHive case creation has failed. "
                    "url={}, data={}, content={}"
                    .format(thehive.session.hive_url, str(case), str(new_case))
                )

            # Processing Observables if any
            if "observables" in cases[srcRef]:
                for observable in cases[srcRef]['observables']:
                    response = thehive.observable.create_in_case(case_id=new_case["_id"],observable=observable)
                    
                    if "failure" in response:
                        # somehow we got a bad response code from thehive
                        helper.log_error(
                            "[CAA-THCC-135-ERROR] TheHive observable update on recent case creation has failed. "
                            "url={}, data={}, content={}, observable={}, error={}"
                            .format(thehive.session.hive_url, str(case), str(response), str(observable), str(response["failure"]))
                        ) 
                    else:
                        response = response[0]
                        # log response status
                        helper.log_info(
                            "[CAA-THCC-130] TheHive case {} was successfully updated with the observable {} on url={}".format(new_case["_id"],response["data"].replace(".","[.]"),thehive.session.hive_url)
                        )

            
            # Processing TTPs if any
            if "ttps" in cases[srcRef]:
                
                response = thehive.case.create_procedures(case_id=new_case["_id"], procedures=cases[srcRef]["ttps"])[0]

                if "_id" in response:
                    # log response status
                    helper.log_info(
                        "[CAA-THCA-130] TheHive case {} was successfully updated with the TTPs on url={}".format(new_case["_id"],thehive.session.hive_url)
                    )

                else:
                    # somehow we got a bad response code from thehive
                    helper.log_error(
                        "[CAA-THCA-135-ERROR] TheHive TTPs update on recent case creation has failed. "
                        "url={}, data={}, content={}, ttp={}"
                        .format(thehive.session.hive_url, str(case), str(response), str(cases[srcRef]["ttps"])))
