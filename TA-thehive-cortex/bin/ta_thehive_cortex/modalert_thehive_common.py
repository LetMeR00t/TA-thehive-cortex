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
import hashlib
import os
import re
import time
import datetime
import random
from thehive import TheHive
from thehive4py.types.observable import InputObservable
from thehive4py.types.custom_field import InputCustomField
from thehive4py.types.procedure import InputProcedure

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


def create_datatype_lookup(helper):
    """ This function is used to create a datatype lookup if it doesn't exist """

    # if it does not exist, create thehive_datatypes.csv
    _SPLUNK_PATH = os.environ['SPLUNK_HOME']
    directory = os.path.join(_SPLUNK_PATH, 'etc', 'apps', "TA-thehive-cortex", 'lookups')
    th_dt_filename = os.path.join(directory, 'thehive_datatypes.csv')
    helper.log_debug("[CAA-THC-1] Directory found: " + str(directory))

    if not os.path.exists(th_dt_filename):
        # file th_dt_filename.csv doesn't exist. Create the file
        observables = list()
        observables.append(['field_name', 'field_type', 'datatype', 'regex', 'description'])
        for dt in dataTypeList:
            observables.append([dt, 'observable', dt, '', ''])
        try:
            if not os.path.exists(directory):
                os.makedirs(directory)
            with open(th_dt_filename, 'w') as file_object:
                csv_writer = csv.writer(file_object, delimiter=',')
                for observable in observables:
                    csv_writer.writerow(observable)
        except IOError:
            helper.log_error("[CAA-THC-5-ERROR] FATAL {} could not be opened in write mode".format(th_dt_filename))

def get_datatype_dict(helper):
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
        create_datatype_lookup(helper)
    if not dataType_dict:
        dataType_dict = dict()
        for dt in dataTypeList:
            dataType_dict[dt] = dt
        helper.log_debug("[CAA-THC-20] dataType_dict built from inline table")
    return dataType_dict

def extract_field(helper, row, field):
    """ This function is used to extract information from a potential field in a row and sanitize it if needed. If the field is not found, use the field name directly as value """

    result = field
    # Check if the given "field" is actually a field from the search results
    if field in row:
        # A field is found
        newValue = str(row[field])
        if newValue not in [None, '']:
            result = newValue
    return result

def parse_events(helper, thehive: TheHive, alert_args, defaults, target):
    # iterate through each row, cleaning multivalue fields
    # and then adding the attributes under same alert key
    # this builds the dict parsed_events
    data_type = get_datatype_dict(helper)
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
        alert = dict()

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
                sourceRef = "SPLUNK_JOB:"+ helper.sid + newSource
            else:
                sourceRef = "SPLUNK_JOB:"+ helper.sid + alert_reference_time
        else:
            sourceRef = "SPLUNK_JOB:"+ helper.sid + alert_reference_time

        helper.log_debug("[CAA-THC-64] sourceRef: {} ".format(sourceRef))

        # Splunk makes a bunch of dumb empty multivalue fields
        # replace value by multivalue if required
        helper.log_debug("[CAA-THC-65] Row before pre-processing: " + str(row))
        for key, value in row.items():
            if not key.startswith("__mv_") and "__mv_" + key in row and row["__mv_" + key] not in [None, '']:
                row[key] = [e[1:len(e) - 1] for e in row["__mv_" + key].split(";")]
        # we filter those out here
        row = {key: value for key, value in row.items() if not key.startswith("__mv_") and key not in ["rid"]}
        helper.log_debug("[CAA-THC-66] Row after pre-processing: " + str(row))

        if 'th_inline_tags' in row:
            # grabs that field's value and assigns it to
            observableTags = list(str(row.pop("th_inline_tags")).split(","))

        # check if the field th_msg exists and strip it from the row.
        # The value will be used as message attached to observables
        if 'th_msg' in row:
            # grabs that field's value and assigns it to
            observableMessage = str(row.pop("th_msg"))
        helper.log_debug("[CAA-THC-75] observable message: {} ".format(observableMessage))
        helper.log_debug("[CAA-THC-76] observable tags: {} ".format(observableTags))

        # check if observables have been stored for this sourceRef.
        # If yes, retrieve them to add new ones from this row
        if sourceRef in parsed_events:
            alert = parsed_events[sourceRef]
            ttps = list(alert["ttps"])
            observables = list(alert["observables"])
            customFields = list(alert['customFields'])

        # check if title contains a field name instead of a string.
        # if yes, strip it from the row and assign value to title
        alert["title"] = extract_field(helper, row, alert_args["title"])

        # check if description contains a field name instead of a string.
        # if yes, strip it from the row and assign value to description
        alert["description"] = extract_field(helper, row, alert_args["description"])

        # find the field name used for a valid timestamp
        # and strip it from the row

        if alert_args['timestamp'] in row:
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
                    helper.log_debug('[CAA-THC-95] key is an observable: {} '.format(key))
                    observable_key = data_type[key]
                elif key in custom_fields:
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
                    # Expected pattern is: tactic::patternId::occurDate
                    values = value.split("::")
                    # Validate the excepted occurDate format (YYYY-mm-dd)
                    try:
                        datetime.date.fromisoformat(values[2])
                        date_check = True
                    except ValueError as e:
                        date_check = False
                    if len(values) == 3 and values[1].startswith("T") and date_check is True:
                        ttps += [{"tactic": values[0], "patternId": values[1], "occurDate": values[2]}]
                        helper.log_debug('[CAA-THC-108] ttp was parsed correctly and added to the alert: {}'.format(value))
                    else:
                        helper.error('[CAA-THC-109-ERROR] ttp field was detected but malformed, expected one value with the pattern \"tactic::patternId::occurDate\" with occurDate as \"YYYY-mm-dd\", got: {}'.format(value))


                if observable_key not in [None, '']:
                    helper.log_debug("[CAA-THC-110] Processing observable key: " + str(observable_key) + " (" + str(value) + ") (" + observableMessage + ")")
                    cTags.append('field:' + str(key))
                    if isinstance(value,list) :  # was a multivalue field
                        helper.log_debug('[CAA-THC-111] value is not a simple string: {} '.format(value))
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
            helper.log_debug("[CAA-THC-116] No observable found for an alert: " + str(alert))

        # Process customFields and TTPs
        alert['customFields'] = [InputCustomField(cf) for cf in customFields]
        alert['ttps'] = [InputProcedure(ttp) for ttp in ttps]

        # Store the parsed event
        parsed_events[sourceRef] = alert


    return parsed_events