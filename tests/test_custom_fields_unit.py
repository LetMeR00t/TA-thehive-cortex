import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Mock EVERYTHING that is not available locally
mocks = [
    'splunklib', 'splunklib.client', 'solnlib', 'solnlib.log',
    'solnlib.modular_input', 'solnlib.utils', 'ta_thehive_cortex_declare',
    'certifi', 'common', 'ta_logging', 'requests', 'requests.adapters',
    'requests.auth', 'urllib3', 'tomark',
]


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _isolation import temporary_mocks  # noqa: E402

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(APP_ROOT, 'TA-thehive-cortex', 'package', 'bin'))
sys.path.insert(0, os.path.join(APP_ROOT, 'TA-thehive-cortex', 'package', 'bin', 'ta_thehive_cortex'))
sys.path.insert(0, os.path.join(APP_ROOT, 'TA-thehive-cortex', 'package', 'bin', 'ta_thehive_cortex', 'libs'))

with temporary_mocks(mocks):
    import modalert_thehive_common


class TestCustomFieldTypes(unittest.TestCase):
    """A custom field whose type is absent from the type chain in parse_events
    is dropped WITHOUT an error -- the alert is still created, minus the field.
    "url" (TheHive >= 5.1) was such a type (GitHub issue #133).
    """

    #: The types this add-on knows how to CONVERT, with a valid value for each.
    #: ⚠️ It is NOT "the types TheHive supports" -- that list belongs to TheHive
    #: and it grows. Keeping a copy of it here would make this table a mirror of
    #: production rather than a guard: it would stay green on the very day a new
    #: type appeared. What guards that case is
    #: test_unknown_type_is_forwarded_as_text_and_logged, which uses an invented
    #: type on purpose.
    ALL_TYPES = {
        "string": ("a string", "a string"),
        "url": ("https://example.org/path", "https://example.org/path"),
        "boolean": ("true", True),
        "integer": ("42", 42),
        "float": ("4.2", 4.2),
        "date": ("1700000000", 1700000000 * 1000),
    }

    def _parse(self, field_name, field_type, value):
        """Run parse_events on a single row carrying one custom field."""
        thehive = MagicMock()
        thehive.custom_field.list.return_value = [
            {"name": field_name, "type": field_type}
        ]

        helper = MagicMock()
        helper.get_events.return_value = [{"unique": "ref-1", field_name: value}]

        alert_args = {
            "alert_mode": "regular_mode",
            "case_mode": "regular_mode",
            "description_results_enable": "0",
            "description_results_keep_observable": "0",
            "scope": "0",
        }

        with patch.object(modalert_thehive_common, "get_datatype_dict", return_value={}):
            parsed = modalert_thehive_common.parse_events(helper, thehive, alert_args)

        self.assertEqual(len(parsed), 1, "exactly one alert should be produced")
        alert = next(iter(parsed.values()))
        return alert["customFields"]

    def test_url_custom_field_is_not_dropped(self):
        """The regression itself: a url-typed field used to vanish silently."""
        fields = self._parse("evidence_link", "url", "https://example.org/path")
        self.assertEqual(len(fields), 1, "the url custom field was dropped")
        self.assertEqual(fields[0]["value"], "https://example.org/path")

    def test_every_thehive_type_survives(self):
        """Guards the whole chain, not just the type that was reported."""
        for field_type, (raw, expected) in self.ALL_TYPES.items():
            with self.subTest(type=field_type):
                fields = self._parse("cf_" + field_type, field_type, raw)
                self.assertEqual(
                    len(fields), 1, f"custom field of type {field_type} was dropped"
                )
                self.assertEqual(fields[0]["value"], expected)

    def test_unknown_type_is_forwarded_as_text_and_logged(self):
        """⚠️ Contract CHANGED: an unknown type is forwarded, not dropped.

        Dropping was the old behaviour, and it is what made #133 cost a day of
        troubleshooting. The list of custom field types belongs to TheHive, not
        to this add-on: TheHive adds types, and every one it added vanished
        here. Sending the raw value as text lets TheHive -- the only authority
        on its own schema -- accept or refuse it.

        The type used below is INVENTED on purpose. A test that draws its types
        from the same table as production is a copy of production, not a guard:
        it stays green precisely on the day TheHive introduces something new,
        which is the only day it would have mattered.
        """
        thehive = MagicMock()
        thehive.custom_field.list.return_value = [{"name": "weird", "type": "quantum"}]
        helper = MagicMock()
        helper.get_events.return_value = [{"unique": "ref-1", "weird": "whatever"}]
        alert_args = {
            "alert_mode": "regular_mode",
            "case_mode": "regular_mode",
            "description_results_enable": "0",
            "description_results_keep_observable": "0",
            "scope": "0",
        }

        with patch.object(modalert_thehive_common, "get_datatype_dict", return_value={}):
            parsed = modalert_thehive_common.parse_events(helper, thehive, alert_args)

        alert = next(iter(parsed.values()))
        self.assertEqual(len(alert["customFields"]), 1,
                         "an unknown type must reach TheHive, not vanish here")
        self.assertEqual(alert["customFields"][0]["value"], "whatever")
        thehive.logger_file.warn.assert_called()
        message = thehive.logger_file.warn.call_args.kwargs["message"]
        self.assertIn("weird", message)
        self.assertIn("quantum", message)


if __name__ == "__main__":
    unittest.main()
