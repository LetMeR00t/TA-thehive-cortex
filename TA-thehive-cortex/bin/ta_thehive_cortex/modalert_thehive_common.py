# encoding = utf-8
#!/usr/bin/env python
# Common code for cases and parsed_events
#
# Author: Alexandre Demeyer <letmer00t@gmail.com>
# Inspired by: Remi Seguy <remg427@gmail.com>
#
# Copyright: LGPLv3 (https://www.gnu.org/licenses/lgpl-3.0.txt)
# Feel free to use the code, but please share the changes you've made

import csv
import gzip
import os
import re
import time
import datetime
from tomark import Tomark
from thehive import TheHive
from thehive4py.types.observable import InputObservable
from thehive4py.types.custom_field import InputCustomField
from thehive4py.types.procedure import InputProcedure
from common import Settings

__author__ = "Alexandre Demeyer"
__maintainer__ = "Alexandre Demeyer"
__email__ = "letmer00t@gmail.com"

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

SEVERITY = {
    "informational": 1,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4
}

# All available data types
dataTypeList = [
    "autonomous-system",
    "domain",
    "file",
    "filename",
    "fqdn",
    "hash",
    "hostname",
    "ip",
    "mail",
    "mail-subject",
    "other",
    "regexp",
    "registry",
    "uri_path",
    "url"
]


def create_datatype_lookup(helper, thehive):
    """ This function is used to create a datatype lookup if it doesn't exist """

    dataType_dict = dict()
    # if it does not exist, create thehive_datatypes.csv
    _SPLUNK_PATH = os.environ['SPLUNK_HOME']
    directory = os.path.join(_SPLUNK_PATH, 'etc', 'apps', "TA-thehive-cortex", 'lookups')
    th_dt_filename = os.path.join(directory, 'thehive_datatypes.csv')

    if not os.path.exists(th_dt_filename):
        # file th_dt_filename.csv doesn't exist. Create the file
        observables = list()
        observables.append(['field_name', 'field_type', 'datatype', 'description'])

        # Get the list of datatypes from TheHive itself
        th_datatypes = thehive.observable_type.list()
        helper.log_debug("[CAA-THC-2] Datatypes recovered from TheHive: " + str(th_datatypes))

        # Parse the response
        for dt in th_datatypes:
            observables.append([dt["name"], "observable", dt["name"], ""])
            dataType_dict[dt["name"]] = dt["name"]

        # Write the file
        try:
            if not os.path.exists(directory):
                os.makedirs(directory)
            with open(th_dt_filename, 'w', newline='') as file_object:
                csv_writer = csv.writer(file_object, delimiter=',')
                for observable in observables:
                    csv_writer.writerow(observable)
        except IOError:
            helper.log_error("[CAA-THC-5-ERROR] FATAL {} could not be opened in write mode".format(th_dt_filename))

    return dataType_dict    

def get_datatype_dict(helper, thehive):
    """ This function is used to recover information from a lookup that contain datatypes """

    dataType_dict = dict()
    _SPLUNK_PATH = os.environ['SPLUNK_HOME']
    directory = os.path.join(_SPLUNK_PATH, 'etc', 'apps', "TA-thehive-cortex", 'lookups')
    th_dt_filename = os.path.join(directory, 'thehive_datatypes.csv')
    helper.log_debug("[CAA-THC-10] Directory found: " + str(directory))

    if os.path.exists(th_dt_filename):
        try:
            # open the file with gzip lib, start making parsed_events
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
                        if row['field_type'] == 'observable':
                            dataType_dict[row['field_name']] = row['datatype']
                helper.log_debug("[CAA-THC-15] dataType_dict built from thehive_datatypes.csv")
            except IOError:  # file thehive_datatypes.csv not readable
                helper.log_error('[CAA-THC-16-ERROR] file {} empty, malformed or not readable'.format(th_dt_filename))
    else:
        dataType_dict = create_datatype_lookup(helper, thehive)
    return dataType_dict

def extract_field(row, field):
    """ This function is used to extract information from a potential field in a row and sanitize it if needed. If the field is not found, use the field name directly as value """

    result = field
    # Check if the given "field" is actually a field from the search results
    if field in row:
        # A field is found
        newValue = str(row[field])
        if newValue not in [None, '']:
            result = newValue
    return result

