import sys
import os
import json
import unittest
from unittest.mock import MagicMock, patch

# Simple selective mocking
mocks = [
    'splunk', 'splunk.entity', 'splunklib', 'splunklib.client', 
    'splunklib.modularinput', 'solnlib', 'solnlib.log', 
    'solnlib.modular_input', 'solnlib.utils', 
    'ta_thehive_cortex_declare', 'certifi', 'common', 'ta_logging', 
    'requests', 'globals', 'thehive', 'thehive4py', 'thehive4py.client',
    'thehive4py.query.filters', 'thehive4py.query.sort'
]

for mod in mocks:
    sys.modules[mod] = MagicMock()

# Add bin to path
APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(APP_ROOT, 'TA-thehive-cortex', 'package', 'bin'))

import thehive_tasks

class TestTheHiveTasksIntegration(unittest.TestCase):
    def setUp(self):
        self.script = thehive_tasks.THEHIVE_TASKS()
        
    @patch('thehive_tasks.create_thehive_instance_modular_input')
    @patch('thehive_tasks.setup_logging')
    def test_stream_events_success(self, mock_logging, mock_create_mi):
        # Setup mocks
        mock_thehive = MagicMock()
        mock_logger_file = MagicMock()
        mock_create_mi.return_value = (mock_thehive, MagicMock(), mock_logger_file)
        
        # Mock task response (already normalized by thehive.py)
        mock_task = {
            "id": "~40968",
            "caseId": "~12345",
            "title": "Normalized Task",
            "time": 1672534800
        }
        
        mock_thehive.get_tasks_events.return_value = [mock_task]
        mock_thehive.session.hive_url = "http://thehive:9000"

        # Mock inputs and event_writer
        mock_inputs = MagicMock()
        mock_inputs.inputs = {"thehive_tasks://test": {"instance_id": "inst1", "index": "main", "interval": "300"}}
        mock_inputs.metadata = {"session_key": "123"}
        mock_ew = MagicMock()

        # Execute
        self.script.stream_events(mock_inputs, mock_ew)

        # Verify
        mock_thehive.get_tasks_events.assert_called_once()
        self.assertTrue(mock_ew.write_event.called)
        
        # Verify event data
        event = mock_ew.write_event.call_args[0][0]
        # In our simplified test, we don't have the real Event object, but we verify it's called
        self.assertIsNotNone(event)

if __name__ == '__main__':
    unittest.main()
