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

class TestTheHiveTasks(unittest.TestCase):
    def setUp(self):
        # We need to bypass __init__ because it calls LoggerFile and other complex things
        with patch.object(thehive.TheHive4Splunk, '__init__', return_value=None):
            self.thehive = thehive.TheHive4Splunk()
            self.thehive.session = MagicMock()
            self.thehive._logger_file = MagicMock()
            # Mock the task endpoint
            self.thehive.task = MagicMock()

    def test_get_tasks_events_success(self):
        # Check if method exists (it shouldn't yet)
        if not hasattr(self.thehive, 'get_tasks_events'):
            raise AttributeError("Method 'get_tasks_events' not found in TheHive4Splunk")

        # Load mock data
        mock_data_path = os.path.join(APP_ROOT, 'tests', 'mocks', 'thehive_task.json')
        with open(mock_data_path, 'r') as f:
            mock_task = json.load(f)

        # Mock self.task.get_tasks
        self.thehive.task.get_tasks.return_value = [mock_task]

        # Execute
        tasks = self.thehive.get_tasks_events(interval=300, date_field="_updatedAt")

        # Verify
        self.thehive.task.get_tasks.assert_called_once()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]['id'], "~40968")
        self.assertEqual(tasks[0]['caseId'], "~12345")

if __name__ == '__main__':
    unittest.main()
