"""The return trip: Splunk -> TheHive -> Splunk, on a live instance.

The five use cases prove what leaves Splunk and what TheHive receives. They
say nothing about the other direction: the modular inputs that pull alerts,
cases, observables and TTPs back into an index. That half has its own way of
being wrong -- an input that runs, logs cheerfully, and indexes nothing.

⚠️ Measured on the lab instance before this case was written: every collection
sourcetype's most recent event was **seven days old**, while the input was
running every two minutes and logging `Got 0 cases` without a single error. It
was right -- nothing had changed in the organisation it watches -- but
"running, logging, and indexing nothing" is exactly what a broken input looks
like too. Only a round trip can tell the two apart.

⚠️ The collected data goes into a **throwaway index** that the test creates
and drops. Indexed events cannot be deleted; sending them into the operator's
own `thehive` index would leave rows behind that no teardown could remove.
"""

import json
import time
import unittest

from . import _config
from ._case import E2ECampaign

ACTION = "thehive_create_a_new_alert"
CASE_ACTION = "thehive_create_a_new_case"

#: #37, 2026-09-27: every "Extra data" option the form offers is collected.
#: One representative per type that the input used to DROP: `procedureCount`
#: (offered as "Common", kept for neither type before), `observableStats` and
#: `alertCount` ("Cases only", dropped for cases).
EXTRA_DATA = "procedureCount,observableStats,alertCount"

SEARCH = """| makeresults
| eval ip="1.2.3.4", fqdn="fake-website.com"
| eval name = "{title}", risk="Medium", unique = "{unique}"
| eval ttp="defense-evasion::T1027.003::"+tostring(strftime(now(),"%Y-%m-%d"))
"""

#: The input polls on an interval and queries a window ending at "now"; a fresh
#: alert therefore needs at least one full cycle, plus indexing time.
COLLECTION_TIMEOUT = 420


