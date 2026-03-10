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

class BACKFILL_ALERTS_CASES(smi.Script):
    def __init__(self):
        super(BACKFILL_ALERTS_CASES, self).__init__()

    def get_scheme(self):
        scheme = smi.Scheme('backfill_alerts_cases')
        scheme.description = 'Backfill: Alerts & Cases'
        scheme.use_external_validation = True
        scheme.streaming_mode_xml = True
        scheme.use_single_instance = False

        scheme.add_argument(smi.Argument('name', title='Name', description='Name', required_on_create=True))
        scheme.add_argument(smi.Argument('instance_id', required_on_create=False))
        scheme.add_argument(smi.Argument('type', required_on_create=False))
        scheme.add_argument(smi.Argument('backfill_start', required_on_create=True))
        scheme.add_argument(smi.Argument('backfill_end', required_on_create=True))
        scheme.add_argument(smi.Argument('date', required_on_create=False))
        scheme.add_argument(smi.Argument('max_size_value', required_on_create=False))
        scheme.add_argument(smi.Argument('fields_removal', required_on_create=False))
        scheme.add_argument(smi.Argument('additional_information', required_on_create=False))
        scheme.add_argument(smi.Argument('extra_data', required_on_create=False))
        return scheme

    def stream_events(self, inputs, ew):
        globals.initialize_globals()
        exec_id = str(uuid.uuid4())[:8]
        stanza = list(inputs.inputs.keys())[0]
        input_item = inputs.inputs[stanza]
        custom_logger = setup_logging("backfill_alerts_cases")
        
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
                try:
                    entities = entity.getEntities('storage/passwords', namespace='TA-thehive-cortex', owner='nobody', sessionKey=self.session_key)
                    for _, ent in entities.items():
                        if ent.get('username') == username:
                            return [username, ent.get('clear_password')]
                except Exception as e:
                    self.log_error(f"Error retrieving credentials for {username}: {str(e)}")
                return [username, ""]

        helper = MockHelper(input_item, stanza, custom_logger, inputs, exec_id)
        (thehive, configuration, logger_file) = create_thehive_instance_modular_input(instance_id=helper.get_arg("instance_id"), helper=helper, acronym="MI-BAC", logger=custom_logger)
        logger_file.exec_id = exec_id

        # Backfill specific logic
        backfill_start = helper.get_arg("backfill_start")
        backfill_end = helper.get_arg("backfill_end")

        if backfill_start and backfill_end:
            try:
                d1 = int(datetime.datetime.strptime(backfill_start, "%Y-%m-%dT%H:%M:%S").timestamp())
                d2 = int(datetime.datetime.strptime(backfill_end, "%Y-%m-%dT%H:%M:%S").timestamp())
            except ValueError:
                try:
                    d1 = int(datetime.datetime.strptime(backfill_start, "%Y-%m-%d %H:%M:%S").timestamp())
                    d2 = int(datetime.datetime.strptime(backfill_end, "%Y-%m-%d %H:%M:%S").timestamp())
                except ValueError as e:
                    helper.log_error(f"Invalid date format for backfill: {str(e)}")
                    return

            types = helper.get_arg("type")
            if types is None: types = ["alerts", "cases"]
            elif isinstance(types, str): types = types.split(",")

            selected_dates = helper.get_arg("date") or []
            if isinstance(selected_dates, str): selected_dates = selected_dates.split(",")
            dates = selected_dates if selected_dates else ["_updatedAt", "_createdAt", "startDate"]

            modular_input_args = {
                "max_size_value": int(helper.get_arg("max_size_value")) if helper.get_arg("max_size_value") else 1000,
                "fields_removal": helper.get_arg("fields_removal") or "",
                "additional_information": (helper.get_arg("additional_information") or "").split(",") if isinstance(helper.get_arg("additional_information"), str) else (helper.get_arg("additional_information") or []),
                "extra_data": (helper.get_arg("extra_data") or "").split(",") if isinstance(helper.get_arg("extra_data"), str) else (helper.get_arg("extra_data") or [])
            }

            for input_type in types:
                for date_field in dates:
                    modular_input_args["type"] = input_type
                    modular_input_args["date"] = date_field
                    date_mode = date_field.replace("_", "last_")
                    filters = Between(date_field, d1 * 1000, d2 * 1000)
                    
                    if input_type == "cases":
                        (new_events, events_tasks) = thehive.get_cases_events(filters=filters, sortby=Desc(date_field), **modular_input_args)
                        for task in events_tasks:
                            ew.write_event(smi.Event(source="thehive:"+stanza, host=thehive.session.hive_url[8:], index=helper.get_output_index(), sourcetype="thehive:"+date_mode+":case_tasks", data=json.dumps(task)))
                    elif input_type == "alerts":
                        new_events = thehive.get_alerts_events(filters=filters, **modular_input_args)

                    for event in new_events:
                        ew.write_event(smi.Event(source="thehive:"+stanza, host=thehive.session.hive_url[8:], index=helper.get_output_index(), sourcetype="thehive:"+date_mode+":"+input_type, data=json.dumps(event)))

                    logger_file.info(id="70", message=f"{str(len(new_events))} events (type: {input_type}, date: {date_mode}) were recovered.")

if __name__ == '__main__':
    exit_code = BACKFILL_ALERTS_CASES().run(sys.argv)
    sys.exit(exit_code)
