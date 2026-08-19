# encoding = utf-8
# Author: Alexandre Demeyer <letmer00t@gmail.com>, Remi Seguy <remg427@gmail.com>
#
# Copyright: LGPLv3 (https://www.gnu.org/licenses/lgpl-3.0.txt)
# Feel free to use the code, but please share the changes you've made

__author__ = "Alexandre Demeyer, Remi Seguy"
__license__ = "LGPLv3"
__version__ = "4.0.0"
__maintainer__ = "Alexandre Demeyer"
__email__ = "letmer00t@gmail.com"

import ta_thehive_cortex_declare

# Standard library imports
import re
import shutil

# Third-party imports
from thehive4py.types.alert import InputAlert

from attachment_builder import AttachmentError, build_attachment
from creation_retry import create_with_retry
from modalert_args import common_args, prepare_instances, si_vide
from post_creation import attach_procedures, upload_attachment

# Local application/library specific imports
from modalert_thehive_common import parse_events
from thehive import TheHive4Splunk

__author__ = "Alexandre Demeyer, Remi Seguy"
__maintainer__ = "Alexandre Demeyer"
__email__ = "letmer00t@gmail.com"


def process_event(helper, *args, **kwargs):

    # The bootstrap is shared by every alert action: it differed only by the
    # four-letter acronym woven into two log prefixes.
    instances = prepare_instances(helper, acronym="THCA")

    for thehive, configuration, defaults, logger_file, instance_id in instances:
        # Get alert arguments -- everything shared lives in modalert_args,
        # which used to be ~110 lines duplicated with the case helper.
        alert_args = common_args(helper, logger_file)
        alert_args["alert_mode"] = si_vide(helper.get_param("alert_mode"), "es_mode")
        alert_args["type"] = si_vide(helper.get_param("type"), "alert")
        alert_args["dashboard"] = si_vide(helper.get_param("dashboard"), None)
        logger_file.debug(id="55", message="Arguments recovered: " + str(alert_args))

        # Create the alert
        logger_file.info(
            id="56", message="Configuration is ready. Creating the alert..."
        )
        logger_file.debug(
            id="57",
            message="TheHive URL instance used after retrieving the configuration: "
            + str(thehive.session.hive_url),
        )
        logger_file.debug(
            id="58", message="Processing following instance ID: " + str(instance_id)
        )
        create_alert(
            helper,
            thehive,
            alert_args,
            max_retry=int(defaults["MAX_CREATION_RETRY"]),
            attachment_prefix=defaults["ATTACHMENT_PREFIX"],
        )
    return 0


def create_alert(
    helper,
    thehive: TheHive4Splunk,
    alert_args,
    max_retry: int = 2,
    attachment_prefix: str = "events_",
):
    """This function is used to create the alert using the API, settings and search results"""

    # Parse events
    alerts = parse_events(helper, thehive, alert_args)

    # Build the external link
    external_link = helper.settings["results_link"]
    if alert_args["dashboard"] is not None:
        results = re.match(r"^(http[s]+:\/\/[^:]+(?::\d+)\/[^\/]+)", external_link)
        if results:
            external_link = f"{results.group(1)}/{alert_args['dashboard']}"
        else:
            thehive.logger_file.warn(
                id="1",
                message="Cannot determine external link url={}, results_link={}".format(
                    thehive.session.hive_url, str(external_link)
                ),
            )

    # actually send the request to create the alert; fail gracefully
    for srcRef in alerts.keys():
        # Create the Alert object
        alert = InputAlert(
            title=alerts[srcRef]["title"],
            date=int(alerts[srcRef]["timestamp"]),
            description=alerts[srcRef]["description"],
            tags=alert_args["tags"],
            severity=alerts[srcRef]["severity"],
            tlp=alerts[srcRef]["tlp"],
            pap=alerts[srcRef]["pap"],
            type=alert_args["type"],
            observables=alerts[srcRef]["observables"],
            customFields=alerts[srcRef]["customFields"],
            source=alert_args["source"],
            caseTemplate=alert_args["caseTemplate"],
            sourceRef=srcRef,
            externalLink=external_link,
        )

        thehive.logger_file.debug(id="120", message="Processing alert: " + str(alert))
        # Get API and create the alert
        new_alert = create_with_retry(
            create=lambda: thehive.alert.create(alert),
            max_retry=max_retry,
            logger_file=thehive.logger_file,
            ids={"duplicate": "122", "retry": "123", "exhausted": "124"},
            contexte=lambda: f"TheHive alert url={thehive.session.hive_url}, data={alert}",
        )

        if new_alert is not None:
            if "_id" in new_alert:
                # log response status
                thehive.logger_file.info(
                    id="125",
                    message="TheHive alert {} is successfully created on url={}".format(
                        new_alert["_id"], thehive.session.hive_url
                    ),
                )

            else:
                # somehow we got a bad response code from thehive
                thehive.logger_file.error(
                    id="126",
                    message="TheHive alert creation has failed. "
                    "url={}, data={}, content={}".format(
                        thehive.session.hive_url, str(alert), str(new_alert)
                    ),
                )

            # Processing TTPs if any -- shared with the case
            # helper, which carried the same ~35 lines and the same ambiguous
            # log identifiers.
            if "ttps" in alerts[srcRef]:
                attach_procedures(
                    endpoint=thehive.alert,
                    object_id=new_alert["_id"],
                    ttps=alerts[srcRef]["ttps"],
                    logger_file=thehive.logger_file,
                    url=thehive.session.hive_url,
                    contexte=lambda: f"data={alert}",
                )

            # Attach the Splunk search results if needed
            if alert_args["attach_results"] > 0:

                thehive.logger_file.info(
                    id="140",
                    message="Processing attachment of the Splunk search results to the alert...",
                )

                # ⚠️ Building the file lives in attachment_builder: it was
                # duplicated here and in the case helper, ~190 lines each,
                # sharing the SAME log identifiers -- so a [141] in production
                # designated two places at once.
                try:
                    tmp_directory, raw_results_filepath_after_rename = build_attachment(
                        results_file=helper.results_file,
                        attach_results=alert_args["attach_results"],
                        attach_format=alert_args["attach_format"],
                        attachment_prefix=attachment_prefix,
                        object_id=new_alert["_id"],
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
                        endpoint=thehive.alert,
                        object_id=new_alert["_id"],
                        chemin=raw_results_filepath_after_rename,
                        logger_file=thehive.logger_file,
                        url=thehive.session.hive_url,
                        ids={"uploading": "149", "failed": "150", "attached": "155", "not_attached": "160"},
                        contexte=lambda: f"data={alert}",
                    )
                finally:
                    # The upload reads FROM this directory, so it is removed
                    # only once the upload is over -- success or not.
                    shutil.rmtree(tmp_directory, ignore_errors=True)
