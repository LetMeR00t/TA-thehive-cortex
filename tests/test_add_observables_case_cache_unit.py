"""Gitea #32: resolving a case number costs one TheHive search -- once.

`thehive_add_observables` used to call `thehive.resolve_case_id(tid)` once
per target ID *per row*, with no memoisation: the same case number repeated
across N rows cost N identical searches. `_resolve_case_ids` is the small,
pure function this was extracted into so the caching itself is testable
without a live TheHive and without exercising the whole `process_event` loop
(gzip results file, Splunk helper, six other parameters).
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
from _isolation import temporary_mocks  # noqa: E402

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(APP_ROOT, 'TA-thehive-cortex', 'package', 'bin')
for p in (BIN,
          os.path.join(BIN, 'ta_thehive_cortex'),
          os.path.join(BIN, 'ta_thehive_cortex', 'libs')):
    if p not in sys.path:
        sys.path.insert(0, p)

with temporary_mocks(mocks):
    import modalert_thehive_add_observables_helper as helper_module  # noqa: E402


class TestResolveCaseIdsCaching(unittest.TestCase):

    def setUp(self):
        self.thehive = MagicMock()
        self.thehive.resolve_case_id.side_effect = lambda n: f"~{n}00"
        self.cache = {}

    def test_the_same_number_is_resolved_once(self):
        first = helper_module._resolve_case_ids(self.thehive, ["42", "42"], self.cache)
        second = helper_module._resolve_case_ids(self.thehive, ["42"], self.cache)

        self.thehive.resolve_case_id.assert_called_once_with("42")
        self.assertEqual(["~4200", "~4200"], first)
        self.assertEqual(["~4200"], second)

    def test_different_numbers_are_each_resolved_once(self):
        helper_module._resolve_case_ids(self.thehive, ["1", "2", "1", "2"], self.cache)

        self.assertEqual(2, self.thehive.resolve_case_id.call_count)
        self.thehive.resolve_case_id.assert_any_call("1")
        self.thehive.resolve_case_id.assert_any_call("2")

    def test_the_cache_is_scoped_to_the_dict_passed_in(self):
        """Not a module global: two executions must not see each other's ids."""
        other_cache = {}
        helper_module._resolve_case_ids(self.thehive, ["9"], self.cache)
        helper_module._resolve_case_ids(self.thehive, ["9"], other_cache)

        self.assertEqual(2, self.thehive.resolve_case_id.call_count)


if __name__ == '__main__':
    unittest.main()
