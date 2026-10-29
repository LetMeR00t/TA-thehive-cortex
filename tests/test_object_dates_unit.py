"""A collected object without a date must not cost the run.

⚠️ From production (TA 3.9.0, TheHive 5.6.7): 36 audit runs in four weeks died
on ``KeyError: '_createdAt'`` and 8 alert/case/observable runs on
``KeyError: '_updatedAt'``. Each lost the whole pull and its time window, which
no later run asks for again. 5.0.0 still indexed ``_createdAt`` directly in
every collector, so the same object still costs a 5.0.0 run its window.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _isolation import temporary_mocks  # noqa: E402

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(APP_ROOT, "TA-thehive-cortex", "package", "bin")
sys.path.insert(0, BIN)
sys.path.insert(0, os.path.join(BIN, "ta_thehive_cortex"))
sys.path.insert(0, os.path.join(BIN, "ta_thehive_cortex", "libs"))

import object_dates  # noqa: E402

MOCKS = [
    "splunklib", "splunklib.client", "solnlib", "solnlib.log",
    "solnlib.modular_input", "solnlib.utils", "ta_thehive_cortex_declare",
    "certifi", "common", "ta_logging", "requests", "requests.adapters",
    "requests.auth", "urllib3",
]
with temporary_mocks(MOCKS):
    import thehive  # noqa: E402

T = 1793180000000  # epoch milliseconds, as TheHive sends them


class TestStamp(unittest.TestCase):

    def test_both_dates_present(self):
        e = {"_createdAt": T, "_updatedAt": T + 5000}
        self.assertEqual([], object_dates.stamp(e, "_updatedAt"))
        self.assertEqual((T / 1000, (T + 5000) / 1000, 1793180005), (e["_createdAt"], e["_updatedAt"], e["_time"]))

    def test_never_updated_object_in_an_updated_pull(self):
        """TheHive omits the key: the object is dated by its creation."""
        e = {"_createdAt": T}
        self.assertEqual(["_updatedAt"], object_dates.stamp(e, "_updatedAt"))
        self.assertEqual(1793180000, e["_time"])
        self.assertNotIn("_updatedAt", e)

    def test_empty_updated_at(self):
        """A present but null date is the same as an absent one (5.0.0 raised TypeError here)."""
        e = {"_createdAt": T, "_updatedAt": None}
        self.assertEqual(["_updatedAt"], object_dates.stamp(e, "_updatedAt"))
        self.assertEqual(1793180000, e["_time"])

    def test_no_created_at(self):
        """The production audit case: _time falls back, nothing is invented in the object."""
        e = {"_updatedAt": T + 2000}
        self.assertEqual(["_createdAt"], object_dates.stamp(e, "_createdAt"))
        self.assertEqual(1793180002, e["_time"])
        self.assertNotIn("_createdAt", e)

    def test_no_date_at_all(self):
        e = {}
        self.assertEqual(["_updatedAt", "_createdAt"], object_dates.stamp(e, "_updatedAt", now=1793190000.7))
        self.assertEqual(1793190000, e["_time"])

    def test_extra_dates_are_converted(self):
        e = {"_createdAt": T, "_startDate": T + 9000}
        self.assertEqual([], object_dates.stamp(e, "_startDate", ("_startDate",)))
        self.assertEqual(1793180009, e["_time"])

    def test_a_field_outside_the_converted_ones_is_used_as_left(self):
        """Cases convert startDate themselves before the generic block."""
        e = {"_createdAt": T, "startDate": 1793180003.0}
        self.assertEqual([], object_dates.stamp(e, "startDate"))
        self.assertEqual(1793180003, e["_time"])


class TestCollectorsKeepTheRun(unittest.TestCase):

    def setUp(self):
        with patch.object(thehive.TheHive4Splunk, "__init__", return_value=None):
            self.th = thehive.TheHive4Splunk()
        self.th.session = MagicMock()
        self.th._logger_file = MagicMock()
        self.th._utils = MagicMock()
        self.th._utils.remove_unwanted_keys_from_dict.side_effect = lambda d, l: d
        self.th._utils.check_and_reduce_values_size.side_effect = lambda d, max_size: d

    def _warnings(self):
        return [c.kwargs for c in self.th._logger_file.warn.call_args_list]

    def test_audit_entry_without_created_at(self):
        objs = [{"_id": "~1", "_type": "Audit", "_createdAt": T, "details": "secret-looking-value"},
                {"_id": "~2", "_type": "Audit", "details": "secret-looking-value"},
                {"_id": "~3", "_type": "Audit", "_createdAt": T + 1000}]
        self.th.organisation = MagicMock()
        self.th.organisation.count_audit_logs.return_value = len(objs)
        self.th.organisation.get_audit_logs.return_value = [dict(o) for o in objs]
        events = self.th.get_audit_logs_events(filters=None, max_size_value=1000, fields_removal="")
        self.assertEqual(3, len(events))
        warns = self._warnings()
        self.assertEqual(1, len(warns))
        self.assertEqual("TH127", warns[0]["id"])
        self.assertIn("_createdAt", warns[0]["message"])
        self.assertNotIn("secret-looking-value", warns[0]["message"])

    def test_tasks_accept_the_date_field_with_or_without_underscore(self):
        self.th.task = MagicMock()
        for date_field in ("updatedAt", "_updatedAt"):
            self.th.task.get_tasks.return_value = [{"_id": "~9", "_type": "Task", "_createdAt": T, "_updatedAt": T + 7000}]
            tasks = self.th.get_tasks_events(interval=300, date_field=date_field)
            self.assertEqual(1793180007, tasks[0]["time"], date_field)
        self.assertEqual([], self._warnings())


if __name__ == "__main__":
    unittest.main()
