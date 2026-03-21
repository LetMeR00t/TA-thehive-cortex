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

class THEHIVE_TASKS(smi.Script):
    def __init__(self):
        super(THEHIVE_TASKS, self).__init__()

    def get_scheme(self):
        scheme = smi.Scheme('thehive_tasks')
        scheme.description = 'TheHive: Tasks'
        scheme.use_external_validation = True
        scheme.streaming_mode_xml = True
        scheme.use_single_instance = False

        scheme.add_argument(smi.Argument('name', title='Name', description='Name', required_on_create=True))
        scheme.add_argument(smi.Argument('instance_id', required_on_create=False))
        scheme.add_argument(smi.Argument('date_field', required_on_create=False))
        scheme.add_argument(smi.Argument('extra_data', required_on_create=False))
        scheme.add_argument(smi.Argument('max_size_value', required_on_create=False))
        scheme.add_argument(smi.Argument('fields_removal', required_on_create=False))
        return scheme

    def stream_events(self, inputs, ew):
        globals.initialize_globals()
        exec_id = str(uuid.uuid4())[:8]
        stanza = list(inputs.inputs.keys())[0]
        input_item = inputs.inputs[stanza]
        custom_logger = setup_logging("thehive_tasks")

        # Minimal Helper for create_thehive_instance_modular_input
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
            acronym="MI-THTSK",
            logger=custom_logger,
            exec_id=exec_id
        )

        # Retrieve arguments
        date_field = helper.get_arg("date_field") or "updatedAt"
        extra_data = helper.get_arg("extra_data") or ""
        max_size_value = int(helper.get_arg("max_size_value") or 1000)
        fields_removal = helper.get_arg("fields_removal") or ""

        # Logic for incremental polling
        interval = int(input_item.get("interval", 300))
        now = time.time()
        # Floor now to the minute (or interval) to avoid seconds shift
        now = now - (now % interval)
        d2 = int(now * 1000)
        d1 = int((now - interval) * 1000)

        # Map UI choice to API field
        api_date_field = "_" + date_field if not date_field.startswith("_") else date_field
        filters = Between(api_date_field, d1, d2)

        modular_input_args = {
            "date_field": date_field,
            "extra_data": extra_data,
            "max_size_value": max_size_value,
            "fields_removal": fields_removal
        }

        try:
            d1_readable = datetime.datetime.fromtimestamp(d1/1000).strftime('%Y-%m-%d %H:%M:%S %Z')
            d2_readable = datetime.datetime.fromtimestamp(d2/1000).strftime('%Y-%m-%d %H:%M:%S %Z')
            logger_file.info(id="1", message=f"Starting tasks collection for interval [from {d1_readable} to {d2_readable}] using {api_date_field}")
            
            new_events = thehive.get_tasks_events(
                filters=filters,
                sortby=Desc(api_date_field),
                **modular_input_args
            )

            for event in new_events:
                # Use the collection time for Splunk's _time
                ew.write_event(smi.Event(
                    time=now,
                    source="thehive:"+stanza,
                    host=thehive.session.hive_url.split("//")[-1].split(":")[0].split("/")[0],
                    index=helper.get_output_index(),
                    sourcetype="thehive:tasks",
                    data=json.dumps(event)
                ))

            logger_file.info(id="2", message=f"Successfully indexed {len(new_events)} tasks.")

        except Exception as e:
            logger_file.error(id="ERR", message=f"Error during tasks collection: {str(e)}")

if __name__ == '__main__':
    exit_code = THEHIVE_TASKS().run(sys.argv)
    sys.exit(exit_code)
