import sys
import os
import json
import unittest
from unittest.mock import MagicMock, patch

# Mock EVERYTHING that is not available locally
mocks = [
    'splunklib', 'splunklib.client', 'solnlib', 'solnlib.log', 
    'solnlib.modular_input', 'solnlib.utils', 'ta_thehive_cortex_declare',
    'certifi', 'common', 'ta_logging', 'requests', 'requests.adapters', 
    'requests.auth', 'urllib3'
]

for mod in mocks:
    sys.modules[mod] = MagicMock()

# Add bin and libs to path
APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(APP_ROOT, 'TA-thehive-cortex', 'package', 'bin'))
sys.path.insert(0, os.path.join(APP_ROOT, 'TA-thehive-cortex', 'package', 'bin', 'ta_thehive_cortex', 'libs'))

# Import TheHive4Splunk AFTER path setup
import thehive

class TestTheHiveStatus(unittest.TestCase):
    def setUp(self):
        # Retrieve credentials from environment variables (loaded from .env if present)
        self.url = os.getenv("THEHIVE_HOST", "http://localhost:9000")
        self.api_key = os.getenv("THEHIVE_API_KEY", "test_key")
        
        # We need to bypass __init__ because it calls LoggerFile and other complex things
        with patch.object(thehive.TheHive4Splunk, '__init__', return_value=None):
            self.thehive = thehive.TheHive4Splunk()
            self.thehive.session = MagicMock()
            self.thehive._logger_file = MagicMock()

    def test_get_instance_status_success(self):
        # Check if method exists (it shouldn't yet)
        if not hasattr(self.thehive, 'get_instance_status'):
            raise AttributeError("Method 'get_instance_status' not found in TheHive4Splunk")

        # Load mock data
        mock_data_path = os.path.join(APP_ROOT, 'tests', 'mocks', 'thehive_status.json')
        with open(mock_data_path, 'r') as f:
            expected_status = json.load(f)

        # Mock session.make_request
        self.thehive.session.make_request.return_value = expected_status

        # Execute
        status = self.thehive.get_instance_status()

        # Verify
        self.thehive.session.make_request.assert_called_once_with("GET", "/api/v1/status")
        self.assertEqual(status['version'], "5.6.1-1")

    def test_get_instance_status_failure(self):
        # Check if method exists
        if not hasattr(self.thehive, 'get_instance_status'):
            self.skipTest("Method not implemented yet")

        # Mock failure
        self.thehive.session.make_request.side_effect = Exception("API Error")

        # Execute & Verify
        with self.assertRaises(Exception):
            self.thehive.get_instance_status()

if __name__ == '__main__':
    unittest.main()