class TestCollectionRoundTrip(E2ECampaign):

    def setUp(self):
        super().setUp()
        self.index = f"e2e{self.runid}"
        self.input_name = f"{self.prefix}_collect"
        self._input_template = None
        self.splunk.create_index(self.index)

    def tearDown(self):
        self.splunk.delete_collection_input(self.input_name)
        # The index goes last and takes its events with it: that is the only
        # way this test can honestly claim to leave nothing behind.
        self.splunk.delete_index(self.index)
        super().tearDown()

    def test_the_created_alert_comes_back_into_splunk(self):
        title = f"{self.prefix} round trip"

        # The input must exist BEFORE the alert: it queries a window ending at
        # "now", so an alert created earlier than its first cycle is simply
        # outside every window it will ever ask for.
        self.splunk.create_collection_input(
            self.input_name,
            {
                "type": "alerts,cases",
                "date": "_createdAt,_updatedAt,date,startDate",
                "additional_information": "observables,ttps",
                "extra_data": EXTRA_DATA,
                "max_size_value": "1000",
            },
            self.instance_name,
            self.index,
            interval="60",
        )

        name = self.play(
            "collection",
            SEARCH.format(title=title, unique=f"{self.prefix}_rt"),
            ACTION,
            {
                "thehive_instance_id": self.instance_name,
                "alert_mode": "regular_mode",
                "unique_id_field": "unique",
                "type": "alert",
                "source": "splunk",
                "title": "name",
                "description": "name",
                "tags": "e2e,collection",
                "scope": "0",
                "severity": "2",
                "tlp": "2",
                "pap": "2",
                "description_results_enable": "0",
                "description_results_keep_observable": "0",
                "attach_results": "0",
                "attach_format": "0",
            },
        )

        case_title = f"{self.prefix} round trip case"
        case_name = self.play(
            "collection_case",
            SEARCH.format(title=case_title, unique=f"{self.prefix}_rtc"),
            CASE_ACTION,
            {
                "thehive_instance_id": self.instance_name,
                "case_mode": "regular_mode",
                "unique_id_field": "unique",
                "case_template": "",
                "source": "splunk",
                "timestamp_field": "",
                "title": "name",
                "description": "name",
                "tags": "e2e,collection",
                "scope": "0",
                "severity": "2",
                "tlp": "2",
                "pap": "2",
                "description_results_enable": "0",
                "description_results_keep_observable": "0",
                "attach_results": "0",
                "attach_format": "0",
            },
        )

        alerts = self.thehive.wait_for_alerts(self.prefix, 1, _config.THEHIVE_TIMEOUT)
        self.assertEqual(1, len(alerts), "the alert must reach TheHive first")
        cases = self.thehive.wait_for_cases(self.prefix, 1, _config.THEHIVE_TIMEOUT)
        self.assertEqual(1, len(cases), "the case must reach TheHive first")

        rows = self._wait_for_collection(title)
        self.assertTrue(
            rows,
            "the modular input never indexed the alert it had every chance to see: "
            f"nothing matching the title landed in index={self.index} within "
            f"{COLLECTION_TIMEOUT}s",
        )

        # ⚠️ Assert on the CONTENT that came back, not merely on the count.
        # An input that indexes an empty envelope is indistinguishable from a
        # working one if all you count is events.
        event = str(rows[0].get("_raw", ""))
        self.assertIn(title, event)
        for expected in ("Medium", "fake-website.com", "MEDIUM", "AMBER", '"dataType": "ip"'):
            self.assertIn(
                expected,
                event,
                f"{expected!r} left Splunk, reached TheHive, and must come back",
            )

        # #37: the alert's TTP must come back too. Until then the input
        # filtered `ttps` out of an ALERT's additional information (it was
        # kept for cases only), while the form offered it for both; this
        # assertion was the reverse one and pinned the gap. The alert really
        # carries the procedure -- UC1 asserts it on TheHive's side.
        self.assertIn(
            "T1027.003",
            event,
            "the alert carries a TTP and the input asks for `ttps`: it must be "
            "indexed with the alert (collection_options.py / get_alerts_events)",
        )

        # #37 extra_data: the ticked option must come back under `extraData`.
        # Consistent with the same event rather than with a guess: the alert
        # carries exactly the procedures indexed with it.
        alert_event = json.loads(rows[0]["_raw"])
        extra = alert_event.get("extraData") or {}
        self.assertIn(
            "procedureCount", extra,
            "`procedureCount` is ticked for an alert and must be collected "
            "(collection_options.EXTRA_DATA)")
        self.assertEqual(len(alert_event.get("ttps") or []), extra["procedureCount"])

        case_rows = self._wait_for_collection(case_title, event_type="Case")
        self.assertTrue(case_rows, f"the case never came back into index={self.index}")
        case_event = json.loads(case_rows[0]["_raw"])
        case_extra = case_event.get("extraData") or {}
        for option in ("procedureCount", "observableStats", "alertCount"):
            self.assertIn(
                option, case_extra,
                f"`{option}` is ticked for a case and must be collected "
                "(collection_options.EXTRA_DATA)")
        self.assertIsInstance(case_extra["observableStats"], dict)
        self.assertEqual(0, case_extra["alertCount"], "the case was created directly, from no alert")

        self.assert_clean_log(name)
        self.assert_clean_log(case_name)

    def _wait_for_collection(self, title, event_type="Alert"):
        """Poll the throwaway index until the object comes back, or give up.

        ⚠️ Filtered on the object type AND the exact title: the alert's title
        is a prefix of the case's, so a bare phrase search would hand the
        alert back to the case assertions.
        """
        deadline = time.time() + COLLECTION_TIMEOUT
        while time.time() < deadline:
            rows = [
                row for row in self.splunk.search_events(
                    f'search index={self.index} "{title}"', earliest="-1h")
                if self._is(row, title, event_type)
            ]
            if rows:
                return rows
            time.sleep(10)
        return []

    @staticmethod
    def _is(row, title, event_type):
        try:
            event = json.loads(row.get("_raw", ""))
        except ValueError:
            return False
        return event.get("title") == title and event.get("type", event_type) == event_type


if __name__ == "__main__":
    unittest.main()
