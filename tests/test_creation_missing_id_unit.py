"""Gitea #32, leftover from #22: a creation response without `_id` must stop.

Both creator helpers logged "creation has failed" when TheHive's response
carried no `_id`, then fell straight through to observable/TTP/attachment
code that all read `new_case["_id"]` / `new_alert["_id"]` -- turning an
already-reported failure into an unrelated KeyError a few lines later, for
the exact object that most needed a legible error. The fix is `continue`:
skip to the next object in the batch, do not touch a key just proven absent.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock

mocks = [
    'splunklib', 'splunklib.client', 'solnlib', 'solnlib.log',
    'solnlib.modular_input', 'solnlib.utils', 'ta_thehive_cortex_declare',
    'certifi', 'common', 'ta_logging', 'requests', 'requests.adapters',
    'requests.auth', 'urllib3', 'splunk', 'splunk.Intersplunk', 'globals',
]

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _isolation import mocks_temporaires  # noqa: E402

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(APP_ROOT, 'TA-thehive-cortex', 'package', 'bin')
for p in (BIN,
          os.path.join(BIN, 'ta_thehive_cortex'),
          os.path.join(BIN, 'ta_thehive_cortex', 'libs')):
    if p not in sys.path:
        sys.path.insert(0, p)

with mocks_temporaires(mocks):
    import modalert_thehive_create_a_new_case_helper as case_module
    import modalert_thehive_create_a_new_alert_helper as alert_module


def _alert_args():
    return {
        "tags": [], "source": "splunk", "caseTemplate": None,
        "type": "internal", "attach_results": 0, "attach_format": 0,
        "dashboard": None,
    }


class TestNoIdMeansSkipTheObject(unittest.TestCase):

    def setUp(self):
        self.helper = MagicMock()
        self.helper.settings = {"results_link": "https://splunk.example/app"}
        self.thehive = MagicMock()
        self.thehive.session.hive_url = "https://thehive.example"

    def test_create_case_does_not_touch_id_when_absent(self):
        parsed = {
            "src1": {
                "title": "t", "timestamp": 0, "description": "d",
                "severity": 2, "tlp": 2, "pap": 2, "customFields": [],
                "ttps": [{"patternId": "T1059"}],
            }
        }
        case_module.parse_events = lambda *a, **k: parsed
        # A response with no "_id": the branch this fix guards.
        case_module.create_with_retry = lambda *a, **k: {"status": "error"}

        try:
            case_module.create_case(self.helper, self.thehive, _alert_args())
        except KeyError as e:
            self.fail(f"fell through to a key the response never had: {e}")

        self.thehive.observable.create_in_case.assert_not_called()

    def test_create_alert_does_not_touch_id_when_absent(self):
        parsed = {
            "src1": {
                "title": "t", "timestamp": 0, "description": "d",
                "severity": 2, "tlp": 2, "pap": 2, "customFields": [],
                "observables": [], "ttps": [{"patternId": "T1059"}],
            }
        }
        alert_module.parse_events = lambda *a, **k: parsed
        alert_module.create_with_retry = lambda *a, **k: {"status": "error"}

        try:
            alert_module.create_alert(self.helper, self.thehive, _alert_args())
        except KeyError as e:
            self.fail(f"fell through to a key the response never had: {e}")

    def test_create_case_still_attaches_ttps_when_id_is_present(self):
        """The fix must skip only the id-less case, not every case."""
        parsed = {
            "src1": {
                "title": "t", "timestamp": 0, "description": "d",
                "severity": 2, "tlp": 2, "pap": 2, "customFields": [],
                "ttps": [{"patternId": "T1059"}],
            }
        }
        case_module.parse_events = lambda *a, **k: parsed
        case_module.create_with_retry = lambda *a, **k: {
            "_id": "~123", "number": 1
        }

        case_module.create_case(self.helper, self.thehive, _alert_args())

        self.thehive.case.create_procedures.assert_called()


if __name__ == '__main__':
    unittest.main()
