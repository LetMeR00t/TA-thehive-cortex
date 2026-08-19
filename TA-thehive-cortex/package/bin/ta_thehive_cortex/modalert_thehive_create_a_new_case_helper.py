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
import shutil

# Third-party imports
from thehive4py.types.case import InputCase

from attachment_builder import AttachmentError, build_attachment
from creation_retry import create_with_retry
from modalert_args import common_args, prepare_instances, si_vide
from post_creation import attach_procedures, upload_attachment

# Local application/library specific imports
from modalert_thehive_common import parse_events
from thehive import TheHive4Splunk

__author__ = "Alexandre Demeyer"
__maintainer__ = "Alexandre Demeyer"
__email__ = "letmer00t@gmail.com"


def process_event(helper, *args, **kwargs):

    # The bootstrap is shared by every alert action: it differed only by the
    # four-letter acronym woven into two log prefixes.
    instances = prepare_instances(helper, acronym="THCC")

    for thehive, configuration, defaults, logger_file, instance_id in instances:
        # Get alert arguments -- everything shared lives in modalert_args,
        # which used to be ~110 lines duplicated with the alert helper.
        alert_args = common_args(helper, logger_file)
        alert_args["case_mode"] = si_vide(helper.get_param("case_mode"), "es_mode")
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

            # Processing TTPs if any -- shared with the alert
            # helper, which carried the same ~35 lines and the same ambiguous
            # log identifiers.
            if "ttps" in cases[srcRef]:
                attach_procedures(
                    endpoint=thehive.case,
                    object_id=new_case["_id"],
                    ttps=cases[srcRef]["ttps"],
                    logger_file=thehive.logger_file,
                    url=thehive.session.hive_url,
                    contexte=lambda: f"data={case}",
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

                try:
                    upload_attachment(
                        endpoint=thehive.case,
                        object_id=new_case["_id"],
                        chemin=raw_results_filepath_after_rename,
                        logger_file=thehive.logger_file,
                        url=thehive.session.hive_url,
                        ids={"uploading": "149", "failed": "150", "attached": "170", "not_attached": "180"},
                        contexte=lambda: f"data={case}",
                    )
                finally:
                    # The upload reads FROM this directory, so it is removed
                    # only once the upload is over -- success or not.
                    shutil.rmtree(tmp_directory, ignore_errors=True)
