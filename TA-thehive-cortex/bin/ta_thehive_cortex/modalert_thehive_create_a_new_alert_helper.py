# encoding = utf-8
#!/usr/bin/env python
# Generate TheHive alerts
#
# Author: Alexandre Demeyer <letmer00t@gmail.com>
# Inspired by: Remi Seguy <remg427@gmail.com>
#
# Copyright: LGPLv3 (https://www.gnu.org/licenses/lgpl-3.0.txt)
# Feel free to use the code, but please share the changes you've made

import re
import tempfile
import time
import gzip
import csv
import os
import json
from  modalert_thehive_common import parse_events
from thehive import TheHive, create_thehive_instance
from thehive4py.types.alert import InputAlert
from thehive4py.errors import TheHiveError
import globals
import hashlib
import shutil

__author__ = "Alexandre Demeyer, Remi Seguy"
__maintainer__ = "Alexandre Demeyer"
__email__ = "letmer00t@gmail.com"


def process_event(helper, *args, **kwargs):

    globals.initialize_globals()

    # Set the current LOG level
    helper.log_info("[CAA-THCA-35] LOG level to: " + helper.log_level)
    helper.set_log_level(helper.log_level)

    # Get the instance connection and initialize settings
    instances_id = helper.get_param("thehive_instance_id").split(",")
    helper.log_debug("[CAA-THCA-40] TheHive instances found: " + str(instances_id))

    instances = []
    for instance_id in instances_id:
        instances.append(create_thehive_instance(instance_id=instance_id, settings=helper.settings, logger=helper._logger, acronym="THCA"))

    for (thehive, configuration, defaults, logger_file, instance_id) in instances:
        # Get alert arguments
        alert_args = {}
        # Get string values from alert form
        alert_args["alert_mode"] = helper.get_param("alert_mode") if helper.get_param("alert_mode") else "es_mode" 
        alert_args["unique_id_field"] = helper.get_param("unique_id_field") if helper.get_param("unique_id_field") else "oneEvent" 
        alert_args["caseTemplate"] = helper.get_param("case_template") if helper.get_param("case_template") else None
        alert_args["type"] = helper.get_param("type") if helper.get_param("type") else "alert"
        alert_args["source"] = helper.get_param("source") if helper.get_param("source") else "splunk"
        if not helper.get_param("timestamp_field"):
            alert_args['timestamp'] = int(time.time() * 1000)
        else:
            alert_args['timestamp'] = helper.get_param("timestamp_field")
            epoch10 = re.match("^[0-9]{10}$", alert_args['timestamp'])
            if epoch10 is not None:
                alert_args['timestamp'] = int(alert_args['timestamp']) * 1000

        alert_args["title"] = helper.get_param("title") if helper.get_param("title") else None
        alert_args["description"] = helper.get_param("description").replace("\\n","\n").replace("\\r","\r") if helper.get_param("description") else "No description provided"
        alert_args["dashboard"] = helper.get_param("dashboard") if helper.get_param("dashboard") else None
        alert_args["tags"] = list(dict.fromkeys(helper.get_param("tags").split(","))) if helper.get_param("tags") else []
        logger_file.debug(id="50",message="scope: {} ".format(helper.get_param("scope")))
        alert_args["scope"] = True if int(helper.get_param("scope")) == 0 else False
        # Get numeric values from alert form
        alert_args["severity"] = int(helper.get_param("severity")) if helper.get_param("severity") is not None else 2
        alert_args["tlp"] = int(helper.get_param("tlp")) if helper.get_param("tlp") is not None else 2
        alert_args["pap"] = int(helper.get_param("pap")) if helper.get_param("pap") is not None else 2
        alert_args["splunk_es_alerts_index"] = helper.get_global_setting("splunk_es_alerts_index") if helper.get_global_setting("splunk_es_alerts_index") is not None else "summary"
        alert_args["description_results_enable"] = True if int(helper.get_param("description_results_enable")) == 1 else False
        alert_args["description_results_keep_observable"] = True if int(helper.get_param("description_results_keep_observable")) == 1 else False
        alert_args["attach_results"] = int(helper.get_param("attach_results"))
        alert_args["attach_format"] = int(helper.get_param("attach_format"))
        logger_file.debug(id="55",message="Arguments recovered: " + str(alert_args))

        # Create the alert
        logger_file.info(id="56",message="Configuration is ready. Creating the alert...")
        logger_file.debug(id="57",message="TheHive URL instance used after retrieving the configuration: " + str(thehive.session.hive_url))
        logger_file.debug(id="58",message="Processing following instance ID: " + str(instance_id))
        create_alert(helper, thehive, alert_args, max_retry = int(defaults["MAX_CREATION_RETRY"]), attachment_prefix = defaults["ATTACHMENT_PREFIX"])
    return 0



