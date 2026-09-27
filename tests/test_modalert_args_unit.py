"""Reading the alert action form -- and the two defaulting rules in it.

⚠️ These ~110 lines existed twice, and the pattern
`helper.get_param(x) if helper.get_param(x) else default` was written out about
twenty-five times per copy. Two rules hide inside that shape, and they are not
interchangeable:

* `if value`             -- an EMPTY string falls back to the default
* `if value is not None` -- an empty string is KEPT

Written by hand fifty times, nothing tells you which one a given field uses.
Named, it becomes visible -- and testable.
"""

import os
import sys
import time
import unittest

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(APP_ROOT, 'TA-thehive-cortex', 'package', 'bin')
for p in (BIN, os.path.join(BIN, 'ta_thehive_cortex')):
    if p not in sys.path:
        sys.path.insert(0, p)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _isolation import temporary_mocks  # noqa: E402

import modalert_args  # noqa: E402
from modalert_args import common_args, as_int, split_tags, event_timestamp, default_if_none, default_if_blank  # noqa: E402


class StubHelper:
    """A faithful stand-in: it answers only the names it was given, so a typo
    in a parameter name shows up as KeyError instead of a MagicMock."""

    def __init__(self, params=None, globals_=None):
        self.params = params or {}
        self.globals_ = globals_ or {}
        self.calls = []

    def get_param(self, name_):
        self.calls.append(name_)
        return self.params.get(name_)

    def get_global_setting(self, name_):
        return self.globals_.get(name_)


class RecordingLogger:
    def __init__(self):
        self.rows = []

    def debug(self, id="?", message=""):
        self.rows.append((id, message))


FORM = {
    "unique_id_field": "src", "case_template": "tmpl", "source": "es",
    "timestamp_field": "", "title": "Un titre", "description": "Une description",
    "tags": "a,b,a", "scope": "0", "severity": "3", "tlp": "1", "pap": "0",
    "description_results_enable": "1", "description_results_keep_observable": "0",
    "attach_results": "2", "attach_format": "1",
}


class TheTwoDefaultingRules(unittest.TestCase):

    def test_if_blank_replaces_the_empty_string(self):
        self.assertEqual(default_if_blank("", "defaut"), "defaut")
        self.assertEqual(default_if_blank(None, "defaut"), "defaut")
        self.assertEqual(default_if_blank("value", "defaut"), "value")

    def test_if_absent_KEEPS_the_empty_string(self):
        # ⚠️ The whole difference. A global setting deliberately left empty is
        # a value, not an absence.
        self.assertEqual(default_if_none("", "defaut"), "")
        self.assertEqual(default_if_none(None, "defaut"), "defaut")

    def test_integer_only_converts_what_exists(self):
        self.assertEqual(as_int("3", 2), 3)
        self.assertEqual(as_int(None, 2), 2)
        # ⚠️ "0" is falsy as a string but is NOT absent: it must survive.
        self.assertEqual(as_int("0", 2), 0)


class Tags(unittest.TestCase):

    def test_duplicates_go_and_the_order_stays(self):
        self.assertEqual(split_tags("b,a,b,c"), ["b", "a", "c"])

    def test_an_empty_value_gives_an_empty_list(self):
        self.assertEqual(split_tags(""), [])
        self.assertEqual(split_tags(None), [])


class EventTimestamp(unittest.TestCase):

    def test_without_a_field_it_is_now_in_milliseconds(self):
        before = int(time.time() * 1000)
        value = event_timestamp("")
        self.assertGreaterEqual(value, before)

    def test_a_ten_digit_epoch_becomes_milliseconds(self):
        self.assertEqual(event_timestamp("1700000000"), 1700000000000)

    def test_everything_else_comes_out_UNCHANGED(self):
        # ⚠️ Preserved on purpose, rough edge included: a date like
        # "2026-01-01" comes back as a string and blows up in whoever converts
        # it. Fixing that belongs to the parse_events work; this module must
        # not change behaviour while it removes duplication.
        self.assertEqual(event_timestamp("2026-01-01"), "2026-01-01")
        self.assertEqual(event_timestamp("1700000000000"), "1700000000000")


