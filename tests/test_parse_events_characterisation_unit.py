"""What `parse_events` does today — pinned, so a restructuring cannot change it.

⚠️ These tests are not here to say the behaviour is *good*. They say it is
**what it is**, line by line, so the dispatch table that replaces the 126-branch
chain can be proven identical rather than declared identical.

Read that literally: where the current code does something odd (a sub-key that
is stored and never read, a key kept where you would expect it dropped, a
malformed value that raises), the test pins the odd thing. Changing it is a
separate ticket, on purpose — a refactoring that smuggles in a fix cannot be
reviewed, because any difference could be either one.

⚠️ The `alert_args` values here are the REAL types produced by
`modalert_args.py`: `scope`, `description_results_enable` and
`description_results_keep_observable` are booleans, `severity`/`tlp`/`pap` are
ints. `scope` in particular is compared with `is False`, so passing the string
"0" silently skips the branch it was meant to exercise.
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
from _isolation import mocks_temporaires  # noqa: E402

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(APP_ROOT, 'TA-thehive-cortex', 'package', 'bin')
for p in (BIN,
          os.path.join(BIN, 'ta_thehive_cortex'),
          os.path.join(BIN, 'ta_thehive_cortex', 'libs')):
    if p not in sys.path:
        sys.path.insert(0, p)

with mocks_temporaires(mocks):
    import modalert_thehive_common
    import ttp_catalogue


class RealTable:
    """A real renderer. Left as a MagicMock, Tomark returns another mock and
    every assertion on the description compares against a mock repr."""

    @staticmethod
    def table(rows):
        return "\n".join(
            " | ".join(f"{k}={v}" for k, v in row.items()) for row in rows
        )


DEFAULT_ARGS = {
    "alert_mode": "regular_mode",
    "case_mode": "regular_mode",
    "unique_id_field": "unique",
    "title": None,
    "description": None,
    "timestamp": None,
    "severity": 2,
    "tlp": 2,
    "pap": 2,
    "scope": True,
    "description_results_enable": True,
    "description_results_keep_observable": False,
}


class Base(unittest.TestCase):

    def setUp(self):
        modalert_thehive_common.reset_per_execution_cache()
        ttp_catalogue.reset_cache()

    def run_rows(self, rows, custom_fields=None, data_type=None,
                 catalogue=None, sid="sid-1", search_name="my search",
                 **overrides):
        """Run parse_events over `rows` and return (parsed, log)."""
        if isinstance(rows, dict):
            rows = [rows]

        thehive = MagicMock()
        thehive.custom_field.list.return_value = custom_fields or []
        thehive.ttp_catalog_name = "mitre-attack" if catalogue is not None else None

        helper = MagicMock()
        helper.get_events.return_value = [dict(r) for r in rows]
        helper.sid = sid
        helper.settings = {"search_name": search_name}

        alert_args = dict(DEFAULT_ARGS)
        alert_args.update(overrides)

        with patch.object(modalert_thehive_common, "get_datatype_dict",
                          return_value=data_type or {}), \
             patch.object(modalert_thehive_common, "pattern_ids",
                          return_value=catalogue), \
             patch.object(modalert_thehive_common, "Tomark", RealTable):
            parsed = modalert_thehive_common.parse_events(helper, thehive, alert_args)

        log = {
            "warn": " ".join(str(c.kwargs.get("message", ""))
                             for c in thehive.logger_file.warn.call_args_list),
            "error": " ".join(str(c.kwargs.get("message", ""))
                              for c in thehive.logger_file.error.call_args_list),
            "helper_error": " ".join(str(c.args[0]) if c.args else ""
                                     for c in helper.error.call_args_list),
        }
        return parsed, log

    def one(self, rows, **kw):
        parsed, log = self.run_rows(rows, **kw)
        self.assertEqual(1, len(parsed), "expected exactly one alert")
        return next(iter(parsed.values())), log


class TestSourceRef(Base):

    def test_es_mode_without_unique_field_takes_event_id(self):
        parsed, _ = self.run_rows(
            {"event_id": "es-42", "a": "1"},
            alert_mode="es_mode", unique_id_field="absent",
        )
        self.assertEqual(["es-42"], list(parsed))

    def test_es_mode_without_event_id_falls_back_to_the_sid(self):
        parsed, _ = self.run_rows(
            {"a": "1"}, alert_mode="es_mode", unique_id_field="absent", sid="sid-9",
        )
        self.assertEqual(["sid-9"], list(parsed))

    def test_case_mode_es_follows_the_same_rule(self):
        parsed, _ = self.run_rows(
            {"event_id": "es-7"}, case_mode="es_mode", unique_id_field="absent",
        )
        self.assertEqual(["es-7"], list(parsed))

    def test_the_unique_field_is_consumed_from_the_raw_table(self):
        alert, _ = self.one({"unique": "ref-1", "other": "keep-me"})
        self.assertNotIn("unique", alert["events_keys"],
                         "the field carrying the identity is consumed")
        self.assertIn("other", alert["events_keys"])

    def test_an_empty_unique_field_falls_back_to_the_sid(self):
        parsed, _ = self.run_rows({"unique": "", "a": "1"}, sid="sid-3")
        self.assertTrue(list(parsed)[0].startswith("sid-3"))

    def test_an_over_long_source_ref_is_cut_to_127(self):
        parsed, _ = self.run_rows({"unique": "x" * 300})
        self.assertEqual(127, len(list(parsed)[0]))

    def test_two_rows_sharing_a_source_ref_are_merged(self):
        parsed, _ = self.run_rows([
            {"unique": "ref-1", "a": "1"},
            {"unique": "ref-1", "b": "2"},
        ])
        self.assertEqual(1, len(parsed))
        alert = next(iter(parsed.values()))
        self.assertEqual({"a", "b"}, set(alert["events_keys"]))


class TestTitleAndDescription(Base):

    def test_inheritance_takes_search_name_from_the_row(self):
        alert, _ = self.one({"unique": "r", "search_name": "ES notable"},
                            title="<inheritance>")
        self.assertEqual("ES notable", alert["title"])
        self.assertNotIn("search_name", alert["events_keys"])

    def test_inheritance_without_search_name_takes_the_saved_search_name(self):
        alert, _ = self.one({"unique": "r"}, title="<inheritance>",
                            search_name="saved search")
        self.assertEqual("saved search", alert["title"])

    def test_a_title_naming_a_field_is_extracted_and_consumed(self):
        alert, _ = self.one({"unique": "r", "subject": "session theft"}, title="subject")
        self.assertEqual("session theft", alert["title"])
        self.assertNotIn("subject", alert["events_keys"])

    def test_no_title_gives_the_default(self):
        alert, _ = self.one({"unique": "r"})
        self.assertEqual("Notable event", alert["title"])

    def test_description_taken_from_the_row(self):
        alert, _ = self.one({"unique": "r", "description": "from the row"})
        self.assertTrue(alert["description"].startswith("from the row"))
        self.assertNotIn("description", alert["events_keys"])

    def test_no_description_gives_the_default(self):
        alert, _ = self.one({"unique": "r"})
        self.assertTrue(alert["description"].startswith("No description provided"))

    def test_a_description_naming_a_field_is_extracted_and_consumed(self):
        alert, _ = self.one({"unique": "r", "summary": "what happened"},
                            description="summary")
        self.assertTrue(alert["description"].startswith("what happened"))
        self.assertNotIn("summary", alert["events_keys"])

    def test_a_literal_description_is_taken_as_is(self):
        """⚠️ `extract_field` returns the name itself when it names no field of
        the row, so the argument doubles as fixed text."""
        alert, _ = self.one({"unique": "r"}, description="fixed text")
        self.assertTrue(alert["description"].startswith("fixed text"))


class TestSeverityTlpPap(Base):

    def test_a_known_th_severity_is_consumed(self):
        alert, _ = self.one({"unique": "r", "th_severity": "high"})
        self.assertEqual(3, alert["severity"])
        self.assertNotIn("th_severity", alert["events_keys"])

    def test_th_severity_in_another_case_is_still_recognised(self):
        alert, _ = self.one({"unique": "r", "th_severity": "CRITICAL"})
        self.assertEqual(4, alert["severity"])

    def test_an_unknown_th_severity_falls_back_to_the_argument(self):
        alert, _ = self.one({"unique": "r", "th_severity": "enormous"}, severity=1)
        self.assertEqual(1, alert["severity"])
        self.assertIn("th_severity", alert["events_keys"],
                      "a value we could not read stays visible to the analyst")

    def test_th_tlp_and_th_pap_follow_the_same_shape(self):
        alert, _ = self.one({"unique": "r", "th_tlp": "red", "th_pap": "green"})
        self.assertEqual(4, alert["tlp"])
        self.assertEqual(1, alert["pap"])

    def test_an_exact_tlp_pap_code_matches_without_case_folding(self):
        alert, _ = self.one({"unique": "r", "th_tlp": "AMBER+STRICT", "th_pap": "W"})
        self.assertEqual(3, alert["tlp"])
        self.assertEqual(0, alert["pap"])

    def test_default_tlp_and_pap_come_from_the_arguments(self):
        alert, _ = self.one({"unique": "r"}, tlp=0, pap=3)
        self.assertEqual(0, alert["tlp"])
        self.assertEqual(3, alert["pap"])


class TestTimestamp(Base):

    def test_a_ten_digit_epoch_is_converted_to_milliseconds(self):
        alert, _ = self.one({"unique": "r", "when": "1700000000"}, timestamp="when")
        self.assertEqual(1700000000000, alert["timestamp"])

    def test_a_thirteen_digit_epoch_is_taken_as_is(self):
        alert, _ = self.one({"unique": "r", "when": "1700000000123"}, timestamp="when")
        self.assertEqual(1700000000123, alert["timestamp"])

    def test_a_non_numeric_value_warns_and_falls_back_to_now(self):
        alert, log = self.one({"unique": "r", "when": "2026-01-01"}, timestamp="when")
        self.assertIn("when", log["warn"])
        self.assertGreater(alert["timestamp"], 0)

    def test_an_unexpected_digit_count_warns(self):
        alert, log = self.one({"unique": "r", "when": "123456"}, timestamp="when")
        self.assertIn("neither a 10 nor a", log["warn"])
        self.assertGreater(alert["timestamp"], 0)

    def test_a_timestamp_field_missing_from_the_row_warns(self):
        alert, log = self.one({"unique": "r"}, timestamp="when")
        self.assertIn("missing", log["warn"])
        self.assertGreater(alert["timestamp"], 0)


class TestObservables(Base):

    def test_a_plain_key_of_a_known_datatype_becomes_an_observable(self):
        alert, _ = self.one({"unique": "r", "src_ip": "192.0.2.10"},
                            data_type={"src_ip": "ip"})
        self.assertEqual(1, len(alert["observables"]))
        self.assertEqual("ip", alert["observables"][0]["dataType"])
        self.assertEqual("192.0.2.10", alert["observables"][0]["data"])

    def test_an_observable_leaves_the_raw_table_unless_asked_to_stay(self):
        alert, _ = self.one({"unique": "r", "src_ip": "192.0.2.10"},
                            data_type={"src_ip": "ip"})
        self.assertNotIn("src_ip", alert["events_keys"])

        alert, _ = self.one({"unique": "r", "src_ip": "192.0.2.10"},
                            data_type={"src_ip": "ip"},
                            description_results_keep_observable=True)
        self.assertIn("src_ip", alert["events_keys"])

    def test_a_composite_key_enriches_the_observable(self):
        """⚠️ The sub-key that fills the observable's message is `description`,
        NOT `message`. Pinned as it is."""
        alert, _ = self.one(
            {"unique": "r", "src_ip": "192.0.2.10", "src_ip:description": "seen here"},
            data_type={"src_ip": "ip"},
        )
        self.assertEqual(1, len(alert["observables"]))
        self.assertEqual("seen here", alert["observables"][0]["message"])

    def test_a_sub_key_nobody_reads_breaks_nothing_and_does_nothing(self):
        """`src_ip:message` is accepted, stored, and never read back. Pinned so
        the dispatch table does not accidentally start honouring it — that would
        be a behaviour change dressed as a refactoring."""
        alert, _ = self.one(
            {"unique": "r", "src_ip": "192.0.2.10", "src_ip:message": "ignored"},
            data_type={"src_ip": "ip"},
        )
        self.assertEqual("No description provided for this observable",
                         alert["observables"][0]["message"])

    def test_a_composite_key_of_an_unknown_prefix_is_named_and_kept(self):
        alert, log = self.one({"unique": "r", "foo:bar": "useful value"})
        self.assertIn("foo:bar", log["warn"])
        self.assertIn("useful value", alert["description"])

    def test_a_multi_value_field_is_split_into_several_observables(self):
        alert, _ = self.one({"unique": "r", "src_ip": "192.0.2.10, 192.0.2.11"},
                            data_type={"src_ip": "ip"})
        self.assertEqual({"192.0.2.10", "192.0.2.11"},
                         {o["data"] for o in alert["observables"]})

    def test_the_field_name_becomes_a_tag(self):
        alert, _ = self.one({"unique": "r", "src_ip": "192.0.2.10"},
                            data_type={"src_ip": "ip"})
        self.assertIn("field:src_ip", alert["observables"][0]["tags"])

    def test_boolean_sub_fields_are_coerced_to_native_types(self):
        alert, _ = self.one(
            {"unique": "r", "src_ip": "192.0.2.10",
             "src_ip:is_ioc": "true", "src_ip:sighted": "false",
             "src_ip:ignore_similarity": "1"},
            data_type={"src_ip": "ip"},
        )
        obs = alert["observables"][0]
        self.assertIs(True, obs["ioc"])
        self.assertIs(False, obs["sighted"],
                      "sighted defaults to True, so this proves the override")
        self.assertIs(True, obs["ignoreSimilarity"])

    def test_an_observable_without_a_value_is_reported(self):
        alert, log = self.one({"unique": "r", "src_ip:description": "orphan"},
                              data_type={"src_ip": "ip"})
        self.assertEqual([], alert["observables"])
        self.assertIn("src_ip", log["warn"])

    def test_scope_false_turns_any_field_into_an_other_observable(self):
        alert, _ = self.one({"unique": "r", "free": "value"}, scope=False)
        self.assertEqual(1, len(alert["observables"]))
        self.assertEqual("other", alert["observables"][0]["dataType"])
        self.assertEqual("free: value", alert["observables"][0]["data"])

    def test_scope_false_never_sees_a_field_consumed_before_the_loop(self):
        """⚠️ Measured, and it says something about the code: `th_severity` is
        consumed by the severity branch BEFORE the dispatch loop snapshots the
        row, so the loop never visits it at all — no observable, and no warning.

        Which means the `THC-106` branch ("key used by TheHive as an internal
        field") appears to be **unreachable**: every deletion before the loop
        also removes the key from the snapshot, and every deletion inside the
        loop targets the key being processed. It is pinned here as unreachable
        rather than removed — proving dead code dead is its own ticket, and this
        one may not change behaviour.
        """
        alert, log = self.one({"unique": "r", "th_severity": "high"}, scope=False)
        self.assertEqual([], alert["observables"])
        self.assertEqual("", log["warn"])

    def test_scope_true_builds_no_other_observable(self):
        alert, _ = self.one({"unique": "r", "free": "value"}, scope=True)
        self.assertEqual([], alert["observables"])


class TestCustomFields(Base):

    def cf(self, row, type_, **kw):
        name = [k for k in row if k != "unique"][0]
        return self.one(row, custom_fields=[{"name": name, "type": type_}], **kw)

    def test_string_and_url_go_through_as_text(self):
        for type_ in ("string", "url"):
            alert, _ = self.cf({"unique": "r", "field": "value"}, type_)
            self.assertEqual([{"name": "field", "value": "value"}],
                             list(alert["customFields"]))

    def test_boolean_both_ways(self):
        alert, _ = self.cf({"unique": "r", "field": "true"}, "boolean")
        self.assertIs(True, alert["customFields"][0]["value"])
        alert, _ = self.cf({"unique": "r", "field": "0"}, "boolean")
        self.assertIs(False, alert["customFields"][0]["value"])

    def test_a_boolean_that_is_neither_is_dropped_and_named(self):
        alert, log = self.cf({"unique": "r", "field": "maybe"}, "boolean")
        self.assertEqual([], list(alert["customFields"]))
        self.assertIn("field", log["warn"])

    def test_integer_and_float(self):
        alert, _ = self.cf({"unique": "r", "field": "42"}, "integer")
        self.assertEqual(42, alert["customFields"][0]["value"])
        alert, _ = self.cf({"unique": "r", "field": "4.5"}, "float")
        self.assertEqual(4.5, alert["customFields"][0]["value"])

    def test_an_unreadable_integer_is_named_and_stays_readable(self):
        alert, log = self.cf({"unique": "r", "field": "forty"}, "integer")
        self.assertEqual([], list(alert["customFields"]))
        self.assertIn("field", log["warn"])
        self.assertIn("forty", alert["description"])

    def test_an_unreadable_float_behaves_the_same(self):
        alert, log = self.cf({"unique": "r", "field": "four point five"}, "float")
        self.assertEqual([], list(alert["customFields"]))
        self.assertIn("four point five", alert["description"])

    def test_date_as_epoch_and_as_iso(self):
        alert, _ = self.cf({"unique": "r", "field": "1700000000"}, "date")
        self.assertEqual(1700000000000, alert["customFields"][0]["value"])
        alert, _ = self.cf({"unique": "r", "field": "1700000000123"}, "date")
        self.assertEqual(1700000000123, alert["customFields"][0]["value"])
        alert, _ = self.cf({"unique": "r", "field": "2023-11-14T22:13:20+00:00"}, "date")
        self.assertEqual(1700000000000, alert["customFields"][0]["value"])

    def test_an_unknown_type_is_forwarded_as_text_with_a_warning(self):
        """⚠️ GitHub #133: freezing the list of TheHive types is what made every
        newly added type vanish. TheHive is the authority on its own schema."""
        alert, log = self.cf({"unique": "r", "field": "value"}, "invented-type")
        self.assertEqual("value", alert["customFields"][0]["value"])
        self.assertIn("invented-type", log["warn"])


class TestTtp(Base):

    def test_a_valid_ttp_known_to_the_catalogue(self):
        alert, _ = self.one({"unique": "r", "ttp": "defense-evasion::T1070::2026-01-15"},
                            catalogue={"T1070"})
        self.assertEqual(1, len(alert["ttps"]))
        self.assertEqual("T1070", alert["ttps"][0]["patternId"])
        self.assertNotIn("ttp", alert["events_keys"])

    def test_a_ttp_absent_from_the_catalogue_is_refused_by_name(self):
        alert, log = self.one({"unique": "r", "ttp": "evasion::T99999::2026-01-15"},
                              catalogue={"T1070"})
        # ⚠️ The key is ABSENT, not empty: `alert["ttps"]` is only written when
        # at least one TTP survived, or when the ES annotations supplied some.
        self.assertEqual([], list(alert.get("ttps", [])))
        self.assertIn("T99999", log["error"])

    def test_a_ttp_without_a_separator_is_reported_and_the_alert_lives(self):
        """Replaces the test that pinned the crash (#36, fixed 2026-08-28).

        `parts[2]` was read before any length check, inside a `try` catching
        only ValueError, so a `ttp` without `::` raised IndexError and took the
        whole alert action with it. The degraded path already existed three
        lines below; the indexed read short-circuited it.
        """
        alert, log = self.one({"unique": "r", "ttp": "nonsense"},
                              catalogue={"T1070"})
        self.assertIn("malformed", log["helper_error"])
        self.assertIn("nonsense", log["helper_error"], "the value must be named")
        self.assertEqual([], list(alert.get("ttps", [])))
        self.assertEqual("Notable event", alert["title"],
                         "the alert itself is unaffected by one unreadable field")

    def test_one_unreadable_ttp_does_not_lose_the_other_rows(self):
        """⚠️ The real cost of the crash, and the reason it was `serious`: the
        batch died, not the field. A row nobody had a problem with disappeared
        because another row carried a typo."""
        parsed, log = self.run_rows([
            {"unique": "good", "ttp": "evasion::T1070::2026-01-15"},
            {"unique": "bad", "ttp": "nonsense"},
        ], catalogue={"T1070"})

        self.assertEqual({"good", "bad"}, set(parsed))
        self.assertEqual(1, len(parsed["good"]["ttps"]))
        self.assertEqual([], list(parsed["bad"].get("ttps", [])))
        self.assertIn("malformed", log["helper_error"])

    def test_an_empty_ttp_field_is_not_even_visited(self):
        """An empty value never reaches the dispatch: the loop skips it. Pinned
        so the length check is not credited with something it does not do."""
        alert, log = self.one({"unique": "r", "ttp": ""}, catalogue={"T1070"})
        self.assertEqual("", log["helper_error"])

    def test_a_three_part_but_malformed_ttp_is_reported(self):
        alert, log = self.one({"unique": "r", "ttp": "evasion::NOT-AN-ID::2026-01-15"},
                              catalogue={"T1070"})
        self.assertIn("malformed", log["helper_error"])

    def test_an_invalid_occur_date_is_refused(self):
        alert, log = self.one({"unique": "r", "ttp": "evasion::T1070::yesterday"},
                              catalogue={"T1070"})
        self.assertIn("malformed", log["helper_error"])

    def test_an_unreachable_catalogue_lets_the_ttp_through(self):
        """⚠️ `None` means "I could not check", not "the catalogue is empty".
        Confusing the two turns an outage into a mass rejection."""
        alert, _ = self.one({"unique": "r", "ttp": "evasion::T1070::2026-01-15"},
                            catalogue=None)
        self.assertEqual(1, len(alert["ttps"]))

    def test_the_same_ttp_twice_is_stored_once(self):
        parsed, _ = self.run_rows([
            {"unique": "r", "ttp": "evasion::T1070::2026-01-15"},
            {"unique": "r", "ttp": "evasion::T1070::2026-01-15"},
        ], catalogue={"T1070"})
        alert = next(iter(parsed.values()))
        self.assertEqual(1, len(alert["ttps"]))

    def test_splunk_es_mitre_annotations_are_picked_up(self):
        alert, _ = self.one({
            "unique": "r",
            "_time": "1700000000",
            "annotations.mitre_attack.mitre_tactic": "defense-evasion",
            "annotations.mitre_attack": "T1070",
        })
        self.assertEqual(1, len(alert["ttps"]))
        self.assertEqual("T1070", alert["ttps"][0]["patternId"])
        self.assertEqual("defense-evasion", alert["ttps"][0]["tactic"])


class TestReinjectedTable(Base):

    def test_a_column_empty_in_every_event_is_dropped(self):
        parsed, _ = self.run_rows([
            {"unique": "r", "full": "1", "hollow_column": ""},
            {"unique": "r", "full": "2", "hollow_column": ""},
        ])
        description = next(iter(parsed.values()))["description"]
        # ⚠️ Assert on the TABLE only, never on the whole description: the
        # default text "No description provided" contains substrings that make
        # a naive assertNotIn fail for the wrong reason.
        table = description.split("Raw events:", 1)[1]
        self.assertIn("full", table)
        self.assertNotIn("hollow_column", table)

    def test_a_column_empty_in_only_one_event_is_kept(self):
        parsed, _ = self.run_rows([
            {"unique": "r", "sometimes": "1"},
            {"unique": "r", "sometimes": ""},
        ])
        table = next(iter(parsed.values()))["description"].split("Raw events:", 1)[1]
        self.assertIn("sometimes", table,
                      "only a column empty in EVERY event is dropped")

    def test_without_reinjection_the_description_stays_bare(self):
        alert, _ = self.one({"unique": "r", "a": "1"},
                            description_results_enable=False)
        self.assertNotIn("Raw events", alert["description"])

    def test_the_events_are_never_handed_back_to_the_caller(self):
        alert, _ = self.one({"unique": "r", "a": "1"})
        self.assertNotIn("events", alert,
                         "the raw events are consumed by the description, never returned")


class TestMultiValue(Base):

    def test_splunk_mv_fields_are_normalised(self):
        alert, _ = self.one({"unique": "r", "tags": "a", "__mv_tags": "$a$;$b$"})
        self.assertIn("a, b", alert["description"],
                      "a multivalue field is joined, and __mv_ never reaches TheHive")
        self.assertNotIn("__mv_tags", alert["events_keys"])


if __name__ == '__main__':
    unittest.main()
