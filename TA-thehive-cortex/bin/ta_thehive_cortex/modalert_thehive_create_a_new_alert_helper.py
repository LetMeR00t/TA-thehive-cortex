# encoding = utf-8
#!/usr/bin/env python
# Generate TheHive alerts
#
# Author: Alexandre Demeyer <letmer00t@gmail.com>
# Inspired by: Remi Seguy <remg427@gmail.com>
#
# Copyright: LGPLv3 (https://www.gnu.org/licenses/lgpl-3.0.txt)
# Feel free to use the code, but please share the changes you've made

import csv
import gzip
import json
import os
import re
import requests
import time
import splunklib.client as client
from common import Settings
from thehive import TheHive, create_thehive_instance
from thehive4py.models import Alert

__author__ = "Alexandre Demeyer, Remi Seguy"
__license__ = "LGPLv3"
__version__ = "2.0.0"
__maintainer__ = "Alexandre Demeyer"
__email__ = "letmeR00t@gmail.com"

# All available data types
OBSERVABLE_TLP = {
    "W": 0,
    "G": 1,
    "A": 2,
    "R": 3,
    "0": "TLP:WHITE",
    "1": "TLP:GREEN",
    "2": "TLP:AMBER",
    "3": "TLP:RED"
}

# All available data types
dataTypeList = [
    "domain",
    "file",
    "filename",
    "fqdn",
    "hash",
    "ip",
    "mail",
    "mail_subject",
    "other",
    "regexp",
    "registry",
    "uri_path",
    "url",
    "user-agent"]


def create_datatype_lookup(helper, app_name):
    # if it does not exist, create thehive_datatypes.csv
    _SPLUNK_PATH = os.environ['SPLUNK_HOME']
    directory = os.path.join(
        _SPLUNK_PATH, 'etc', 'apps', app_name, 'lookups')
    th_dt_filename = os.path.join(directory, 'thehive_datatypes.csv')
    if not os.path.exists(th_dt_filename):
        # file th_dt_filename.csv doesn't exist. Create the file
        observables = list()
        observables.append(['field_name', 'field_type', 'datatype', 'regex', 'description'])
        for dt in dataTypeList:
            observables.append([dt, 'artifact', dt, '', ''])
        try:
            if not os.path.exists(directory):
                os.makedirs(directory)
            with open(th_dt_filename, 'w') as file_object:
                csv_writer = csv.writer(file_object, delimiter=',')
                for observable in observables:
                    csv_writer.writerow(observable)
        except IOError:
            helper.log_error(
                "[HC102] FATAL {} could not be opened in write mode".format(th_dt_filename)
            )


def create_instance_lookup(helper, app_name):
    # if the lookup available on github has not been created
    # generate it on first alert and return a message to configure it
    _SPLUNK_PATH = os.environ['SPLUNK_HOME']
    directory = os.path.join(
        _SPLUNK_PATH, 'etc', 'apps', app_name, 'lookups')
    th_list_filename = os.path.join(directory, 'thehive_instance_list.csv')
    if not os.path.exists(th_list_filename):
        # file thehive_instance_list.csv doesn't exist. Create the file
        th_list = [['thehive_instance', 'thehive_url', 'thehive_api_key_name',
                    'thehive_verifycert', 'thehive_ca_full_path',
                    'thehive_use_proxy', 'client_use_cert',
                    'client_cert_full_path'],
                   ['th_test', 'https://testhive.example.com/',
                    'thehive_api_key1', 'True', '',
                    'False', 'False', 'client_cert_full_path'],
                   ['th_staging', 'https://staginghive.example.com/',
                    'thehive_api_key2', 'True', '',
                    'False', 'False', 'client_cert_full_path'],
                   ['th_prod', 'https://prodhive.example.com/',
                    'thehive_api_key3', 'True', '',
                    'False', 'False', 'client_cert_full_path']
                   ]
        try:
            if not os.path.exists(directory):
                os.makedirs(directory)
            with open(th_list_filename, 'w') as file_object:
                csv_writer = csv.writer(file_object, delimiter=',')
                for instance in th_list:
                    csv_writer.writerow(instance)
        except IOError:
            helper.log_error(
                "[HC202] FATAL {} could not be opened in write mode"
                .format(th_list_filename)
            )


