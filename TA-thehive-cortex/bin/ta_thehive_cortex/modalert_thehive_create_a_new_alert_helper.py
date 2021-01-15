# encoding = utf-8
#!/usr/bin/env python
# Generate TheHive alerts
#
# Author: Alexandre Demeyer <letmer00t@gmail.com>
# Inspired by: Remi Seguy <remg427@gmail.com>
#
# Copyright: LGPLv3 (https://www.gnu.org/licenses/lgpl-3.0.txt)
# Feel free to use the code, but please share the changes you've made

from hive_common import get_customField_dict, get_datatype_dict, prepare_config
import json
import re
import requests
import time
import splunklib.client as client

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
    thehive_instance = helper.get_param("thehive_instance")
    helper.log_info("thehive_instance={}".format(thehive_instance))

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

    helper.log_info("Alert action thehive_create_a_new_alert started.")
    
    helper.set_log_level(helper.log_level)
    helper.log_info("[AL101] Alert action thehive_ce_alert started at {}".format(time.time()))

    # TODO: Implement your alert action logic here
    th_app_name = "TA_thehive_ce"
    th_config = prepare_alert(helper, th_app_name)
    if th_config is None:
        helper.log_error("[AL102] FATAL config dict not initialised")
        return 1
    else:
        helper.log_debug("[AL103] config dict is ready to use")
        helper.log_info("[AL104] Alert action create_alert started at {}".format(time.time()))
        create_alert(helper, th_config, th_app_name)
        helper.log_info("[AL105] Alert action create_alert finished at {}".format(time.time()))
    return 0



def prepare_alert(helper, app_name):
    instance = helper.get_param("th_instance")
    sessionKey = helper.settings['session_key']
    splunkService = client.connect(token=sessionKey)
    storage = splunkService.storage_passwords
    config_args = prepare_config(helper, app_name, instance, storage)
    if config_args is None:
        return None
    alert_args = dict()
    # Get string values from alert form
    if not helper.get_param("th_case_template"):
        alert_args['caseTemplate'] = "default"
    else:
        alert_args['caseTemplate'] = helper.get_param("th_case_template")
    if not helper.get_param("th_type"):
        alert_args['type'] = "alert"
    else:
        alert_args['type'] = helper.get_param("th_type")
    if not helper.get_param("th_source"):
        alert_args['source'] = "splunk"
    else:
        alert_args['source'] = helper.get_param("th_source")
    if not helper.get_param("th_timestamp"):
        alert_args['timestamp'] = int(time.time() * 1000)
    else:
        alert_args['timestamp'] = helper.get_param("th_timestamp")
        epoch10 = re.match("^[0-9]{10}$", alert_args['timestamp'])
        if epoch10 is not None:
            alert_args['timestamp'] = alert_args['timestamp'] * 1000
    if not helper.get_param("th_unique_id"):
        alert_args['unique'] = "oneEvent"
    else:
        alert_args['unique'] = helper.get_param("th_unique_id")
    if not helper.get_param("th_title"):
        alert_args['title'] = "notable event"
    else:
        alert_args['title'] = helper.get_param("th_title")
    if not helper.get_param("th_description"):
        alert_args['description'] = "No description provided."
    else:
        alert_args['description'] = helper.get_param("th_description")
    myTags = helper.get_param("th_tags")
    if myTags in [None, '']:
        alert_args['tags'] = []
    else:
        tags = []
        tag_list = myTags.split(',')
        for tag in tag_list:
            if tag not in tags:
                tags.append(tag)
        alert_args['tags'] = tags
    scope = int(helper.get_param("th_scope"))
    helper.log_debug("[X304] scope: {} ".format(scope))
    if scope == 0:
        alert_args['scope'] = True
    else:
        alert_args['scope'] = False
    # Get numeric values from alert form
    alert_args['severity'] = int(helper.get_param("th_severity"))
    alert_args['tlp'] = int(helper.get_param("th_tlp"))
    alert_args['pap'] = int(helper.get_param("th_pap"))

    config_args.update(alert_args)
    return config_args


