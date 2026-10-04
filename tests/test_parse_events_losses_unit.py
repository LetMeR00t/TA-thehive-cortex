"""No key may cross parse_events without leaving a trace.

This is the worst defect in the repository, and its defining feature is that it
is INVISIBLE. The alert reaches TheHive, it looks right, and a field is missing.
Nobody reports what they cannot see -- GitHub #133 cost a day of troubleshooting
for exactly one type (`url`), and the comment left in the code at the time
admits the next unknown type will fall in the same hole.

Four proven paths delete a value from the Splunk row BEFORE knowing how to
handle it, then add nothing and log nothing:

  R07  unknown custom field type: `del row_sanitized[key]` runs BEFORE the type
       is inspected, so the value leaves the raw table too -- a double loss
  R08  composite `foo:bar` whose prefix is not a datatype: deleted, then no
       `else` at all, not even a warning. The sneakiest of the four
  R09  an ordinary key while `scope` is truthy matches none of the five
       branches, and there is no terminal branch
  R10  `integer` / `float` conversion failures: value lost AND key already gone
  R13  a `timestamp_field` that is neither epoch10 nor epoch13 leaves
       `alert["timestamp"]` undefined while a log statement reads it -- an
       uncaught KeyError that fails the WHOLE alert

These are characterization tests: they pin the behaviour we want so the
restructuring that follows has a net. That is their real purpose.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

mocks = [
    'splunklib', 'splunklib.client', 'solnlib', 'solnlib.log',
    'solnlib.modular_input', 'solnlib.utils', 'ta_thehive_cortex_declare',
    'certifi', 'common', 'ta_logging', 'requests', 'requests.adapters',
    'requests.auth', 'urllib3', 'splunk', 'splunk.Intersplunk', 'tomark', 'globals',
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
    import modalert_thehive_common
    import datatypes  # imported by modalert_thehive_common: same module object


def parse_row(row, custom_fields=None, data_type=None, **overrides):
    """Run parse_events on one row and hand back everything it produced.

    `description_results_enable` is ON by default: the raw table reinjected in
    the description is HALF the evidence. A value can be missing from
    customFields and still be visible to the analyst there -- or be gone from
    both, which is the double loss.
    """
    thehive = MagicMock()
    thehive.custom_field.list.return_value = custom_fields or []

    helper = MagicMock()
    helper.get_events.return_value = [dict(row)]

    alert_args = {
        "alert_mode": "regular_mode",
        "case_mode": "regular_mode",
        "description_results_enable": "1",
        "description_results_keep_observable": "0",
        "scope": "0",
    }
    alert_args.update(overrides)

    # ⚠️ Tomark renders the raw table reinjected into the description. Left as a
    # MagicMock it returns another mock, and `assertIn("42", description)` would
    # compare against a mock repr -- an assertion that can never mean anything.
    # A real, minimal renderer is what makes the check honest.
    class RealTable:
        @staticmethod
        def table(rows_):
            return "\n".join(
                " | ".join(f"{k}={v}" for k, v in row.items()) for row in rows_
            )

    with patch.object(datatypes, "get_datatype_dict",
                      return_value=data_type or {}),\
         patch.object(modalert_thehive_common, "Tomark", RealTable):
        parsed = modalert_thehive_common.parse_events(helper, thehive, alert_args)

    alert_ = next(iter(parsed.values()))
    warning_records = " ".join(
        str(a.kwargs.get("message", "")) for a in thehive.logger_file.warn.call_args_list
    )
    return alert_, warning_records


class TestNoKeyVanishesSilently(unittest.TestCase):

    def test_r07_an_untransmittable_field_keeps_its_value_visible(self):
        """⚠️ The DOUBLE loss, on the case that remains after R11.

        An unknown TYPE is now forwarded as text, so it no longer falls here.
        What still cannot be forwarded is a KNOWN type whose value does not fit
        it -- `date` expecting an epoch or an ISO string, given "hier". The
        field is legitimately absent from customFields; what would not be
        legitimate is the value disappearing from the raw table too, which is
        what the premature `del` used to do.
        """
        alert_, warning_records = parse_row(
            {"unique": "ref-1", "quand": "hier"},
            custom_fields=[{"name": "quand", "type": "date"}],
        )
        self.assertEqual(0, len(alert_["customFields"]),
                         "a value that does not fit its declared type cannot be sent")
        self.assertIn("quand", warning_records, "the drop must be named")
        self.assertIn("hier", alert_["description"],
                      "the VALUE must survive in the reinjected table: losing it from "
                      "both places is how the analyst loses it entirely")

    def test_r08_composite_key_without_datatype_does_not_vanish_silently(self):
        """The sneakiest: deleted at :507, then `if mainkey in data_type` with
        no `else` at all -- not even a warning."""
        alert_, warning_records = parse_row({"unique": "ref-1", "foo:bar": "valeur-utile"})
        self.assertTrue(
            "valeur-utile" in alert_["description"] or "foo:bar" in warning_records,
            "a composite key whose prefix is not a datatype vanished without a word",
        )

    def test_r09_a_plain_key_with_scope_does_not_fall_into_the_void(self):
        """`scope` truthy: none of the five branches match, and there is no
        terminal branch, so the key is simply never seen."""
        alert_, warning_records = parse_row(
            {"unique": "ref-1", "champ_libre": "contenu"}, scope="1"
        )
        self.assertTrue(
            "contenu" in alert_["description"] or "champ_libre" in warning_records,
            "an ordinary key fell through every branch unnoticed",
        )

    def test_invariant_every_value_sent_can_be_found(self):
        """The general form of every case above, and the real protection.

        Rather than pinning the five branches that exist today, this asserts the
        INVARIANT: whatever key a row carries, its value must be findable
        somewhere in what reaches TheHive -- an observable, a custom field, a
        TTP, or failing all of those, the raw table in the description. A new
        branch, or a branch removed, cannot silently open a hole under it.
        """
        keys_ = {
            "unique": "ref-1",
            "champ_inconnu": "valeur-A",
            "prefixe:sous_cle": "valeur-B",
            "UPPER_CASE": "valeur-C",
            "avec espace": "valeur-D",
            "accentué": "valeur-E",
        }
        alert_, warning_records = parse_row(keys_)
        returned = str(alert_.get("description", "")) + str(alert_.get("customFields", ""))\
            + str(alert_.get("title", "")) + warning_records
        for key_, value_ in keys_.items():
            if key_ == "unique":
                continue
            with self.subTest(key_=key_):
                self.assertIn(value_, returned,
                              f"the value of '{key_}' is reachable nowhere: neither in the "
                              f"alert, nor in the raw table, nor in a warning")

    def test_r11_an_unknown_type_is_sent_as_a_string(self):
        """A type this add-on does not know is not a reason to drop the field.

        The list of TheHive custom field types is not ours to freeze: TheHive
        adds types, and every one it adds used to vanish here. Sending the raw
        value as a string lets TheHive itself accept or refuse it -- which is
        the only authority on its own schema. `url` cost a day of
        troubleshooting for exactly this reason.
        """
        alert_, warning_records = parse_row(
            {"unique": "ref-1", "montant": "42"},
            custom_fields=[{"name": "montant", "type": "number"}],
        )
        self.assertEqual(1, len(alert_["customFields"]),
                         "an unknown type must be forwarded, not dropped")
        self.assertEqual("42", alert_["customFields"][0]["value"])
        self.assertIn("montant", warning_records, "forwarding as text must be said")

    def test_r11_an_iso_date_is_accepted(self):
        """ISO-8601 is what a Splunk `strftime` produces; only epochs were taken."""
        alert_, _ = parse_row(
            {"unique": "ref-1", "quand": "2026-01-15T10:30:00"},
            custom_fields=[{"name": "quand", "type": "date"}],
        )
        self.assertEqual(1, len(alert_["customFields"]))
        self.assertIsInstance(alert_["customFields"][0]["value"], int)

    def test_r10_invalid_integer_warns_and_keeps(self):
        alert_, warning_records = parse_row(
            {"unique": "ref-1", "compteur": "pas-un-nombre"},
            custom_fields=[{"name": "compteur", "type": "integer"}],
        )
        self.assertIn("compteur", warning_records)
        self.assertIn("pas-un-nombre", alert_["description"])

    def test_r10_invalid_float_warns_and_keeps(self):
        alert_, warning_records = parse_row(
            {"unique": "ref-1", "ratio": "n/a"},
            custom_fields=[{"name": "ratio", "type": "float"}],
        )
        self.assertIn("ratio", warning_records)
        self.assertIn("n/a", alert_["description"])

    # ⚠️ The setting is read as `timestamp`, NOT `timestamp_field`. Writing the
    # latter makes the code take the `else` branch, set a fallback, and the test
    # pass while proving nothing -- which is exactly what happened on the first
    # attempt here.

    def test_r13_a_non_numeric_timestamp_does_not_fail_the_whole_alert(self):
        """⚠️ Not a lost field -- a lost ALERT.

        `float(row.pop(arg_timestamp))` on "2026-01-01" raises ValueError,
        uncaught, so the whole alert fails. An ISO date in a timestamp column is
        not an exotic input: it is what a Splunk `strftime` produces.
        """
        alert_, warning_records = parse_row(
            {"unique": "ref-1", "quand": "2026-01-01"},
            timestamp="quand",
        )
        self.assertIn("timestamp", alert_, "a fallback timestamp must always exist")
        self.assertIn("quand", warning_records, "the fallback must be said")

    def test_r13_an_off_format_numeric_timestamp_does_not_raise(self):
        """The second shape: numeric, but neither ten nor thirteen digits.

        Both branches are skipped, `alert["timestamp"]` is never assigned, and
        the very next line logs it -- KeyError on a key the code just failed to
        write.
        """
        alert_, warning_records = parse_row(
            {"unique": "ref-1", "quand": "12345"},
            timestamp="quand",
        )
        self.assertIn("timestamp", alert_)
        self.assertIsInstance(alert_["timestamp"], int)


if __name__ == '__main__':
    unittest.main()