def get_datatype_dict(helper, app_name):
    dataType_dict = dict()
    _SPLUNK_PATH = os.environ['SPLUNK_HOME']
    directory = os.path.join(
        _SPLUNK_PATH, 'etc', 'apps', app_name, 'lookups'
    )
    th_dt_filename = os.path.join(directory, 'thehive_datatypes.csv')
    if os.path.exists(th_dt_filename):
        try:
            # open the file with gzip lib, start making alerts
            # can with statements fail gracefully??
            fh = open(th_dt_filename, "rt")
        except ValueError:
            # Workaround for Python 2.7 under Windows
            fh = gzip.open(th_dt_filename, "r")
        if fh is not None:
            try:
                csv_reader = csv.DictReader(fh)
                for row in csv_reader:
                    if 'field_name' in row and 'field_type' in row:
                        if row['field_type'] == 'artifact':
                            dataType_dict[row['field_name']] = row['datatype']
                helper.log_info("[HC304] dataType_dict built from thehive_datatypes.csv")
            except IOError:  # file thehive_datatypes.csv not readable
                helper.log_error('[HC305] file {} empty, malformed or not readable'.format(
                    th_dt_filename
                ))
    else:
        create_datatype_lookup(helper, app_name)
    if not dataType_dict:
        dataType_dict = dict()
        for dt in dataTypeList:
            dataType_dict[dt] = dt
        helper.log_info("[HC306] dataType_dict built from inline table")
    return dataType_dict


def get_customField_dict(helper, app_name):
    customField_dict = dict()
    _SPLUNK_PATH = os.environ['SPLUNK_HOME']
    directory = os.path.join(
        _SPLUNK_PATH, 'etc', 'apps', app_name, 'lookups'
    )
    th_dt_filename = os.path.join(directory, 'thehive_datatypes.csv')
    if os.path.exists(th_dt_filename):
        try:
            # open the file with gzip lib, start making alerts
            # can with statements fail gracefully??
            fh = open(th_dt_filename, "rt")
        except ValueError:
            # Workaround for Python 2.7 under Windows
            fh = gzip.open(th_dt_filename, "r")
        if fh is not None:
            try:
                csv_reader = csv.DictReader(fh)
                for row in csv_reader:
                    if 'field_name' in row and 'field_type' in row:
                        if row['field_type'] == 'customField':
                            customField_dict[row['field_name']] = row['datatype']
                helper.log_info("[HC604] customField_dict built from thehive_datatypes.csv")
            except IOError:  # file thehive_datatypes.csv not readable
                helper.log_error('[HC605] file {} absent or not readable'.format(
                    th_dt_filename
                ))
    else:
        create_datatype_lookup(helper, app_name)
    return customField_dict


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
    thehive_max_cases = helper.get_global_setting("thehive_max_cases")
    helper.log_info("thehive_max_cases={}".format(thehive_max_cases))
    thehive_sort_cases = helper.get_global_setting("thehive_sort_cases")
    helper.log_info("thehive_sort_cases={}".format(thehive_sort_cases))

    # The following example gets the alert action parameters and prints them to the log
    thehive_instance_id = helper.get_param("thehive_instance_id")
    helper.log_info("thehive_instance_id={}".format(thehive_instance_id))

    case_template = helper.get_param("case_template")
    helper.log_info("case_template={}".format(case_template))

    type = helper.get_param("type")
    helper.log_info("type={}".format(type))

    source = helper.get_param("source")
    helper.log_info("source={}".format(source))

    unique_id_field = helper.get_param("unique_id_field")
    helper.log_info("unique_id_field={}".format(unique_id_field))

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
    helper.log_info("LOG level to: "+helper.log_level)
    helper.set_log_level(helper.log_level)

    helper.log_info("[AL101] Alert action thehive_create_a_new_alert started at {}".format(time.time()))

    # Get the instance connection and initialize settings
    instance_id = helper.get_param("thehive_instance_id")
    helper.log_debug("TheHive instance found: "+str(instance_id))

    (thehive, configuration, defaults, logger) = create_thehive_instance(instance_id=instance_id, settings=helper.settings, logger=helper._logger)

    helper.log_debug("TheHive connection is ready. Processing alert parameters...")

    # Get alert arguments
    alert_args = {}
    # Get string values from alert form
    alert_args["caseTemplate"] = helper.get_param("case_template") if helper.get_param("case_template") else "default"
    alert_args["type"] = helper.get_param("type") if helper.get_param("type") else "alert"
    alert_args["source"] = helper.get_param("source") if helper.get_param("source") else "splunk"
    alert_args["unique_id_field"] = helper.get_param("unique_id_field") if helper.get_param("unique_id_field") else "oneEvent" 
    if not helper.get_param("timestamp_field"):
        alert_args['timestamp'] = int(time.time() * 1000)
    else:
        alert_args['timestamp'] = helper.get_param("timestamp_field")
        epoch10 = re.match("^[0-9]{10}$", alert_args['timestamp'])
        if epoch10 is not None:
            alert_args['timestamp'] = alert_args['timestamp'] * 1000

    alert_args["title"] = helper.get_param("title") if helper.get_param("title") else "Notable event" 
    alert_args["description"] = helper.get_param("description").replace("\\n","\n").replace("\\r","\r") if helper.get_param("description") else "No description provided"         
    alert_args["tags"] = list(dict.fromkeys(helper.get_param("tags").split(","))) if helper.get_param("tags") else []
    helper.log_debug("[X304] scope: {} ".format(helper.get_param("scope")))
    alert_args["scope"] = True if int(helper.get_param("scope"))==0 else False   
    # Get numeric values from alert form
    alert_args['severity'] = int(helper.get_param("severity")) if helper.get_param("severity") is not None else 2
    alert_args['tlp'] = int(helper.get_param("tlp")) if helper.get_param("tlp") is not None else 2
    alert_args['pap'] = int(helper.get_param("pap")) if helper.get_param("pap") is not None else 2

    # Create the alert
    helper.log_debug("[AL103] Alert preparation is finished. Creating the alert...")
    create_alert(helper, thehive, alert_args)
    helper.log_debug("[AL104] Alert creation is done.")
    return 0

