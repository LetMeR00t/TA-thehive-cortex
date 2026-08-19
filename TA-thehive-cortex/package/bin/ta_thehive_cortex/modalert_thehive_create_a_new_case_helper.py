# encoding = utf-8
# Author: Alexandre Demeyer <letmer00t@gmail.com>
#
# Copyright: LGPLv3 (https://www.gnu.org/licenses/lgpl-3.0.txt)
# Feel free to use the code, but please share the changes you've made

__author__ = "Alexandre Demeyer"
__license__ = "LGPLv3"
__version__ = "4.0.0"
__maintainer__ = "Alexandre Demeyer"
__email__ = "letmer00t@gmail.com"

import ta_thehive_cortex_declare

# Standard library imports
import re
import shutil
import time

# Third-party imports
from thehive4py.errors import TheHiveError
from thehive4py.types.case import InputCase

from attachment_builder import AttachmentError, build_attachment
from creation_retry import create_with_retry

# Local application/library specific imports
import globals
from modalert_thehive_common import parse_events
from thehive import TheHive4Splunk, create_thehive_instance

__author__ = "Alexandre Demeyer"
__maintainer__ = "Alexandre Demeyer"
__email__ = "letmer00t@gmail.com"


def process_event(helper, *args, **kwargs):

    globals.initialize_globals()

    # Set the current LOG level
    helper.log_info("[CAA-THCC-35] LOG level to: " + helper.log_level)
    helper.set_log_level(helper.log_level)

    # Get the instance connection and initialize settings
    instances_id = helper.get_param("thehive_instance_id").split(",")
    helper.log_debug("[CAA-THCC-40] TheHive instances found: " + str(instances_id))

    instances = []
    for instance_id in instances_id:
        instances.append(
            create_thehive_instance(
                instance_id=instance_id,
                settings=helper.settings,
                logger=helper._logger,
                acronym="THCC",
                exec_id=helper.exec_id,
            )
        )

    for thehive, configuration, defaults, logger_file, instance_id in instances:
        # Get alert arguments
        alert_args = {}
        # Get string values from alert form
        alert_args["case_mode"] = (
            helper.get_param("case_mode")
            if helper.get_param("case_mode")
            else "es_mode"
        )
        alert_args["unique_id_field"] = (
            helper.get_param("unique_id_field")
            if helper.get_param("unique_id_field")
            else "oneEvent"
        )
        alert_args["caseTemplate"] = (
            helper.get_param("case_template")
            if helper.get_param("case_template")
            else None
        )
        alert_args["source"] = (
            helper.get_param("source") if helper.get_param("source") else "splunk"
        )
        if not helper.get_param("timestamp_field"):
            alert_args["timestamp"] = int(time.time() * 1000)
        else:
            alert_args["timestamp"] = helper.get_param("timestamp_field")
            epoch10 = re.match("^[0-9]{10}$", alert_args["timestamp"])
            if epoch10 is not None:
                alert_args["timestamp"] = int(alert_args["timestamp"]) * 1000

        alert_args["splunk_sanitize_backslashes"] = (
            helper.get_global_setting("splunk_sanitize_backslashes")
            if helper.get_global_setting("splunk_sanitize_backslashes") is not None
            else "ENABLED"
        )
        alert_args["title"] = (
            helper.get_param("title") if helper.get_param("title") else None
        )
        alert_args["description"] = (
            helper.get_param("description")
            if helper.get_param("description")
            else "No description provided"
        )
        # Check if we need to sanitize backslashes
        if alert_args["splunk_sanitize_backslashes"] == "ENABLED":
            alert_args["description"] = (
                alert_args["description"].replace("\\n", "\n").replace("\\r", "\r")
            )
        alert_args["tags"] = (
            list(dict.fromkeys(helper.get_param("tags").split(",")))
            if helper.get_param("tags")
            else []
        )
        logger_file.debug(
            id="50", message="scope: {} ".format(helper.get_param("scope"))
        )
        alert_args["scope"] = True if int(helper.get_param("scope")) == 0 else False
        # Get numeric values from alert form
        alert_args["severity"] = (
            int(helper.get_param("severity"))
            if helper.get_param("severity") is not None
            else 2
        )
        alert_args["tlp"] = (
            int(helper.get_param("tlp")) if helper.get_param("tlp") is not None else 2
        )
        alert_args["pap"] = (
            int(helper.get_param("pap")) if helper.get_param("pap") is not None else 2
        )
        alert_args["splunk_es_alerts_index"] = (
            helper.get_global_setting("splunk_es_alerts_index")
            if helper.get_global_setting("splunk_es_alerts_index") is not None
            else "summary"
        )
        alert_args["description_results_enable"] = (
            True if int(helper.get_param("description_results_enable")) == 1 else False
        )
        alert_args["description_results_keep_observable"] = (
            True
            if int(helper.get_param("description_results_keep_observable")) == 1
            else False
        )
        alert_args["attach_results"] = int(helper.get_param("attach_results"))
        alert_args["attach_format"] = int(helper.get_param("attach_format"))
        logger_file.debug(id="55", message="Arguments recovered: " + str(alert_args))

        # Create the case
        logger_file.info(
            id="56", message="Configuration is ready. Creating the case..."
        )
        logger_file.debug(
            id="57",
            message="TheHive URL instance used after retrieving the configuration: "
            + str(thehive.session.hive_url),
        )
        logger_file.debug(
            id="58", message="Processing following instance ID: " + str(instance_id)
        )
        create_case(
            helper,
            thehive,
            alert_args,
            max_retry=int(defaults["MAX_CREATION_RETRY"]),
            attachment_prefix=defaults["ATTACHMENT_PREFIX"],
        )
    return 0


