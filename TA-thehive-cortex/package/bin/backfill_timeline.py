# encoding = utf-8
import ta_thehive_cortex_declare
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

class BACKFILL_TIMELINE(smi.Script):
    def __init__(self):
        super(BACKFILL_TIMELINE, self).__init__()

    def get_scheme(self):
        scheme = smi.Scheme('backfill_timeline')
        scheme.description = 'TheHive: Timeline Events - Backfill'
        scheme.use_external_validation = True
        scheme.streaming_mode_xml = True
        scheme.use_single_instance = False

        scheme.add_argument(smi.Argument('name', title='Name', description='Name', required_on_create=True))
        scheme.add_argument(smi.Argument('instance_id', required_on_create=False))
        scheme.add_argument(smi.Argument('backfill_start', required_on_create=True))
        scheme.add_argument(smi.Argument('backfill_end', required_on_create=True))
        scheme.add_argument(smi.Argument('timeline_event_kinds', required_on_create=False))
        scheme.add_argument(smi.Argument('max_events_per_case', required_on_create=False))
        scheme.add_argument(smi.Argument('max_size_value', required_on_create=False))
        scheme.add_argument(smi.Argument('fields_removal', required_on_create=False))
        return scheme

    def stream_events(self, inputs, ew):
        globals.initialize_globals()
        exec_id = str(uuid.uuid4())[:8]
        stanza = list(inputs.inputs.keys())[0]
        input_item = inputs.inputs[stanza]
        custom_logger = setup_logging("backfill_timeline")

        class MockHelper:
            def __init__(self, item, stanza_name, logger, inputs_obj, eid):
                self.item = item
                self.stanza = stanza_name
                self.logger = logger
                self.context_meta = {"session_key": inputs_obj.metadata.get("session_key")}
                self.exec_id = eid
            def get_arg(self, key): return self.item.get(key)
            def get_output_index(self): return self.item.get("index", "default")

        helper = MockHelper(input_item, stanza, custom_logger, inputs, exec_id)
        (thehive, configuration, logger_file) = create_thehive_instance_modular_input(
            instance_id=helper.get_arg("instance_id"), 
            helper=helper, 
            acronym="MI-BTL", 
            logger=custom_logger, 
            exec_id=exec_id
        )

        backfill_start = helper.get_arg("backfill_start")
        backfill_end = helper.get_arg("backfill_end")

        def parse_date(date_str, is_end=False):
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    dt = datetime.datetime.strptime(date_str, fmt)
                    if fmt == "%Y-%m-%d" and is_end:
                        dt = dt.replace(hour=23, minute=59, second=59)
                    return int(dt.timestamp() * 1000)
                except ValueError:
                    continue
            raise ValueError(f"Invalid date format: {date_str}")

        try:
            d1 = parse_date(backfill_start)
            d2 = parse_date(backfill_end, is_end=True)
        except ValueError as e:
            logger_file.error(id="MI-BTL-ERR-DATE", message=str(e))
            return

        modular_input_args = {
            "max_events_per_case": int(helper.get_arg("max_events_per_case") or 0),
            "timeline_event_kinds": helper.get_arg("timeline_event_kinds") or "",
            "max_size_value": int(helper.get_arg("max_size_value") or 1000),
            "fields_removal": helper.get_arg("fields_removal") or ""
        }

        filters = Between("_updatedAt", d1, d2)

        try:
            d1_readable = datetime.datetime.fromtimestamp(d1/1000).strftime('%Y-%m-%d %H:%M:%S %Z')
            d2_readable = datetime.datetime.fromtimestamp(d2/1000).strftime('%Y-%m-%d %H:%M:%S %Z')
            logger_file.info(id="1", message=f"Starting backfill timeline collection for interval [from {d1_readable} to {d2_readable}]")
            new_events = thehive.get_case_timeline_events(
                filters=filters, 
                sortby=Desc("_updatedAt"), 
                **modular_input_args
            )

            for event in new_events:
                ew.write_event(smi.Event(
                    time=time.time(),
                    source="thehive:"+stanza, 
                    host=thehive.session.hive_url[8:].split(":")[0], 
                    index=helper.get_output_index(), 
                    sourcetype="thehive:timeline", 
                    data=json.dumps(event)
                ))
            
            logger_file.info(id="2", message=f"Successfully backfilled {len(new_events)} timeline events.")

        except Exception as e:
            logger_file.error(id="ERR", message=f"Error during backfill timeline collection: {str(e)}")

if __name__ == '__main__':
    exit_code = BACKFILL_TIMELINE().run(sys.argv)
    sys.exit(exit_code)