def create_alert(helper, config, app_name):
    # iterate through each row, cleaning multivalue fields
    # and then adding the attributes under same alert key
    # this builds the dict alerts
    data_type = get_datatype_dict(helper, config, app_name)
    custom_field_type = get_customField_dict(helper, config, app_name)
    alert_refererence = 'SPK' + str(int(time.time()))
    helper.log_debug("[HA301] alert_refererence: {}".format(alert_refererence))
    alerts = dict()
    events = helper.get_events()
    for row in events:
        # Splunk makes a bunch of dumb empty multivalue fields
        # we filter those out here
        row = {key: value for key, value in row.items() if not key.startswith("__mv_")}
        # find the field name used for a unique identifier
        sourceRef = alert_refererence
        if config['unique'] in row:
            newSource = str(row[config['unique']])
            if newSource not in [None, '']:
                # grabs that field's value and assigns it to our sourceRef
                sourceRef = newSource
        helper.log_debug("[HA304] sourceRef: {} ".format(sourceRef))
        # check if the field th_alert_id exists and strip it from the row.
        # if exists and valid it will be used to update alert
        # if 'th_alert_id' in row:
        #     # grabs that field's value and assigns it to
        #     artifactAlertId = str(row.pop("th_alert_id"))
        #     valid_alert_id = re.match("^[0-9a-f]{32}$", artifactAlertId)
        #     if valid_alert_id is None:
        #         artifactAlertId = None
        # else:
        #     artifactAlertId = None
        # check if the field th_inline_tags exists and strip it from the row.
        # The comma-separated values will be used as tags attached to artifacts
        artifactTags = []
        if 'th_inline_tags' in row:
            # grabs that field's value and assigns it to
            inline_tags = str(row.pop("th_inline_tags"))
            if "," in inline_tags:
                artifactTags = inline_tags.split(',')
            else:
                artifactTags = [inline_tags]
        # check if the field th_msg exists and strip it from the row.
        # The value will be used as message attached to artifacts
        if 'th_msg' in row:
            # grabs that field's value and assigns it to
            artifactMessage = str(row.pop("th_msg"))
        else:
            artifactMessage = ''
        helper.log_debug("[HA332] artifact message: {} ".format(artifactMessage))
        helper.log_debug("[HA331] artifact tags: {} ".format(artifactTags))
        # helper.log_debug("[HA333] inline alert id  {} ".format(artifactAlertId))

        # check if artifacts have been stored for this sourceRef.
        # If yes, retrieve them to add new ones from this row
        if sourceRef in alerts:
            alert = alerts[sourceRef]
            artifacts = list(alert["artifacts"])
            customFields = dict(alert['customFields'])
        else:
            alert = dict()
            artifacts = []
            customFields = dict()
        # check if title contains a field name instead of a string.
        # if yes, strip it from the row and assign value to title
        alert['title'] = config['title']
        if config['title'] in row:
            newTitle = str(row.pop(config['title']))
            if newTitle not in [None, '']:
                alert['title'] = newTitle
        # check if description contains a field name instead of a string.
        # if yes, strip it from the row and assign value to description
        alert['description'] = config['description']
        if config['description'] in row:
            newDescription = str(row.pop(config['description']))
            if newDescription not in [None, '']:
                alert['description'] = newDescription
        # find the field name used for a valid timestamp
        # and strip it from the row
        alert['timestamp'] = config['timestamp']
        if config['timestamp'] in row:
            newTimestamp = row.pop(config['timestamp'])
            helper.log_debug(
                "[HA305] new Timestamp from row: {} ".format(newTimestamp)
            )
            epoch10 = re.match("^[0-9]{10}$", newTimestamp)
            epoch13 = re.match("^[0-9]{13}$", newTimestamp)
            if epoch13 is not None:
                alert['timestamp'] = int(newTimestamp)
            elif epoch10 is not None:
                alert['timestamp'] = int(newTimestamp) * 1000
        helper.log_debug(
            "[HA306] alert timestamp: {} ".format(alert['timestamp'])
        )
        # now we take those KV pairs to add to dict
        for key, value in row.items():
            cTags = artifactTags[:]
            if value != "":
                helper.log_debug('[HA320] field to process: {}'.format(key))
                custom_msg = ''
                artifact_key = ''
                cTLP = ''
                if ':' in key:
                    helper.log_debug('[HA321] composite fieldvalue: {}'.format(key))
                    dType = key.split(':', 1)
                    key = str(dType[0])
                    # extract TLP at observable level
                    # it is on letter W G A or R fappended to field name
                    observable_tlp_check = re.match("^(W|G|A|R)$", str(dType[1]))
                    if observable_tlp_check is not None:
                        cTLP = OBSERVABLE_TLP[dType[1]]
                        cTags.append(OBSERVABLE_TLP[str(cTLP)])
                    else:
                        custom_msg = str(dType[1])
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
                elif config['scope'] is False:
                    helper.log_debug(
                        '[HA323] key is added as another artifact (scope is False): {} '.format(key)
                    )
                    artifact_key = 'other'

                if artifact_key not in [None, '']:
                    cMsg = 'field: ' + str(key)
                    if custom_msg not in [None, '']:
                        cMsg = custom_msg + ' - ' + cMsg
                    if artifactMessage not in [None, '']:
                        cMsg = artifactMessage + ' - ' + cMsg
                    if '\n' in value:  # was a multivalue field
                        helper.log_debug('[HA324] value is not a simple string: {} '.format(value))
                        values = value.split('\n')
                        for val in values:
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

    # actually send the request to create the alert; fail gracefully
    for srcRef in alerts.keys():
        payload = json.dumps(
            dict(
                title=alerts[srcRef]['title'],
                date=int(alerts[srcRef]['timestamp']),
                description=alerts[srcRef]['description'],
                tags=config['tags'],
                severity=config['severity'],
                tlp=config['tlp'],
                type=config['type'],
                artifacts=alerts[srcRef]['artifacts'],
                customFields=alerts[srcRef]['customFields'],
                source=config['source'],
                caseTemplate=config['caseTemplate'],
                sourceRef=srcRef
            )
        )
        # set proper headers
        url = config['thehive_url'] + '/api/alert'
        auth = config['thehive_key']
        # client cert file
        client_cert = config['client_cert_full_path']

        headers = {'Content-type': 'application/json'}
        headers['Authorization'] = 'Bearer ' + auth
        headers['Accept'] = 'application/json'

        helper.log_debug('[HA315] DEBUG payload={}'.format(payload))
        # post alert
        response = requests.post(url, headers=headers, data=payload,
                                 verify=False, cert=client_cert,
                                 proxies=config['proxies'])

        if response.status_code in (200, 201, 204):
            # log response status
            helper.log_info(
                "[HA316] INFO theHive alert is successful created. "
                "url={}, HTTP status={}".format(url, response.status_code)
            )
        else:
            # somehow we got a bad response code from thehive
            helper.log_error(
                "[HA317] ERROR theHive alert creation has failed. "
                "url={}, data={}, HTTP Error={}, content={}"
                .format(url, payload, response.status_code, response.text)
            )
