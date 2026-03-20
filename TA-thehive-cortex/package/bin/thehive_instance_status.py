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

class THEHIVE_INSTANCE_STATUS(smi.Script):
    def __init__(self):
        super(THEHIVE_INSTANCE_STATUS, self).__init__()

    def get_scheme(self):
        scheme = smi.Scheme('thehive_instance_status')
        scheme.description = 'TheHive: Instance Status'
        scheme.use_external_validation = True
        scheme.streaming_mode_xml = True
        scheme.use_single_instance = False

        scheme.add_argument(smi.Argument('name', title='Name', description='Name', required_on_create=True))
        scheme.add_argument(smi.Argument('instance_id', required_on_create=False))
        scheme.add_argument(smi.Argument('fields_removal', required_on_create=False))
        return scheme

    def stream_events(self, inputs, ew):
        globals.initialize_globals()
        exec_id = str(uuid.uuid4())[:8]
        stanza = list(inputs.inputs.keys())[0]
        input_item = inputs.inputs[stanza]
        custom_logger = setup_logging("thehive_instance_status")

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
            acronym="MI-THIS", 
            logger=custom_logger, 
            exec_id=exec_id
        )

        # Retrieve arguments
        fields_removal = helper.get_arg("fields_removal") or ""

        now = time.time()
        
        try:
            logger_file.info(id="1", message="Starting instance status collection")
            status = thehive.get_instance_status()

            if status:
                # Post-processing: Fields removal if requested
                if fields_removal:
                    from common import Utils
                    utils = Utils(logger_file=logger_file)
                    status = utils.remove_unwanted_keys_from_dict(
                        d=status, l=fields_removal.split(",")
                    )

                # Add metadata for Splunk
                status["instance_id"] = helper.get_arg("instance_id")
                status["collection_time"] = int(now)

                # Simple host extraction from URL
                host = thehive.session.hive_url.split("//")[-1].split(":")[0].split("/")[0]

                # Index the event
                ew.write_event(smi.Event(
                    time=now,
                    source="thehive:"+stanza, 
                    host=host,
                    index=helper.get_output_index(), 
                    sourcetype="thehive:status", 
                    data=json.dumps(status)
                ))

                logger_file.info(id="2", message="Successfully indexed instance status.")

        except Exception as e:
            logger_file.error(id="ERR", message=f"Error during instance status collection: {str(e)}")

if __name__ == '__main__':
    exit_code = THEHIVE_INSTANCE_STATUS().run(sys.argv)
    sys.exit(exit_code)
