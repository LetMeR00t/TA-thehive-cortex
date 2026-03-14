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

class BACKFILL_OBSERVABLES(smi.Script):
    def __init__(self):
        super(BACKFILL_OBSERVABLES, self).__init__()

    def get_scheme(self):
        scheme = smi.Scheme('backfill_observables')
        scheme.description = 'Backfill: Observables'
        scheme.use_external_validation = True
        scheme.streaming_mode_xml = True
        scheme.use_single_instance = False

        scheme.add_argument(smi.Argument('name', title='Name', description='Name', required_on_create=True))
        scheme.add_argument(smi.Argument('instance_id', required_on_create=False))
        scheme.add_argument(smi.Argument('backfill_start', required_on_create=True))
        scheme.add_argument(smi.Argument('backfill_end', required_on_create=True))
        scheme.add_argument(smi.Argument('date', required_on_create=False))
        scheme.add_argument(smi.Argument('max_size_value', required_on_create=False))
        scheme.add_argument(smi.Argument('event_mode', required_on_create=False))
        scheme.add_argument(smi.Argument('fields_removal', required_on_create=False))
        scheme.add_argument(smi.Argument('extra_data', required_on_create=False))
        return scheme

    def stream_events(self, inputs, ew):
        globals.initialize_globals()
        exec_id = str(uuid.uuid4())[:8]
        stanza = list(inputs.inputs.keys())[0]
        input_item = inputs.inputs[stanza]
        custom_logger = setup_logging("backfill_observables")
        
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
        (thehive, configuration, logger_file) = create_thehive_instance_modular_input(instance_id=helper.get_arg("instance_id"), helper=helper, acronym="MI-BOB", logger=custom_logger, exec_id=exec_id)

        # Backfill specific logic
        backfill_start = helper.get_arg("backfill_start")
        backfill_end = helper.get_arg("backfill_end")

        def parse_date(date_str, is_end=False):
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    dt = datetime.datetime.strptime(date_str, fmt)
                    if fmt == "%Y-%m-%d" and is_end:
                        dt = dt.replace(hour=23, minute=59, second=59)
                    return int(dt.timestamp())
                except ValueError:
                    continue
            raise ValueError(f"Invalid date format for backfill: {date_str}. Expected YYYY-MM-DD, YYYY-MM-DDTHH:MM:SS or YYYY-MM-DD HH:MM:SS")

        if backfill_start and backfill_end:
            try:
                d1 = parse_date(backfill_start)
                d2 = parse_date(backfill_end, is_end=True)
            except ValueError as e:
                helper.log_error(str(e))
                return

            modular_input_args = {
                "max_size_value": int(helper.get_arg("max_size_value")) if helper.get_arg("max_size_value") else 1000,
                "event_mode": helper.get_arg("event_mode") or "detailed",
                "fields_removal": helper.get_arg("fields_removal") or "",
                "extra_data": helper.get_arg("extra_data") or "",
            }

            dates = (helper.get_arg("date") or "").split(",") if isinstance(helper.get_arg("date"), str) else (helper.get_arg("date") or ["_updatedAt", "_createdAt"])

            for date_field in dates:
                modular_input_args["date"] = date_field
                date_mode = date_field.lstrip("_")
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

                new_events = thehive.get_observables_events(filters=filters, **modular_input_args)
                for event in new_events:
                    ew.write_event(smi.Event(source="thehive:"+stanza, host=thehive.session.hive_url[8:], index=helper.get_output_index(), sourcetype="thehive:observables:"+date_mode, data=json.dumps(event)))
                logger_file.info(id="70", message=f"{str(len(new_events))} events (date: {date_mode}) were recovered.")

if __name__ == '__main__':
    exit_code = BACKFILL_OBSERVABLES().run(sys.argv)
    sys.exit(exit_code)
