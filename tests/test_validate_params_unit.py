"""Gitea #32: `validate_params()` must gate on what the action actually reads.

Three of the six alert actions (the two creators and the Cortex job) required
six global settings each -- `cortex_max_jobs`, `cortex_sort_jobs`,
`thehive_max_cases`, `thehive_sort_cases`, `thehive_max_alerts`,
`thehive_sort_alerts` -- copy-pasted onto every one of the three regardless of
relevance: a pure-Cortex action required TheHive settings and vice versa.
None of the six is read by object CREATION at all; they size and sort the
JOB/CASE/ALERT LISTING dashboards, and `common.Settings` already falls back to
a working default when a global setting is absent (`getCortexJobsMax` and
friends). A user who never touched those dashboard settings had every
creation action refuse to run.

The other three actions (run_function, add_observables, add_timeline_event)
never checked these six, which is what this file pins as the correct shape:
`validate_params()` reads only ITS OWN parameters.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock

mocks = [
    'splunklib', 'splunklib.client', 'solnlib', 'solnlib.log',
    'solnlib.modular_input', 'solnlib.utils', 'ta_thehive_cortex_declare',
    'certifi', 'common', 'ta_logging', 'requests', 'requests.adapters',
    'requests.auth', 'urllib3', 'splunk', 'splunk.clilib',
    'splunk.clilib.bundle_paths', 'splunk.rest', 'splunk.entity',
    'splunk.util', 'splunk.Intersplunk', 'splunktaucclib',
    'splunktaucclib.splunk_aoblib', 'splunktaucclib.splunk_aoblib.rest_helper',
    'splunktaucclib.splunk_aoblib.setup_util', 'globals',
    'past', 'past.builtins',
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
    import thehive_create_a_new_alert
    import thehive_create_a_new_case
    import cortex_run_a_new_job


IRRELEVANT_GLOBAL_SETTINGS = {
    "cortex_max_jobs", "cortex_sort_jobs",
    "thehive_max_cases", "thehive_sort_cases",
    "thehive_max_alerts", "thehive_sort_alerts",
}


def _worker(module, class_name, own_params, missing_settings=()):
    """An `object.__new__`-built worker: `validate_params()` never needs a
    real Splunk connection, only `get_param`/`get_global_setting`/`log_error`.
    """
    cls = getattr(module, class_name)
    worker = object.__new__(cls)
    worker.log_error = MagicMock()
    worker.get_param = lambda name: own_params.get(name)
    worker.get_global_setting = lambda name: (
        None if name in missing_settings else "irrelevant-but-set"
    )
    return worker


class TestCreatorsIgnoreDashboardOnlySettings(unittest.TestCase):
    """The dashboard-only settings must never block a creation."""

    def test_create_a_new_alert_does_not_require_them(self):
        worker = _worker(
            thehive_create_a_new_alert,
            "AlertActionWorkerthehive_create_a_new_alert",
            {"thehive_instance_id": "inst1", "scope": "0", "severity": "2",
             "tlp": "2", "pap": "2"},
            missing_settings=IRRELEVANT_GLOBAL_SETTINGS,
        )
        self.assertTrue(worker.validate_params())

    def test_create_a_new_case_does_not_require_them(self):
        worker = _worker(
            thehive_create_a_new_case,
            "AlertActionWorkerthehive_create_a_new_case",
            {"thehive_instance_id": "inst1", "scope": "0", "severity": "2",
             "tlp": "2", "pap": "2"},
            missing_settings=IRRELEVANT_GLOBAL_SETTINGS,
        )
        self.assertTrue(worker.validate_params())

    def test_cortex_run_a_new_job_does_not_require_them(self):
        worker = _worker(
            cortex_run_a_new_job,
            "AlertActionWorkercortex_run_a_new_job",
            {"cortex_instance_id": "inst1", "data_field_name": "data",
             "datatype_field_name": "datatype", "analyzers": "all",
             "tlp": "2", "pap": "2"},
            missing_settings=IRRELEVANT_GLOBAL_SETTINGS,
        )
        self.assertTrue(worker.validate_params())

    def test_create_a_new_alert_still_refuses_its_own_missing_parameter(self):
        """The fix must not turn `validate_params` into a rubber stamp."""
        worker = _worker(
            thehive_create_a_new_alert,
            "AlertActionWorkerthehive_create_a_new_alert",
            {"thehive_instance_id": None, "scope": "0", "severity": "2",
             "tlp": "2", "pap": "2"},
            missing_settings=IRRELEVANT_GLOBAL_SETTINGS,
        )
        self.assertFalse(worker.validate_params())
        worker.log_error.assert_called_once()


if __name__ == '__main__':
    unittest.main()