def extract_field(row, field):
    """ This function is used to extract information from a potential field in a row and sanitize it if needed. If the field is not found, use the field name directly as value """
    result = field
    if field in row:
        newValue = str(row.pop(field))
        if newValue not in [None, '']:
            result = newValue
    return result

def create_alert(helper, thehive_api, alert_args):
    """ This function is used to create the alert using the API, settings and search results """

    # iterate through each row, cleaning multivalue fields
    # and then adding the attributes under same alert key
    # this builds the dict alerts
    app_name = "TA-thehive-cortex"
    data_type = get_datatype_dict(helper, app_name)
    custom_field_type = get_customField_dict(helper, app_name)
    alert_reference = 'SPK' + str(int(time.time()))
    helper.log_debug("[HA301] alert_reference: {}".format(alert_reference))
    alerts = dict()
    events = helper.get_events()
    for row in events:
        # Initialize values
        artifacts = []
        artifactTags = []
        artifactMessage = ''
        customFields = dict()
        sourceRef = alert_reference
        alert = dict() 

        # Splunk makes a bunch of dumb empty multivalue fields
        # replace value by multivalue if required
        for key, value in row.items():
            if not key.startswith("__mv_") and "__mv_"+key in row and row["__mv_"+key] not in [None, '']:
                row[key] = [e[1:len(e)-1] for e in row["__mv_"+key].split(";")]
        # we filter those out here
        row = {key: value for key, value in row.items() if not key.startswith("__mv_") and key not in ["rid"]}

        # find the field name used for a unique identifier
        if alert_args['unique_id_field'] in row:
            newSource = str(row[alert_args['unique_id_field']])
            if newSource not in [None, '']:
                # grabs that field's value and assigns it to our sourceRef
                sourceRef = newSource

        helper.log_debug("[HA304] sourceRef: {} ".format(sourceRef))

        if 'th_inline_tags' in row:
            # grabs that field's value and assigns it to
            artifactTags = str(row.pop("th_inline_tags")).split(",")

        # check if the field th_msg exists and strip it from the row.
        # The value will be used as message attached to artifacts
        if 'th_msg' in row:
            # grabs that field's value and assigns it to
            artifactMessage = str(row.pop("th_msg"))
            
        helper.log_debug("[HA332] artifact message: {} ".format(artifactMessage))
        helper.log_debug("[HA331] artifact tags: {} ".format(artifactTags))

        # check if artifacts have been stored for this sourceRef.
        # If yes, retrieve them to add new ones from this row
        if sourceRef in alerts:
            alert = alerts[sourceRef]
            artifacts = list(alert["artifacts"])
            customFields = dict(alert['customFields'])

        # check if title contains a field name instead of a string.
        # if yes, strip it from the row and assign value to title
        alert["title"] = extract_field(row, alert_args["title"])

        # check if description contains a field name instead of a string.
        # if yes, strip it from the row and assign value to description
        alert["description"] = extract_field(row, alert_args["description"])

        # find the field name used for a valid timestamp
        # and strip it from the row

        if alert_args['timestamp'] in row:
            newTimestamp = str(int(float(row.pop(alert_args['timestamp']))))
            helper.log_debug(
                "[HA305] new Timestamp from row: {} ".format(newTimestamp)
            )
            epoch10 = re.match("^[0-9]{10}$", newTimestamp)
            epoch13 = re.match("^[0-9]{13}$", newTimestamp)
            if epoch13 is not None:
                alert['timestamp'] = int(float(newTimestamp))
            elif epoch10 is not None:
                alert['timestamp'] = int(float(newTimestamp)) * 1000
            helper.log_debug("[HA306] alert timestamp: {} ".format(alert['timestamp']))

        # now we take those KV pairs to add to dict
        for key, value in row.items():
            cTags = artifactTags[:]
            if value != "":
                helper.log_debug('[HA320] field to process: {}'.format(key))
                artifact_key = ''
                cTLP = ''
                if ':' in key:
                    helper.log_debug('[HA321] composite fieldvalue: {}'.format(key))
                    dType = key.split(':', 1)
                    key = str(dType[0])
                    # extract TLP at observable level
                    # it is on letter W G A or R appended to field name
                    observable_tlp_check = re.match("^(W|G|A|R)$", str(dType[1]))
                    if observable_tlp_check is not None:
                        cTLP = OBSERVABLE_TLP[dType[1]]
                        cTags.append(OBSERVABLE_TLP[str(cTLP)])
                    else:
                        cTags.append(str(dType[1].replace(" ", "_")))
                if key in data_type:
                    helper.log_debug('[HA322] key is an artifact: {} '.format(key))
                    artifact_key = data_type[key]
                elif key in custom_field_type:
                    helper.log_debug('[HA327] key is a custom field: {} '.format(key))
                    # expected types are `string`, `boolean`, `number` (only TH3), `date`, `integer` (only TH4), `float` (only TH4)
                    custom_field_check = False
                    custom_field = dict()
                    custom_field['order'] = len(customFields)
                    custom_type = custom_field_type[key]
                    if custom_type == 'string':
                        custom_field_check = True
                        custom_field[custom_type] = str(value)
                    elif custom_type == 'boolean':
                        is_True = re.match("^(1|y|Y|t|T|true|True)$", value)
                        is_False = re.match("^(0|n|N|f|F|false|False)$", value)
                        if is_True is not None:
                            custom_field_check = True
                            custom_field[custom_type] = True
                        elif is_False is not None:
                            custom_field_check = True
                            custom_field[custom_type] = False
                    elif custom_type == 'number':  # for TheHive3 only
                        is_integer = re.match("^[0-9]+$", value)
                        if is_integer is not None:
                            custom_field_check = True
                            custom_field[custom_type] = int(value)
                        else:
                            try:
                                number = float(value)
                                custom_field_check = True
                                custom_field[custom_type] = number
                            except ValueError:
                                pass
                    elif custom_type == 'integer':  # for TheHive4 only
                        try:
                            number = int(value)
                            custom_field_check = True
                            custom_field[custom_type] = number
                        except ValueError:
                            pass
                    elif custom_type == 'float':  # for TheHive4 only
                        try:
                            number = float(value)
                            custom_field_check = True
                            custom_field[custom_type] = number
                        except ValueError:
                            pass
                    elif custom_type == 'date':
                        epoch10 = re.match("^[0-9]{10}$", value)
                        epoch13 = re.match("^[0-9]{13}$", value)
                        if epoch13 is not None:
                            custom_field_check = True
                            custom_field[custom_type] = int(value)
                        elif epoch10 is not None:
                            custom_field_check = True
                            custom_field[custom_type] = int(value) * 1000
                    if custom_field_check is True:
                        customFields[key] = custom_field
                elif alert_args['scope'] is False:
                    helper.log_debug(
                        '[HA323] key is added as another artifact (scope is False): {} '.format(key)
                    )
                    artifact_key = 'other'

                if artifact_key not in [None, '']:
                    helper.log_debug("Processing artifact key: "+str(artifact_key)+" ("+str(value)+") ("+artifactMessage+")")
                    cMsg = 'field: ' + str(key)
                    if artifactMessage not in [None, '']:
                        cMsg = artifactMessage + ' - ' + cMsg
                    if isinstance(value,list) :  # was a multivalue field
                        helper.log_debug('[HA324] value is not a simple string: {} '.format(value))
                        for val in value:
                            if val != "":
                                artifact = dict(dataType=artifact_key,
                                                data=str(val),
                                                message=cMsg,
                                                tags=cTags
                                                )
                                if cTLP != '':
                                    artifact['tlp'] = cTLP
                                helper.log_debug(
                                    "[HA325] new artifact is {}".format(artifact)
                                )
                                if artifact not in artifacts:
                                    artifacts.append(artifact)
                    else:
                        artifact = dict(dataType=artifact_key,
                                        data=str(value),
                                        message=cMsg,
                                        tags=cTags
                                        )
                        if cTLP != '':
                            artifact['tlp'] = cTLP
                        if artifact not in artifacts:
                            artifacts.append(artifact)

        if artifacts:
            alert['artifacts'] = list(artifacts)
            alert['customFields'] = customFields
            alerts[sourceRef] = alert
            helper.log_debug("Artifacts found for an alert: "+str(artifacts))
        else:
            helper.log_debug("No artifact found for an alert: "+str(alert))

    # actually send the request to create the alert; fail gracefully
    for srcRef in alerts.keys():

        # Create the Alert object
        alert = Alert(
                title=alerts[srcRef]['title'],
                date=int(alerts[srcRef]['timestamp']),
                description=alerts[srcRef]['description'],
                tags=alert_args['tags'],
                severity=alert_args['severity'],
                tlp=alert_args['tlp'],
                pap=alert_args['pap'],
                type=alert_args['type'],
                artifacts=alerts[srcRef]['artifacts'],
                customFields=alerts[srcRef]['customFields'],
                source=alert_args['source'],
                caseTemplate=alert_args['caseTemplate'],
                sourceRef=srcRef
            )

        helper.log_debug("Processing alert: "+alert.jsonify())
        # Get API and create the alert
        response = thehive_api.create_alert(alert)

        if response.status_code in (200, 201, 204):
            # log response status
            helper.log_info(
                "[HA316] INFO theHive alert is successful created. "
                "url={}, HTTP status={}".format(thehive_api.url, response.status_code)
            )
        else:
            # somehow we got a bad response code from thehive
            helper.log_error(
                "[HA317] ERROR theHive alert creation has failed. "
                "url={}, data={}, HTTP Error={}, content={}"
                .format(thehive_api.url, alert.jsonify(), response.status_code, response.text)
            )