class TheFullAssembly(unittest.TestCase):

    def setUp(self):
        self.recorder = RecordingLogger()

    def build(self, **replacements):
        params = dict(FORM)
        params.update(replacements)
        self.helper = StubHelper(params, {})
        return common_args(self.helper, self.recorder)

    def test_the_form_fields(self):
        args = self.build()
        self.assertEqual(args["unique_id_field"], "src")
        self.assertEqual(args["caseTemplate"], "tmpl")
        self.assertEqual(args["source"], "es")
        self.assertEqual(args["title"], "Un titre")
        self.assertEqual(args["tags"], ["a", "b"])
        self.assertEqual(args["severity"], 3)
        self.assertEqual(args["tlp"], 1)
        self.assertEqual(args["pap"], 0)
        self.assertEqual(args["attach_results"], 2)
        self.assertEqual(args["attach_format"], 1)

    def test_the_defaults_when_the_form_is_empty(self):
        args = self.build(unique_id_field="", case_template="", source="",
                               title="", description="", tags="",
                               severity=None, tlp=None, pap=None)
        self.assertEqual(args["unique_id_field"], "oneEvent")
        self.assertIsNone(args["caseTemplate"])
        self.assertEqual(args["source"], "splunk")
        self.assertIsNone(args["title"])
        self.assertEqual(args["description"], "No description provided")
        self.assertEqual(args["tags"], [])
        self.assertEqual((args["severity"], args["tlp"], args["pap"]), (2, 2, 2))

    def test_scope_is_TRUE_when_the_field_is_zero(self):
        # Inverted on purpose in the form, and easy to get backwards.
        self.assertTrue(self.build(scope="0")["scope"])
        self.assertFalse(self.build(scope="1")["scope"])

    def test_backslashes_are_converted_when_enabled(self):
        args = self.build(description="ligne1\\nligne2")
        self.assertEqual(args["description"], "ligne1\nligne2")

    def test_they_are_not_when_it_is_disabled(self):
        self.helper = StubHelper(
            dict(FORM, description="ligne1\\nligne2"),
            {"splunk_sanitize_backslashes": "DISABLED"})
        args = common_args(self.helper, self.recorder)
        self.assertEqual(args["description"], "ligne1\\nligne2")

    def test_global_settings_have_their_defaults(self):
        args = self.build()
        self.assertEqual(args["splunk_sanitize_backslashes"], "ENABLED")
        self.assertEqual(args["splunk_es_alerts_index"], "summary")

    def test_the_two_boolean_flags(self):
        args = self.build(description_results_enable="1",
                               description_results_keep_observable="1")
        self.assertTrue(args["description_results_enable"])
        self.assertTrue(args["description_results_keep_observable"])

    def test_the_scope_is_traced(self):
        self.build()
        self.assertEqual([id for id, _ in self.recorder.rows], ["50"])

    def test_each_parameter_is_read_ONCE(self):
        # ⚠️ The duplicated pattern called get_param TWICE per field, about
        # twenty-five times over. Not a correctness bug -- a cost nobody chose.
        self.build()
        duplicates = {n for n in self.helper.calls
                   if self.helper.calls.count(n) > 1}
        self.assertEqual(duplicates, {"scope"},
                         "only `scope` is read twice, for its own debug line")


class BothCallersShareTheAssembly(unittest.TestCase):

    def test_no_helper_rebuilds_the_common_arguments(self):
        for name_ in ("modalert_thehive_create_a_new_case_helper.py",
                    "modalert_thehive_create_a_new_alert_helper.py"):
            with open(os.path.join(BIN, "ta_thehive_cortex", name_),
                      encoding="utf-8") as f:
                source = f.read()
            with self.subTest(helper=name_):
                self.assertIn("common_args(helper, logger_file)", source)
                self.assertNotIn('alert_args["severity"]', source)
                self.assertNotIn('alert_args["tlp"]', source)


class InstanceBootstrap(unittest.TestCase):
    """⚠️ The function that 123 green tests never executed.

    `prepare_instances` carried `from modalert_thehive_common import
    create_thehive_instance` -- the function lives in `thehive`. That is an
    ImportError on the first useful line of BOTH creation actions, and the
    suite could not see it: no test ever entered this function.

    A test proves the paths it WALKS. This one walks the import.
    """

    def test_the_function_really_runs(self):
        from unittest.mock import MagicMock

        helper = StubHelper({"thehive_instance_id": "local,distant"})
        helper.log_info = lambda m: None
        helper.log_debug = lambda m: None
        helper.set_log_level = lambda n: None
        helper.log_level = "INFO"
        helper.settings = {"sessionKey": "(SANITIZED)"}
        helper._logger = MagicMock()
        helper.exec_id = "abcd1234"

        fake_globals = MagicMock()
        built = []

        def fake_factory(instance_id, settings, logger, acronym, exec_id):
            built.append((instance_id, acronym))
            return ("thehive", "conf", "defaults", "logger", instance_id)

        # ⚠️ Replace the two modules the function imports LAZILY, so the
        # import really happens -- the import is what is under test.
        fake_thehive = MagicMock()
        fake_thehive.create_thehive_instance = fake_factory
        with temporary_mocks(["globals", "thehive"],
                               {"globals": fake_globals, "thehive": fake_thehive}):
            instances = modalert_args.prepare_instances(helper, acronym="THCC")

        self.assertEqual(len(instances), 2)
        self.assertEqual(built, [("local", "THCC"), ("distant", "THCC")])
        fake_globals.initialize_globals.assert_called_once()

    def test_the_acronym_is_woven_into_both_prefixes(self):
        from unittest.mock import MagicMock

        traces = []
        helper = StubHelper({"thehive_instance_id": "local"})
        helper.log_info = lambda m: traces.append(m)
        helper.log_debug = lambda m: traces.append(m)
        helper.set_log_level = lambda n: None
        helper.log_level = "DEBUG"
        helper.settings = {}
        helper._logger = MagicMock()
        helper.exec_id = "z"

        fake_thehive = MagicMock()
        fake_thehive.create_thehive_instance = lambda **k: ("t", "c", "d", "l", "i")
        with temporary_mocks(["globals", "thehive"],
                               {"globals": MagicMock(), "thehive": fake_thehive}):
            modalert_args.prepare_instances(helper, acronym="THCA")

        self.assertTrue(any("[CAA-THCA-35]" in m for m in traces))
        self.assertTrue(any("[CAA-THCA-40]" in m for m in traces))


if __name__ == "__main__":
    unittest.main()