def create_case(
    helper,
    thehive: TheHive4Splunk,
    alert_args,
    max_retry: int = 2,
    attachment_prefix: str = "events_",
):
    """This function is used to create the alert using the API, settings and search results"""

    # Parse events
    cases = parse_events(helper, thehive, alert_args)

    # actually send the request to create the alert; fail gracefully
    for srcRef in cases.keys():
        # Create the Alert object
        case = InputCase(
            title=cases[srcRef]["title"],
            date=int(cases[srcRef]["timestamp"]),
            description=cases[srcRef]["description"],
            tags=alert_args["tags"],
            severity=cases[srcRef]["severity"],
            tlp=cases[srcRef]["tlp"],
            pap=cases[srcRef]["pap"],
            customFields=cases[srcRef]["customFields"],
            source=alert_args["source"],
            caseTemplate=alert_args["caseTemplate"],
            sourceRef=srcRef,
            externalLink=helper.settings["results_link"],
        )

        thehive.logger_file.debug(id="120", message="Processing case: " + str(case))
        # Get API and create the case
        new_case = create_with_retry(
            create=lambda: thehive.case.create(case),
            max_retry=max_retry,
            logger_file=thehive.logger_file,
            ids={"retry": "126", "exhausted": "127"},
            contexte=lambda: f"TheHive case url={thehive.session.hive_url}, data={case}",
        )

        if new_case is not None:
            if "_id" in new_case:
                # log response status
                thehive.logger_file.info(
                    id="130",
                    message="TheHive case #{} is successfully created on url={}".format(
                        new_case["number"], thehive.session.hive_url
                    ),
                )

            else:
                # somehow we got a bad response code from thehive
                thehive.logger_file.error(
                    id="135",
                    message="TheHive case creation has failed. "
                    "url={}, data={}, content={}".format(
                        thehive.session.hive_url, str(case), str(new_case)
                    ),
                )

            # Processing Observables if any
            if "observables" in cases[srcRef]:
                for observable in cases[srcRef]["observables"]:
                    try:
                        response = thehive.observable.create_in_case(
                            case_id=new_case["_id"], observable=observable
                        )

                        if "failure" in response:
                            # somehow we got a bad response code from thehive
                            thehive.logger_file.error(
                                id="135",
                                message="TheHive observable update on recent case creation has failed. "
                                "url={}, data={}, content={}, observable={}, error={}".format(
                                    thehive.session.hive_url,
                                    str(case),
                                    str(response),
                                    str(observable),
                                    str(response["failure"]),
                                ),
                            )
                        else:
                            response = response[0]
                            # log response status
                            thehive.logger_file.info(
                                id="130",
                                message="TheHive case {} was successfully updated with the observable {} on url={}".format(
                                    new_case["_id"],
                                    response["data"].replace(".", "[.]"),
                                    thehive.session.hive_url,
                                ),
                            )
                    except Exception as e:
                        # Catch 400 "already exists" and log as WARNING
                        status_code = getattr(e, 'status_code', None)
                        if status_code is None and hasattr(e, 'response'):
                            status_code = getattr(e.response, 'status_code', None)
                        
                        error_msg = str(e).lower()
                        is_duplicate = "already exists" in error_msg or "duplicate" in error_msg or status_code in [400, 409]
                        
                        if is_duplicate:
                            thehive.logger_file.warning(
                                id="136",
                                message="Observable already exists in case {} (Status={}). Skipping. url={}, data={}".format(
                                    new_case["_id"], status_code, thehive.session.hive_url, str(observable)
                                ),
                            )
                        else:
                            # Log the full error context for debugging
                            response_text = ""
                            if hasattr(e, 'response'):
                                try:
                                    response_text = f" | Response: {e.response.text}"
                                except Exception:  # silent-except: best-effort detail, the error itself is logged just below
                                    pass
                            thehive.logger_file.error(
                                id="137",
                                message="TheHive observable update on recent case creation has failed. "
                                "url={}, data={}, observable={}, error={}{}".format(
                                    thehive.session.hive_url,
                                    str(case),
                                    str(observable),
                                    str(e),
                                    response_text
                                ),
                            )

            # Processing TTPs if any
            if "ttps" in cases[srcRef]:

                response = thehive.case.create_procedures(
                    case_id=new_case["_id"], procedures=cases[srcRef]["ttps"]
                )[0]

                if "_id" in response:
                    # log response status
                    thehive.logger_file.info(
                        id="135",
                        message="TheHive case {} was successfully updated with the TTPs on url={}".format(
                            new_case["_id"], thehive.session.hive_url
                        ),
                    )

                else:
                    # somehow we got a bad response code from thehive
                    thehive.logger_file.error(
                        id="140",
                        message="TheHive TTPs update on recent case creation has failed. "
                        "url={}, data={}, content={}, ttp={}".format(
                            thehive.session.hive_url,
                            str(case),
                            str(response),
                            str(cases[srcRef]["ttps"]),
                        ),
                    )

            # Attach the Splunk search results if needed
            if alert_args["attach_results"] > 0:

                thehive.logger_file.info(
                    id="140",
                    message="Processing attachment of the Splunk search results to the case...",
                )

                # ⚠️ Building the file lives in attachment_builder: it was
                # duplicated here and in the alert helper, ~190 lines each,
                # sharing the SAME log identifiers -- so a [141] in production
                # designated two places at once.
                try:
                    tmp_directory, raw_results_filepath_after_rename = build_attachment(
                        results_file=helper.results_file,
                        attach_results=alert_args["attach_results"],
                        attach_format=alert_args["attach_format"],
                        attachment_prefix=attachment_prefix,
                        object_id=new_case["_id"],
                        logger_file=thehive.logger_file,
                    )
                except AttachmentError as e:
                    thehive.logger_file.error(
                        id="151",
                        message=f"The search results could not be prepared for attachment: {e}",
                    )
                    # ⚠️ `continue`, not `return`: this sits inside the loop
                    # over the objects being created. One unusable attachment
                    # must cost its own object, never the ones after it. The
                    # previous code raised here and abandoned the whole batch.
                    continue

                attachment_result = None
                try:
                    thehive.logger_file.info(
                        id="149",
                        message=f"Processing name for the attachment from the options, result is: {raw_results_filepath_after_rename}",
                    )
                    attachment_result = thehive.case.add_attachment(
                        new_case["_id"], [raw_results_filepath_after_rename]
                    )
                except TheHiveError as e:
                    thehive.logger_file.error(
                        id="150",
                        message="TheHive attachment creation has failed. "
                        "url={}, data={}, content={}, error={}".format(
                            thehive.session.hive_url, str(case), str(new_case), str(e)
                        ),
                    )

                # Remove the dedicated temporary directory (and its content)
                shutil.rmtree(tmp_directory, ignore_errors=True)

                if attachment_result is not None and "_id" in attachment_result[0]:
                    # log response status
                    thehive.logger_file.info(
                        id="170",
                        message="TheHive case {} search results were successfully attached to the case on url={}".format(
                            new_case["_id"], thehive.session.hive_url
                        ),
                    )

                else:
                    # somehow we got a bad response code from thehive
                    thehive.logger_file.error(
                        id="180",
                        message="TheHive attachment creation on recent case creation has failed. "
                        "url={}, data={}, content={}, attachment={}".format(
                            thehive.session.hive_url,
                            str(case),
                            str(response),
                            str(helper.results_file),
                        ),
                    )
