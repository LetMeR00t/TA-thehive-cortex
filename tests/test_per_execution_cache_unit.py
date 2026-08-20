"""What must be read once per execution, and was read once per row.

⚠️ `parse_events` re-read two invariants on every call: the custom field
definitions (an HTTP round-trip to TheHive) and the datatypes lookup (a full
CSV re-read, plus a rewrite attempt under `$SPLUNK_HOME/etc/apps` when the file
is over 24 hours old).

That is harmless for the creation actions, which call `parse_events` once. It
is not harmless for "add observables", which calls it **once per row**: for
1000 rows, ~1000 identical HTTP calls and ~1000 CSV re-reads.

The cost is invisible in a unit test that runs one row, and invisible in a
reading — you have to count the calls.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock

mocks = [
    'splunklib', 'splunklib.client', 'solnlib', 'solnlib.log',
    'solnlib.modular_input', 'solnlib.utils', 'ta_thehive_cortex_declare',
    'splunk', 'splunk.Intersplunk', 'splunk.rest', 'globals', 'certifi',
    'requests', 'requests.adapters', 'requests.auth', 'requests.exceptions',
    'urllib3', 'urllib3.util', 'urllib3.util.retry', 'tomark',
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
    import modalert_thehive_common as commun


class Session:
    def __init__(self, url):
        self.hive_url = url


class CountingCustomFields:
    def __init__(self):
        self.calls = 0

    def list(self):
        self.calls += 1
        return [{"name": "impact", "type": "string"}]


class FakeTheHive:
    def __init__(self, url="https://thehive.invalid"):
        self.session = Session(url)
        self.custom_field = CountingCustomFields()
        self.logger_file = MagicMock()


class ReadOncePerExecution(unittest.TestCase):

    def setUp(self):
        commun.reset_per_execution_cache()
        self.datatype_calls = 0
        self._vrai = commun.get_datatype_dict

        def compter(thehive):
            self.datatype_calls += 1
            return {"ip": "ip"}

        commun.get_datatype_dict = compter

    def tearDown(self):
        commun.get_datatype_dict = self._vrai
        commun.reset_per_execution_cache()

    def test_a_thousand_rows_cost_one_read(self):
        thehive = FakeTheHive()
        for _ in range(1000):
            commun.per_execution_invariants(thehive)
        self.assertEqual(thehive.custom_field.calls, 1)
        self.assertEqual(self.datatype_calls, 1)

    def test_the_values_are_the_same_every_time(self):
        # ⚠️ A cache returning something else on the second call would be worse
        # than no cache: the defect would only appear from the second row on.
        thehive = FakeTheHive()
        premier = commun.per_execution_invariants(thehive)
        for _ in range(10):
            self.assertEqual(commun.per_execution_invariants(thehive), premier)

    def test_two_instances_do_not_share_a_catalogue(self):
        # ⚠️ One search can address several TheHive instances in the same
        # execution, and they share neither custom fields nor datatypes.
        # Memoising without a key would mix them.
        une = FakeTheHive("https://un.invalid")
        deux = FakeTheHive("https://deux.invalid")
        commun.per_execution_invariants(une)
        commun.per_execution_invariants(deux)
        self.assertEqual(une.custom_field.calls, 1)
        self.assertEqual(deux.custom_field.calls, 1)
        self.assertEqual(self.datatype_calls, 2)

    def test_the_cache_can_be_forgotten(self):
        thehive = FakeTheHive()
        commun.per_execution_invariants(thehive)
        commun.reset_per_execution_cache()
        commun.per_execution_invariants(thehive)
        self.assertEqual(thehive.custom_field.calls, 2)


class TheCallSiteUsesIt(unittest.TestCase):

    def test_parse_events_no_longer_reads_them_itself(self):
        chemin = os.path.join(BIN, "ta_thehive_cortex", "modalert_thehive_common.py")
        with open(chemin, encoding="utf-8") as f:
            source = f.read()
        corps = source[source.index("def parse_events"):]
        self.assertIn("per_execution_invariants(thehive)", corps)
        self.assertNotIn("thehive.custom_field.list()", corps)


if __name__ == "__main__":
    unittest.main()