def create_alert(helper, thehive: TheHive, alert_args, max_retry: int = 2, attachment_prefix: str = "events_"):
    """ This function is used to create the alert using the API, settings and search results """
 
    # Parse events
    alerts = parse_events(helper, thehive, alert_args)

    # Build the external link
    external_link = helper.settings["results_link"]
    if alert_args["dashboard"] is not None:
        results = re.match(r'^(http[s]+:\/\/[^:]+(?::\d+)\/[^\/]+)', external_link)
        if results:
            external_link = f"{results.group(1)}/{alert_args['dashboard']}"
        else:
             thehive.logger_file.warn(id="1",message="Cannot determine external link url={}, results_link={}"
                .format(thehive.session.hive_url, str(external_link))
            )

    # actually send the request to create the alert; fail gracefully
    for srcRef in alerts.keys():
        # Create the Alert object
        alert = InputAlert(
            title=alerts[srcRef]['title'],
            date=int(alerts[srcRef]['timestamp']),
            description=alerts[srcRef]['description'],
            tags=alert_args['tags'],
            severity=alerts[srcRef]['severity'],
            tlp=alerts[srcRef]['tlp'],
            pap=alerts[srcRef]['pap'],
            type=alert_args['type'],
            observables=alerts[srcRef]['observables'],
            customFields=alerts[srcRef]['customFields'],
            source=alert_args['source'],
            caseTemplate=alert_args['caseTemplate'],
            sourceRef=srcRef,
            externalLink=external_link
        )

        thehive.logger_file.debug(id="120",message="Processing alert: " + str(alert))
        # Get API and create the alert
        new_alert = None
        alert_created = False
        retry_count = 0
        while retry_count <= max_retry and not alert_created:
            try:
                new_alert = thehive.alert.create(alert)
                alert_created = True
            except TheHiveError as e:
                thehive.logger_file.warning(id="122",message="TheHive alert creation has failed. Will retry... "
                    "url={}, data={}, content={}, error={}"
                    .format(thehive.session.hive_url, str(alert), str(new_alert), str(e))
                )
            retry_count += 1
        if retry_count == max_retry:
            thehive.logger_file.error(id="125",message="TheHive alert creation has failed, after {max_retry} retries. "
                    "url={}, data={}, content={}, error={}"
                    .format(thehive.session.hive_url, str(alert), str(new_alert), str(e))
                )

        if new_alert is not None:
            if "_id" in new_alert:
                # log response status
                thehive.logger_file.info(id="125",message="TheHive alert {} is successfully created on url={}".format(new_alert["_id"],thehive.session.hive_url)
                )

            else:
                # somehow we got a bad response code from thehive
                thehive.logger_file.error(id="126",message="TheHive alert creation has failed. "
                    "url={}, data={}, content={}"
                    .format(thehive.session.hive_url, str(alert), str(new_alert))
                )
            
            # Processing TTPs if any
            if "ttps" in alerts[srcRef]:
                
                response = thehive.alert.create_procedures(alert_id=new_alert["_id"], procedures=alerts[srcRef]["ttps"])[0]

                if "_id" in response:
                    # log response status
                    thehive.logger_file.info(id="130",message="TheHive alert {} was successfully updated with the TTPs on url={}".format(new_alert["_id"],thehive.session.hive_url)
                    )

                else:
                    # somehow we got a bad response code from thehive
                    thehive.logger_file.warn(id="135",message="TheHive TTPs update on recent alert creation has failed. "
                        "url={}, data={}, content={}, ttp={}"
                        .format(thehive.session.hive_url, str(alert), str(response), str(alerts[srcRef]["ttps"])))
                    
            # Attach the Splunk search results if needed
            if alert_args["attach_results"] > 0:

                # This means, yes
                
                thehive.logger_file.info(id="140",message="Processing attachment of the Splunk search results to the alert...")

                results_file = helper.results_file
                thehive.logger_file.debug(id="141",message=f"Processing results file: {results_file}")
                results_file_name = os.path.basename(results_file).split(".")[0]
                tmp_directory = tempfile.gettempdir()
                file_ext = ".csv.gz"
                raw_results_filepath_before_rename = None

                # This means, yes but compressed in GZ format
                if alert_args["attach_results"] == 1:
                    # Just copy the file without any change
                    raw_results_filepath_before_rename = os.path.join(tmp_directory,results_file_name+file_ext)
                    shutil.copyfile(results_file, raw_results_filepath_before_rename)

                # This means, yes but uncompressed
                elif alert_args["attach_results"] >= 2:

                    thehive.logger_file.warn(id="145",message="Uncompressing Splunk search results file located at {}...".format(results_file))

                    # uncompress file
                    headers = None
                    data = None
                    sha256 = None

                    # Headers and rows
                    try:
                        csvreader = None
                        data = []
                        with gzip.open(results_file, 'rt') as f:
                            csvreader = csv.reader(f)
                            headers = next(csvreader)
                            for row in csvreader:
                                data.append(row)

                    except Exception as e:
                        thehive.logger_file.error(id="148",message="Error during uncompressing process: {}".format(e))

                    # Headers are in 'headers' and rows in 'data'

                    # This means, yes but uncompressed in CSV format
                    if alert_args["attach_results"] == 2:
                        # CSV file, no change
                        file_ext = ".csv"
                        raw_results_filepath_before_rename = os.path.join(tmp_directory,results_file_name+file_ext)

                        with open(raw_results_filepath_before_rename, "wt", newline="") as f:
                            csvwriter = csv.writer(f)
                            csvwriter.writerow(headers)
                            csvwriter.writerows(data)
                        
                        # Calculate SHA256
                        with open(raw_results_filepath_before_rename,"rb") as f:
                            bytes = f.read() # read entire file as bytes
                            sha256 = hashlib.sha256(bytes)

                    # This means, yes but uncompressed in JSON format
                    elif alert_args["attach_results"] == 3:
                        file_ext = ".json"
                        # JSON file, convert it
                        with gzip.open(results_file, 'rt') as f:
                            reader = csv.DictReader(f, headers)
                            # Skip first row
                            next(reader)
                            data = []
                            for row in reader:
                                data.append(row)

                        # Convert
                        json_data = None
                        if len(data)>1:
                            json_data = json.dumps(data, indent=2)
                        else:
                            json_data = json.dumps(data[0], indent=2)

                        raw_results_filepath_before_rename = os.path.join(tmp_directory,results_file_name+file_ext)

                        with open(raw_results_filepath_before_rename, 'w') as jsonfile:
                            jsonfile.write(json_data)


                # Calculate SHA256
                with open(raw_results_filepath_before_rename,"rb") as f:
                    bytes = f.read() # read entire file as bytes
                    sha256 = hashlib.sha256(bytes)

                # Evaluate the file name
                if alert_args["attach_format"] == 0:
                    # Prefix + Alert ID
                    raw_results_filepath_after_rename = os.path.join(tmp_directory,attachment_prefix+new_alert["_id"].replace("~","")+file_ext)
                elif alert_args["attach_format"] == 1:
                    # Alert ID
                    raw_results_filepath_after_rename = os.path.join(tmp_directory,new_alert["_id"].replace("~","")+file_ext)
                elif alert_args["attach_format"] == 2:
                    # Prefix + SHA256
                    raw_results_filepath_after_rename = os.path.join(tmp_directory,attachment_prefix+sha256.hexdigest()+file_ext)
                elif alert_args["attach_format"] == 3:
                    # SHA256
                    raw_results_filepath_after_rename = os.path.join(tmp_directory,sha256.hexdigest()+file_ext)
                else:
                    attach_format = alert_args["attach_format"]
                    thehive.logger_file.error(id="141",message=f"Attachment format isn't supported, given: {attach_format}")

                os.rename(raw_results_filepath_before_rename, raw_results_filepath_after_rename)

                attachment_result = None
                try:
                    thehive.logger_file.info(id="149",message=f"Processing name for the attachment from the options, result is: {raw_results_filepath_after_rename}")
                    attachment_result = thehive.alert.add_attachment(new_alert["_id"],[raw_results_filepath_after_rename])
                except TheHiveError as e:
                    thehive.logger_file.error(id="150",message="TheHive attachment creation has failed. "
                        "url={}, data={}, content={}, error={}"
                        .format(thehive.session.hive_url, str(alert), str(new_alert), str(e))
                    )


                # Remove tmp file
                os.remove(raw_results_filepath_after_rename)

                if "_id" in attachment_result[0]:
                    # log response status
                    thehive.logger_file.info(id="155",message="TheHive alert {} search results were successfully attached to the alert on url={}".format(new_alert["_id"],thehive.session.hive_url)
                    )

                else:
                    # somehow we got a bad response code from thehive
                    thehive.logger_file.error(id="160",message="TheHive attachment creation on recent alert creation has failed. "
                        "url={}, data={}, content={}, attachment={}"
                        .format(thehive.session.hive_url, str(alert), str(response), str(helper.results_file)))
                
