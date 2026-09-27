"""What counts as a date, on both paths that read one.

⚠️ These cases come from a real end-to-end run, not from imagination: the UC2
of `docs/alert_actions_and_adaptive_responses.md` sets
`"ip:sighted_at" = relative_time(now(),"-6h")`, Splunk renders that as
`1788071433.000000`, and both readers rejected it -- the observable one
without a word. The observable arrived `sighted` with no sighting date, and
nothing anywhere said so.
"""

import os
import sys
import unittest

sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "TA-thehive-cortex",
        "package",
        "bin",
        "ta_thehive_cortex",
    ),
)

import value_codecs  # noqa: E402


class TestEpochMillis(unittest.TestCase):

    def test_whole_seconds(self):
        self.assertEqual(1788093033000, value_codecs.epoch_millis("1788093033"))

    def test_whole_milliseconds(self):
        self.assertEqual(1788093033123, value_codecs.epoch_millis("1788093033123"))

    def test_fractional_seconds(self):
        """The shape Splunk actually emits, and the one that was rejected."""
        self.assertEqual(1788071433000, value_codecs.epoch_millis("1788071433.000000"))

    def test_fractional_milliseconds(self):
        self.assertEqual(1788071433123, value_codecs.epoch_millis("1788071433123.4"))

    def test_what_is_not_a_date(self):
        for value_ in ("", "hier", "12345", None, "1788071433.000000.1"):
            self.assertIsNone(value_codecs.epoch_millis(value_), repr(value_))

    def test_the_old_name_is_still_available(self):
        self.assertEqual(
            value_codecs.epoch_millis("1788071433.5"),
            value_codecs.str_to_epoch_millis("1788071433.5"),
        )


class TestDateCodec(unittest.TestCase):
    """The custom field path must agree with the observable one.

    Two date readers that disagree about what a date looks like is how the
    same value lands in a custom field and vanishes from an observable of the
    same event.
    """

    def _codec(self, value_):
        return value_codecs.CUSTOM_FIELD_CODECS["date"](value_)

    def test_accepts_what_the_other_reader_accepts(self):
        for value_ in ("1788093033", "1788093033123", "1788071433.000000"):
            mapped, millis = self._codec(value_)
            self.assertTrue(mapped, value_)
            self.assertEqual(value_codecs.epoch_millis(value_), millis, value_)

    def test_iso_8601_is_still_accepted(self):
        mapped, millis = self._codec("2026-08-30T12:00:00+00:00")
        self.assertTrue(mapped)
        self.assertEqual(1788091200000, millis)

    def test_refuses_what_is_not_a_date(self):
        mapped, millis = self._codec("pas une date")
        self.assertFalse(mapped)
        self.assertIsNone(millis)


if __name__ == "__main__":
    unittest.main()
