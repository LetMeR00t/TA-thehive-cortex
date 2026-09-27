"""#37 -- the alerts & cases collection must bring an alert's TTPs back.

Two hops can drop the option, and each one is pinned here:

1. `collection_options.options_for` -- the per-type filter both inputs apply
   to what the form saved. It used to keep only `observables,attachments` for
   an alert, so `ttps` was accepted by the form and dropped at every run.
2. `TheHive4Splunk.get_alerts_events` -- accepting the option is worthless if
   the retrieval never asks TheHive for the procedures. It had no `ttps`
   branch at all, only the cases getter had one.
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

MOCKS = [
    "splunklib", "splunklib.client", "solnlib", "solnlib.log",
    "solnlib.modular_input", "solnlib.utils", "ta_thehive_cortex_declare",
    "certifi", "common", "ta_logging", "requests", "requests.adapters",
    "requests.auth", "urllib3",
]

with temporary_mocks(MOCKS):
    import thehive

import collection_options  # noqa: E402

GROUP_TYPES = {"Common": ("alerts", "cases"), "Alerts only": ("alerts",),
               "Cases only": ("cases",)}


def _form_extra_data():
    """{input type: extra_data options the alerts & cases form offers it}."""
    import json
    with open(os.path.join(APP_ROOT, "TA-thehive-cortex", "globalConfig.json"),
              encoding="utf-8") as fh:
        config = json.load(fh)
    offered = {"alerts": set(), "cases": set()}
    for service in config["pages"]["inputs"]["services"]:
        if service["name"] != "thehive_alerts_cases":
            continue
        for entity in service["entity"]:
            if entity.get("field") != "extra_data":
                continue
            for group in entity["options"]["groups"]:
                for input_type in GROUP_TYPES[group["label"]]:
                    offered[input_type].update(group["fields"])
    assert offered["alerts"] and offered["cases"], "form not found"
    return offered


class TestOptionsFor(unittest.TestCase):
    def test_alert_keeps_ttps(self):
        info, _ = collection_options.options_for(
            "alerts", ["observables", "ttps"], [])
        self.assertEqual(info, ["observables", "ttps"])

    def test_case_keeps_ttps(self):
        info, _ = collection_options.options_for("cases", ["ttps"], [])
        self.assertEqual(info, ["ttps"])

    def test_cases_only_options_are_not_asked_for_an_alert(self):
        info, _ = collection_options.options_for(
            "alerts", ["tasks", "pages", "attachments"], [])
        self.assertEqual(info, ["attachments"])

    def test_extra_data_offered_by_the_form_is_kept_for_its_type(self):
        # #37, user decision 2026-09-27: every extra_data option the form
        # offers is collected. Read from the form itself, so an option added
        # there and forgotten here turns this red.
        for input_type, offered in _form_extra_data().items():
            _, extra = collection_options.options_for(input_type, [], sorted(offered))
            self.assertEqual(
                sorted(extra), sorted(offered),
                f"{input_type}: offered by the form but dropped: "
                f"{sorted(set(offered) - set(extra))}")

    def test_extra_data_of_the_other_type_is_not_asked_for(self):
        _, extra = collection_options.options_for(
            "alerts", [], ["status", "caseNumber", "alerts", "taskStats"])
        self.assertEqual(extra, ["status", "caseNumber"])
        _, extra = collection_options.options_for(
            "cases", [], ["status", "caseNumber", "alerts", "importDate"])
        self.assertEqual(extra, ["status", "alerts"])

    def test_unknown_type_keeps_nothing(self):
        self.assertEqual(
            collection_options.options_for("tasks", ["ttps"], ["status"]),
            ([], []))


class TestAlertEventsCarryTtps(unittest.TestCase):
    def setUp(self):
        with patch.object(thehive.TheHive4Splunk, "__init__", return_value=None):
            self.hive = thehive.TheHive4Splunk()
        self.hive._logger_file = MagicMock()
        self.hive._utils = MagicMock()
        self.hive.alert = MagicMock()
        self.hive.alert.count.return_value = 1
        self.hive.alert.find.return_value = [
            {"_id": "~41", "_createdAt": 1000, "title": "t"}]
        self.hive.alert.find_procedures.return_value = [
            {"patternId": "T1027.003", "tactic": "defense-evasion"}]

    def _collect(self, additional_information):
        return self.hive.get_alerts_events(
            date="_createdAt", additional_information=additional_information,
            extra_data=[], fields_removal=None, max_size_value=None)

    def test_ttps_requested_are_fetched_and_indexed(self):
        events = self._collect(["ttps"])
        self.hive.alert.find_procedures.assert_called_once()
        self.assertEqual(
            self.hive.alert.find_procedures.call_args.args[0], "~41")
        self.assertEqual(events[0]["ttps"][0]["patternId"], "T1027.003")

    def test_ttps_not_requested_are_not_fetched(self):
        events = self._collect(["observables"])
        self.hive.alert.find_procedures.assert_not_called()
        self.assertNotIn("ttps", events[0])


class TestExtraDataReachesTheQuery(unittest.TestCase):
    """Keeping an option is worthless if the query never asks TheHive for it."""

    def setUp(self):
        with patch.object(thehive.TheHive4Splunk, "__init__", return_value=None):
            self.hive = thehive.TheHive4Splunk()
        self.hive._logger_file = MagicMock()
        self.hive._utils = MagicMock()

    def _paginate_extra_data(self, getter, obj, row):
        obj.count.return_value = 1
        obj.find.return_value = [row]
        getter(date="_createdAt", additional_information=[],
               extra_data=["procedureCount", "status"],
               fields_removal=None, max_size_value=None)
        return obj.find.call_args.kwargs["paginate"]["extraData"]

    def test_alert_query_asks_for_the_extra_data(self):
        self.hive.alert = MagicMock()
        extra = self._paginate_extra_data(
            self.hive.get_alerts_events, self.hive.alert,
            {"_id": "~1", "_createdAt": 1000, "title": "t"})
        self.assertEqual(extra, ["procedureCount", "status"])

    def test_case_query_asks_for_the_extra_data(self):
        self.hive.case = MagicMock()
        extra = self._paginate_extra_data(
            self.hive.get_cases_events, self.hive.case,
            {"_id": "~2", "_createdAt": 1000, "startDate": 1000, "title": "t"})
        self.assertEqual(extra, ["procedureCount", "status"])


if __name__ == "__main__":
    unittest.main()
