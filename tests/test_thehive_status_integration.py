import sys
import os
import json
import unittest
from unittest.mock import MagicMock, patch

# Selective mocking to avoid recursion
mocks = [
    'splunk', 'splunk.entity', 'splunklib', 'splunklib.client', 
    'splunklib.modularinput', 'solnlib', 'solnlib.log', 
    'solnlib.modular_input', 'solnlib.utils', 
    'ta_thehive_cortex_declare', 'certifi', 'common', 'ta_logging', 
    'requests', 'globals'
]

for mod in mocks:
    sys.modules[mod] = MagicMock()

# Mock thehive and thehive4py more simply
sys.modules['thehive'] = MagicMock()
sys.modules['thehive4py'] = MagicMock()
sys.modules['thehive4py.client'] = MagicMock()

# Add bin to path
APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(APP_ROOT, 'TA-thehive-cortex', 'package', 'bin'))

import thehive_instance_status

class TestTheHiveStatusIntegration(unittest.TestCase):
    def setUp(self):
        self.script = thehive_instance_status.THEHIVE_INSTANCE_STATUS()
        # Retrieve credentials from environment variables
        self.url = os.getenv("THEHIVE_HOST", "http://localhost:9000")
        self.api_key = os.getenv("THEHIVE_API_KEY", "test_key")
        
    @patch('thehive_instance_status.create_thehive_instance_modular_input')
    @patch('thehive_instance_status.setup_logging')
    def test_stream_events_success(self, mock_logging, mock_create_mi):
        # Setup mocks
        mock_thehive = MagicMock()
        mock_logger_file = MagicMock()
        mock_create_mi.return_value = (mock_thehive, MagicMock(), mock_logger_file)
        
        # Mock status response
        mock_data_path = os.path.join(APP_ROOT, 'tests', 'mocks', 'thehive_status.json')
        with open(mock_data_path, 'r') as f:
            mock_status = json.load(f)
        mock_thehive.get_instance_status.return_value = mock_status
        mock_thehive.session.hive_url = self.url

        # Mock inputs and event_writer
        mock_inputs = MagicMock()
        mock_inputs.inputs = {"thehive_instance_status://test": {"instance_id": "inst1", "index": "main"}}
        mock_inputs.metadata = {"session_key": "123"}
        mock_ew = MagicMock()

        # Execute
        self.script.stream_events(mock_inputs, mock_ew)

        # Verify
        mock_thehive.get_instance_status.assert_called_once()
        self.assertTrue(mock_ew.write_event.called)
        
        # Verify event content
        event = mock_ew.write_event.call_args[0][0]
        event_data = json.loads(event._data)
        self.assertEqual(event_data['version'], "5.6.1-1")
        self.assertEqual(event_data['instance_id'], "inst1")

if __name__ == '__main__':
    unittest.main()
