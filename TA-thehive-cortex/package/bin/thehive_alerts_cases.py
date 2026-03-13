# encoding = utf-8
import import_declare_test
import os
import sys
import time
import datetime
import json
import logging
import uuid

from splunklib import modularinput as smi
import splunk.entity as entity

# Local application imports
import globals
from thehive import create_thehive_instance_modular_input
from ta_logging import setup_logging
from thehive4py.query.filters import Between
from thehive4py.query.sort import Desc

class THEHIVE_ALERTS_CASES(smi.Script):
    def __init__(self):
        super(THEHIVE_ALERTS_CASES, self).__init__()

    def get_scheme(self):
        scheme = smi.Scheme('thehive_alerts_cases')
        scheme.description = 'TheHive: Alerts & Cases'
        scheme.use_external_validation = True
        scheme.streaming_mode_xml = True
        scheme.use_single_instance = False

        scheme.add_argument(smi.Argument('name', title='Name', description='Name', required_on_create=True))
        scheme.add_argument(smi.Argument('instance_id', required_on_create=False))
        scheme.add_argument(smi.Argument('type', required_on_create=False))
        scheme.add_argument(smi.Argument('additional_information', required_on_create=False))
        scheme.add_argument(smi.Argument('extra_data', required_on_create=False))
        scheme.add_argument(smi.Argument('date', required_on_create=False))
        scheme.add_argument(smi.Argument('max_size_value', required_on_create=False))
        scheme.add_argument(smi.Argument('fields_removal', required_on_create=False))
        return scheme

    def stream_events(self, inputs, ew):
        globals.initialize_globals()
        exec_id = str(uuid.uuid4())[:8]
        stanza = list(inputs.inputs.keys())[0]
        input_item = inputs.inputs[stanza]
        custom_logger = setup_logging("thehive_alerts_cases")
        
        class MockHelper:
            def __init__(self, item, stanza_name, logger, inputs_obj, eid):
                self.item = item
                self.stanza = stanza_name
                self.logger = logger
                self.log_level = "INFO"
                self.session_key = inputs_obj.metadata.get("session_key")
                self.context_meta = {"session_key": self.session_key}
                self.exec_id = eid
            def get_arg(self, key): return self.item.get(key)
            def get_output_index(self): return self.item.get("index", "default")
            def log_debug(self, msg): self.logger.debug(msg)
            def log_info(self, msg): self.logger.info(msg)
            def log_error(self, msg): self.logger.error(msg)
            def new_event(self, **kwargs): return smi.Event(**kwargs)
            def get_user_credential_by_username(self, username):
                self.log_debug(f"Searching credentials for username: {username}")
                try:
                    entities = entity.getEntities('storage/passwords', namespace='TA-thehive-cortex', owner='nobody', sessionKey=self.session_key)
                    for _, ent in entities.items():
                        if ent.get('username') == username:
                            self.log_debug(f"Credentials found for {username}")
                            return [username, ent.get('clear_password')]
                except Exception as e:
                    self.log_error(f"Error retrieving credentials for {username}: {str(e)}")
                self.log_error(f"Credentials NOT FOUND for {username} in TA-thehive-cortex storage/passwords")
                return [username, ""]

        helper = MockHelper(input_item, stanza, custom_logger, inputs, exec_id)
        (thehive, configuration, logger_file) = create_thehive_instance_modular_input(instance_id=helper.get_arg("instance_id"), helper=helper, acronym="MI-THAC", logger=custom_logger, exec_id=exec_id)

        types = helper.get_arg("type")
        if types is None: types = ["alerts", "cases"]
        elif isinstance(types, str): types = types.split(",")

        dates = (helper.get_arg("date") or "").split(",") if isinstance(helper.get_arg("date"), str) else (helper.get_arg("date") or ["_updatedAt", "_createdAt", "startDate", "date"])

        modular_input_args = {
            "max_size_value": int(helper.get_arg("max_size_value")) if helper.get_arg("max_size_value") else 1000,
            "fields_removal": helper.get_arg("fields_removal") or "",
            "additional_information": (helper.get_arg("additional_information") or "").split(",") if isinstance(helper.get_arg("additional_information"), str) else (helper.get_arg("additional_information") or []),
            "extra_data": (helper.get_arg("extra_data") or "").split(",") if isinstance(helper.get_arg("extra_data"), str) else (helper.get_arg("extra_data") or [])
        }

        for input_type in types:
            for date_field in dates:
                # startDate is only for cases, date is only for alerts (occurred time)
                if input_type == "alerts" and date_field == "startDate":
                    continue
                if input_type == "cases" and date_field == "date":
                    continue
                
                # Process independently depending on the additional fields provided
                current_modular_input_args = modular_input_args.copy()
                if input_type == "alerts":
                    current_modular_input_args["additional_information"] = [item for item in modular_input_args["additional_information"] if item in ["observables", "attachments"]]
                    current_modular_input_args["extra_data"] = [item for item in modular_input_args["extra_data"] if item in ["caseNumber", "status"]]
                elif input_type == "cases":
                    current_modular_input_args["additional_information"] = [item for item in modular_input_args["additional_information"] if item in ["tasks", "observables", "attachments", "pages", "ttps"]]
                    current_modular_input_args["extra_data"] = [item for item in modular_input_args["extra_data"] if item in ["status", "alerts"]]

                current_modular_input_args["type"] = input_type
                current_modular_input_args["date"] = date_field
                
                if date_field == "date":
                    date_mode = "occuredDate"
                else:
                    date_mode = date_field.lstrip("_")
                interval = int(input_item.get("interval", 60))
                now = time.time()
                d2 = now - now % 60
                d1 = d2 - interval
                # Robust filter logic
                if d1 is not None and d2 is not None:
                    filters = Between(date_field, int(d1 * 1000), int(d2 * 1000))
                elif d1 is not None:
                    from thehive4py.query.filters import Gte
                    filters = Gte(date_field, int(d1 * 1000))
                elif d2 is not None:
                    from thehive4py.query.filters import Lte
                    filters = Lte(date_field, int(d2 * 1000))
                else:
                    filters = None
                
                try:
                    if input_type == "cases":
                        (new_events, events_tasks) = thehive.get_cases_events(filters=filters, sortby=Desc(date_field), **current_modular_input_args)
                        if "tasks" in current_modular_input_args["additional_information"]:
                            for task in events_tasks:
                                ew.write_event(smi.Event(source="thehive:"+stanza, host=thehive.session.hive_url[8:], index=helper.get_output_index(), sourcetype="thehive:"+date_mode+":tasks", data=json.dumps(task)))
                    elif input_type == "alerts":
                        new_events = thehive.get_alerts_events(filters=filters, **current_modular_input_args)
                    
                    for event in new_events:
                        ew.write_event(smi.Event(source="thehive:"+stanza, host=thehive.session.hive_url[8:], index=helper.get_output_index(), sourcetype="thehive:"+date_mode+":"+input_type, data=json.dumps(event)))
                except Exception as e:
                    logger_file.error(id="MI-ERR", message="Error processing type={} with date_field={}: {}".format(input_type, date_field, str(e)))

if __name__ == '__main__':
    exit_code = THEHIVE_ALERTS_CASES().run(sys.argv)
    sys.exit(exit_code)