def parse_events(helper, thehive: TheHive, configuration: Settings, alert_args):
    # iterate through each row, cleaning multivalue fields
    # and then adding the attributes under same alert key
    # this builds the dict parsed_events
    data_type = get_datatype_dict(helper, thehive)
    custom_fields = {cf["name"]:cf for cf in thehive.custom_field.list()}
    alert_reference_time = str(int(time.time()))
    parsed_events = dict()
    events = helper.get_events()
    
    for row in events:
        # Initialize values
        observables = []
        ttps = []
        observableTags = []
        observableMessage = ''
        customFields = []
        events = []
        alert = dict()

        # Splunk makes a bunch of dumb empty multivalue fields
        # replace value by multivalue if required
        helper.log_debug("[CAA-THC-61] Row before pre-processing: " + str(row))
        for key, value in row.items():
            if not key.startswith("__mv_") and "__mv_" + key in row and row["__mv_" + key] not in [None, '']:
                row[key] = [e[1:len(e) - 1] for e in row["__mv_" + key].split(";")]
        # we filter those out here
        row = {key: value for key, value in row.items() if not key.startswith("__mv_") and key not in ["rid"]}
        row_sanitized = row.copy()
        helper.log_debug("[CAA-THC-62] Row after pre-processing: " + str(row))

        # Define thehive alert unique ID (if duplicated, alert creations fails)
        if ("alert_mode" in alert_args and alert_args["alert_mode"] == "es_mode") or ("case_mode" in alert_args and alert_args["case_mode"] == "es_mode"):
            # Check if it's coming from Splunk ES
            if "event_id" in row:
                sourceRef = row["event_id"]
            else:
                sourceRef = helper.sid
        elif alert_args['unique_id_field'] in row:
            newSource = str(row[alert_args['unique_id_field']])
            if newSource not in [None, '']:
                # grabs that field's value and assigns it to our sourceRef
                sourceRef = newSource
                del row_sanitized[alert_args['unique_id_field']]
            else:
                sourceRef = helper.sid + alert_reference_time
        else:
            sourceRef = helper.sid + alert_reference_time

        # Check if sourceRef is not too long, otherwise cut to 127 characters
        if len(sourceRef)>128:
            helper.log_debug("[CAA-THC-63] original sourceRef: {} was cut as it was a string too long (max 128 char).".format(sourceRef))
            sourceRef = sourceRef[0:127]

        helper.log_debug("[CAA-THC-64] sourceRef: {} ".format(sourceRef))

        if 'th_inline_tags' in row:
            del row_sanitized["th_inline_tags"]
            # grabs that field's value and assigns it to
            observableTags = list(str(row.pop("th_inline_tags")).split(","))

        # check if the field th_msg exists and strip it from the row.
        # The value will be used as message attached to observables
        if 'th_msg' in row:
            del row_sanitized["th_msg"]
            # grabs that field's value and assigns it to
            observableMessage = str(row.pop("th_msg"))
            helper.log_debug("[CAA-THC-75] observable message: {} ".format(observableMessage))
            helper.log_debug("[CAA-THC-76] observable tags: {} ".format(observableTags))

        # check if observables have been stored for this sourceRef.
        # If yes, retrieve them to add new ones from this row
        if sourceRef in parsed_events:
            alert = parsed_events[sourceRef]
            events = alert["events"]
            ttps = list(alert["ttps"]) if "ttps" in alert else []
            observables = list(alert["observables"]) if "observables" in alert else []
            customFields = list(alert['customFields']) if "customFields" in alert else []

        # check if title contains a field name instead of a string.
        # if yes, strip it from the row and assign value to title
        if alert_args["title"] == "<inheritance>":
            # Find the most accurate information for the title
            if "search_name" in row:
                # Use this information coming from Splunk ES
                del row_sanitized["search_name"]
                alert["title"] = row["search_name"]
            else:
                # Take the name of the savedsearch itself
                alert["title"] = helper.settings["search_name"]
        elif alert_args["title"]:
            # Field is not null but it's not inheritance, try to format the field
            alert["title"] = extract_field(row, alert_args["title"])
            # Check if sanitization is required
            if alert_args["title"] in row:
                del row_sanitized[alert_args["title"]]
        else:
            # Give a default name
            alert["title"] = "Notable event"

        # check if description contains a field name instead of a string.
        # if yes, strip it from the row and assign value to description
        if alert_args["description"]:
            # Field is not null, try to format the field
            alert["description"] = extract_field(row, alert_args["description"])
            # Check if sanitization is required
            if alert_args["description"] in row:
                del row_sanitized[alert_args["description"]]
        elif "description" in row:
            # Description is provided in the event
            alert["description"] = row["description"]
            del row_sanitized["description"]
        else:
            # Give a default name
            alert["description"] = "No description provided"

        # check if severity is provided or not in the logs (Splunk ES event)
        if "severity" in row:
            alert["severity"] = SEVERITY[row["severity"]]
            del row_sanitized["severity"]
        else:
            alert["severity"] = alert_args['severity']

        # find the field name used for a valid timestamp
        # and strip it from the row
        if alert_args['timestamp'] in row:
            del row_sanitized[alert_args['timestamp']]
            newTimestamp = str(int(float(row.pop(alert_args['timestamp']))))
            helper.log_debug("[CAA-THC-80] new Timestamp from row: {} ".format(newTimestamp))
            epoch10 = re.match("^[0-9]{10}$", newTimestamp)
            epoch13 = re.match("^[0-9]{13}$", newTimestamp)
            if epoch13 is not None:
                alert['timestamp'] = int(float(newTimestamp))
            elif epoch10 is not None:
                alert['timestamp'] = int(float(newTimestamp)) * 1000
            helper.log_debug("[CAA-THC-85] alert timestamp: {} ".format(alert['timestamp']))
        else:
            alert['timestamp'] = alert_args['timestamp']

        # now we take those KV pairs to add to dict
        for key, value in row.items():
            cTags = observableTags[:]
            if value != "":
                helper.log_debug('[CAA-THC-90] field to process: {}'.format(key))
                observable_key = ''
                cTLP = ''
                if ':' in key:
                    helper.log_debug('[CAA-THC-91] composite fieldvalue: {}'.format(key))
                    dType = key.split(':', 1)
                    key = str(dType[0])
                    # extract TLP at observable level
                    # it is on letter W G A or R appended to field name
                    observable_tlp_check = re.match("^(W|G|A|R)$", str(dType[1]))
                    if observable_tlp_check is not None:
                        cTLP = OBSERVABLE_TLP[dType[1]]
                        cTags.append(OBSERVABLE_TLP[str(cTLP)])
                    else:
                        cTags.append(str(dType[1]).replace(" ", "_"))
                if key in data_type:
                    # Check if observables must be kept in the sanitized results or not
                    if not alert_args["description_results_keep_observable"]:
                        del row_sanitized[key]
                    helper.log_debug('[CAA-THC-95] key is an observable: {} '.format(key))
                    observable_key = data_type[key]
                elif key in custom_fields:
                    del row_sanitized[key]
                    custom_type = custom_fields[key]["type"]
                    helper.log_debug('[CAA-THC-96] key is a custom field: {}, with type {} '.format(key,custom_type))
                    custom_field_check = False
                    custom_field = {"name": key}
                    if custom_type == 'string':
                        custom_field_check = True
                        custom_field["value"] = str(value)
                    elif custom_type == 'boolean':
                        is_True = re.match("^(1|y|Y|t|T|true|True)$", value)
                        is_False = re.match("^(0|n|N|f|F|false|False)$", value)
                        if is_True is not None:
                            custom_field_check = True
                            custom_field["value"] = True
                        elif is_False is not None:
                            custom_field_check = True
                            custom_field["value"] = False
                    elif custom_type == 'integer':  # for TheHive4 only
                        try:
                            number = int(value)
                            custom_field_check = True
                            custom_field["value"] = number
                        except ValueError:
                            pass
                    elif custom_type == 'float':  # for TheHive4 only
                        try:
                            number = float(value)
                            custom_field_check = True
                            custom_field["value"] = number
                        except ValueError:
                            pass
                    elif custom_type == 'date':
                        epoch10 = re.match("^[0-9]{10}$", value)
                        epoch13 = re.match("^[0-9]{13}$", value)
                        if epoch13 is not None:
                            custom_field_check = True
                            custom_field["value"] = int(value)
                        elif epoch10 is not None:
                            custom_field_check = True
                            custom_field["value"] = int(value) * 1000
                    if custom_field_check is True:
                        customFields += [custom_field]
                elif alert_args['scope'] is False:
                    helper.log_debug('[CAA-THC-105] key is added as another observable (scope is False): {}'.format(key))
                    observable_key = 'other'
                elif key == "ttp":
                    del row_sanitized["ttp"]
                    # Expected pattern is: tactic::patternId::occurDate
                    values = value.split("::")
                    # Validate the excepted occurDate format (YYYY-mm-dd)
                    try:
                        datetime.date.fromisoformat(values[2])
                        date_check = True
                    except ValueError as e:
                        date_check = False
                    if len(values) == 3 and values[1].startswith("T") and date_check is True:
                        new_ttp = {"tactic": values[0], "patternId": values[1], "occurDate": values[2]}
                        if new_ttp not in ttps:
                            ttps.append(new_ttp)
                            helper.log_debug('[CAA-THC-108] ttp was parsed correctly and added to the alert: {}'.format(value))
                        else:
                            helper.log_debug('[CAA-THC-109] ttp already exist, ignoring duplicates: {}'.format(value))
                    else:
                        helper.error('[CAA-THC-110-ERROR] ttp field was detected but malformed, expected one value with the pattern \"tactic::patternId::occurDate\" with occurDate as \"YYYY-mm-dd\", got: {}'.format(value))


                if observable_key not in [None, '']:
                    helper.log_debug("[CAA-THC-111] Processing observable key: " + str(observable_key) + " (" + str(value) + ") (" + observableMessage + ")")
                    cTags.append('field:' + str(key))
                    if isinstance(value,list) :  # was a multivalue field
                        helper.log_debug('[CAA-THC-112] value is not a simple string: {} '.format(value))
                        for val in value:
                            if val != "":
                                observable = dict(dataType=observable_key,
                                                data=str(val),
                                                message=observableMessage,
                                                tags=cTags
                                                )
                                if cTLP != '':
                                    observable['tlp'] = cTLP
                                helper.log_debug("[CAA-THC-113] new observable is {}".format(observable))
                                if observable not in observables:
                                    observables.append(observable)
                    else:
                        observable = dict(dataType=observable_key,
                                        data=str(value),
                                        message=observableMessage,
                                        tags=cTags
                                        )
                        if cTLP != '':
                            observable['tlp'] = cTLP
                        if observable not in observables:
                            observables.append(observable)

        if observables:
            alert['observables'] = [InputObservable(o) for o in observables]
            helper.log_debug("[CAA-THC-115] observables found for an alert: " + str(observables))
        else:
            alert['observables'] = []
            helper.log_debug("[CAA-THC-116] No observable found for an alert: " + str(alert))

        # Process customFields
        alert['customFields'] = [InputCustomField(cf) for cf in customFields]

        # Process TTPs
        if len(ttps) > 0:
            # TTPs are given manually
            # Ensure that there is no duplicate
            alert['ttps'] = [InputProcedure(ttp) for ttp in ttps]
        elif "annotations.mitre_attack.mitre_tactic" in row:
            # Try to extract them from Splunk ES notable event
            mitre_tactics = row["annotations.mitre_attack.mitre_tactic"]
            mitre_technics = row["annotations.mitre_attack"]
            date = datetime.datetime.fromtimestamp(int(row['_time'])).strftime("%Y-%m-%d") 
            alert['ttps'] = []
            for i in range(0,len(mitre_technics)):
                ttp = {"tactic": mitre_tactics[i], "patternId": mitre_technics[i], "occurDate": date}
                alert['ttps'].append(InputProcedure(ttp))

        # Store original event
        alert["events"] = alert["events"]+[row_sanitized] if "events" in alert else [row_sanitized]
        alert["events_keys"] = list(set(alert["events_keys"]+list(row_sanitized.keys()))) if "events_keys" in alert else list(row_sanitized.keys())

        # Store the parsed event
        parsed_events[sourceRef] = alert

    for sourceRef in parsed_events:
        # Store original events if required
        # check if we need to append the results to the description
        if alert_args["description_results_enable"]:

            # Sanitize dictionnaries 
            # Get all keys from events
            # Check all events for each key
            for k in parsed_events[sourceRef]["events_keys"]:
                count = 0
                total = len(parsed_events[sourceRef]["events"])
                for event in parsed_events[sourceRef]["events"]:
                    # If empty, count + 1
                    if k not in event or event[k] == "":
                        count += 1
                if count == total:
                    # This means that all fields are empty, remove the key
                    for event in parsed_events[sourceRef]["events"]:
                        if k in event:
                            del event[k]

            helper.log_debug("[CAA-THC-77] Append results to description as markdown table")
            parsed_events[sourceRef]['description'] += "\r\nRaw events:\r\n"+Tomark.table(parsed_events[sourceRef]["events"])

        # Remove events
        del parsed_events[sourceRef]["events"]

    return parsed_events
