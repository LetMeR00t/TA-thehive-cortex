"""Checking a MITRE patternId against the catalogue TheHive actually holds.

⚠️ Two halves of the same hole, each hiding the other: the setting
`thehive_ttp_catalog_name` was exposed, read, handed over — and consumed by
nobody, so changing it did nothing. Meanwhile a TTP's `patternId` was validated
by `startswith("T")`, which accepts `T`, `TOTO` and `T99999` alike. The setting
that did nothing existed precisely for the check that was missing.
"""

import os
import sys
import unittest

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(APP_ROOT, 'TA-thehive-cortex', 'package', 'bin')
for p in (BIN, os.path.join(BIN, 'ta_thehive_cortex')):
    if p not in sys.path:
        sys.path.insert(0, p)

import ttp_catalogue  # noqa: E402
from ttp_catalogue import is_known, pattern_ids  # noqa: E402


class RecordingLogger:
    def __init__(self):
        self.lines = []

    def warn(self, id="?", message=""):
        self.lines.append(("warn", id, message))

    def debug(self, id="?", message=""):
        self.lines.append(("debug", id, message))

    def error(self, id="?", message=""):
        self.lines.append(("error", id, message))

    def ids(self, level=None):
        return [i for lvl, i, _ in self.lines if level is None or lvl == level]


class FakeProcedureEndpoint:
    def __init__(self, patterns=None, raises=None):
        self.patterns = patterns or []
        self.raises = raises
        self.calls = 0

    def get_catalog(self, catalog_id):
        self.calls += 1
        if self.raises:
            raise self.raises
        return self.patterns


class FakeTheHive:
    def __init__(self, endpoint):
        self.procedure = endpoint


CATALOGUE = [
    {"patternId": "T1566"}, {"patternId": "T1059"}, {"patternId": "T1055"},
]


class Base(unittest.TestCase):
    def setUp(self):
        ttp_catalogue.reset_cache()
        self.log = RecordingLogger()


class LoadingTheCatalogue(Base):

    def test_the_ids_are_extracted(self):
        thehive = FakeTheHive(FakeProcedureEndpoint(CATALOGUE))
        self.assertEqual(pattern_ids(thehive, "enterprise", self.log),
                         {"T1566", "T1059", "T1055"})

    def test_read_once_per_execution_not_once_per_row(self):
        # ⚠️ The catalogue does not change while a batch is being sent, and
        # re-reading it per row would be one HTTP round-trip per row.
        endpoint = FakeProcedureEndpoint(CATALOGUE)
        thehive = FakeTheHive(endpoint)
        for _ in range(50):
            pattern_ids(thehive, "enterprise", self.log)
        self.assertEqual(endpoint.calls, 1)

    def test_no_catalogue_configured_means_no_check(self):
        endpoint = FakeProcedureEndpoint(CATALOGUE)
        self.assertIsNone(pattern_ids(FakeTheHive(endpoint), "", self.log))
        self.assertIsNone(pattern_ids(FakeTheHive(endpoint), None, self.log))
        self.assertEqual(endpoint.calls, 0, "no setting, no round-trip")

    def test_an_unreadable_catalogue_is_named_and_does_not_raise(self):
        thehive = FakeTheHive(FakeProcedureEndpoint(raises=RuntimeError("403")))
        self.assertIsNone(pattern_ids(thehive, "enterprise", self.log))
        self.assertEqual(self.log.ids("warn"), ["THC-120"])

    def test_a_malformed_entry_does_not_break_the_set(self):
        thehive = FakeTheHive(FakeProcedureEndpoint(
            [{"patternId": "T1566"}, {}, "pas un dictionnaire", {"patternId": None}]))
        self.assertEqual(pattern_ids(thehive, "enterprise", self.log), {"T1566"})


class DecidingOnOneId(Base):

    def test_a_known_id_passes(self):
        self.assertTrue(is_known("T1566", {"T1566", "T1059"}))

    def test_an_unknown_id_is_refused(self):
        self.assertFalse(is_known("T9999", {"T1566", "T1059"}))

    def test_shape_alone_is_no_longer_enough(self):
        # ⚠️ The whole point: these all satisfied `startswith("T")`.
        for invente in ("T", "TOTO", "T99999", "T1566x"):
            with self.subTest(id=invente):
                self.assertFalse(is_known(invente, {"T1566"}))

    def test_when_we_could_not_check_we_let_it_through(self):
        # ⚠️ None means "I could not verify", NOT "the catalogue is empty".
        # Blocking here would let an outage of ours silently drop legitimate
        # TTPs — punishing the user for our own failure.
        self.assertTrue(is_known("T9999", None))

    def test_an_empty_catalogue_refuses_everything(self):
        # And that is the other side of the same distinction: an empty set is
        # an answer, not an absence of answer.
        self.assertFalse(is_known("T1566", set()))


class TheSettingIsActuallyCarried(unittest.TestCase):
    """The half that made the other invisible."""

    def test_the_instance_carries_the_catalogue_name(self):
        chemin = os.path.join(BIN, "thehive.py")
        with open(chemin, encoding="utf-8") as f:
            source = f.read()
        self.assertIn('thehive.ttp_catalog_name = defaults["TTP_CATALOG_NAME"]', source)

    def test_parse_events_reads_it(self):
        chemin = os.path.join(BIN, "ta_thehive_cortex", "modalert_thehive_common.py")
        with open(chemin, encoding="utf-8") as f:
            source = f.read()
        self.assertIn("ttp_catalog_name", source)
        self.assertIn("is_known(", source)


if __name__ == "__main__":
    unittest.main()
