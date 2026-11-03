"""A REAL Splunk ES notable: sent to TheHive, marked handled, never sent twice.

Unlike UC4, which fakes an `event_id` in a search, this case lets Splunk ES
create the notable (the `notable` adaptive response, on a saved search), reads
its real `event_id` through the ES `notable` macro, sends it with the add-on in
ES mode and `notable_status`, and then checks both sides:

* TheHive: one alert whose sourceRef is the notable's event_id;
* Splunk ES: the notable's review status really changed;
* a second send of the same notable is refused by TheHive ("already exists")
  and must be taken as a success: no retry, no error, still one alert.

⚠️ A notable cannot be deleted from `index=notable`. The test closes it
(status 5) in `tearDown` so it does not stay in an analyst's queue.
"""

import time
import unittest

from . import _config
from ._case import E2ECampaign

ACTION = "thehive_create_a_new_alert"

#: ES review status IDs of a default install: 1 New, 2 In Progress, 5 Closed.
IN_PROGRESS = "2"
CLOSED = "5"

NOTABLE_SEARCH = "| makeresults | eval x=1"
SEND_SEARCH = (
    'search `notable` | search rule_title="{title}" '
    '| eval name="{title}" | table event_id, name'
)


class TestRealNotable(E2ECampaign):

    def setUp(self):
        super().setUp()
        self._event_id = None

    def tearDown(self):
        try:
            if self._event_id:
                self.splunk._call(
                    "POST", f"{self.splunk.base}/services/notable_update",
                    data={"ruleUIDs": self._event_id, "status": CLOSED,
                          "comment": "closed by the e2e campaign"},
                )
        finally:
            super().tearDown()

    # -- helpers ----------------------------------------------------------

    def _notable_rows(self, title):
        spl = ('search `notable` | search rule_title="%s" '
               '| table event_id, status, status_label' % title)
        return self.splunk.search_events(spl, earliest="-30m")

    def _wait_notable(self, title, timeout_s=120, status=None):
        deadline = time.time() + timeout_s
        rows = []
        while time.time() < deadline:
            rows = self._notable_rows(title)
            if rows and (status is None or rows[0].get("status") == status):
                return rows[0]
            time.sleep(5)
        self.fail(f"notable {title!r} never reached status {status!r}: {rows}")

    def _send(self, name):
        sid = self.splunk.dispatch(name)
        state = self.splunk.wait_for_job(sid, _config.JOB_TIMEOUT)
        self.assertNotEqual("FAILED", state.get("dispatchState"))
        return state

    def _wait_log(self, name, marker, timeout_s=90):
        """The action's log is indexed with a delay: poll, never sleep."""
        deadline = time.time() + timeout_s
        rows = []
        while time.time() < deadline:
            rows = self.splunk.action_log(name)
            if any(marker in r for r in rows):
                break
            time.sleep(5)
        return rows

    def _create_the_notable(self, title):
        source = f"{self.prefix}_nb_src"
        self.splunk.create_saved_search(
            source, NOTABLE_SEARCH, "notable",
            {"rule_title": title, "rule_description": "e2e", "security_domain": "threat",
             "severity": "low", "default_status": "", "default_owner": "",
             "next_steps": "", "recommended_actions": ""},
        )
        self._searches.append(source)
        self._send(source)
        notable = self._wait_notable(title)
        self._event_id = notable["event_id"]
        self.assertEqual("1", notable.get("status"), "a fresh notable is New")
        return notable

    def _parameters(self):
        return {
            "thehive_instance_id": self.instance_name,
            "alert_mode": "es_mode",
            # Declared and absent from the rows: es_mode takes the event_id.
            "unique_id_field": "unique",
            "case_template": "",
            "type": "alert",
            "source": "splunk",
            "timestamp_field": "",
            "title": "name",
            "description": "name",
            "tags": "e2e,notable",
            "scope": "0",
            "severity": "2",
            "tlp": "2",
            "pap": "2",
            "description_results_enable": "0",
            "description_results_keep_observable": "0",
            "attach_results": "0",
            "attach_format": "0",
            "notable_status": IN_PROGRESS,
        }

    # -- the case ---------------------------------------------------------

    def test_the_notable_is_marked_and_a_second_send_is_refused_without_retry(self):
        title = f"{self.prefix} real notable"
        notable = self._create_the_notable(title)

        send = f"{self.prefix}_nb_send"
        self.splunk.create_saved_search(
            send, SEND_SEARCH.format(title=title), ACTION, self._parameters(),
            earliest="-1h")
        self._searches.append(send)

        # -- first send: the alert is created AND the notable moves ---------
        self._send(send)
        alerts = self.thehive.wait_for_alerts(self.prefix, 1, _config.THEHIVE_TIMEOUT)
        self.assertEqual(1, len(alerts))
        self.assertEqual(notable["event_id"], alerts[0].get("sourceRef"),
                         "the real event_id is the sourceRef")
        marked = self._wait_notable(title, status=IN_PROGRESS)
        self.assertEqual("In Progress", marked.get("status_label"))

        # -- second send of the very same notable ---------------------------
        state = self._send(send)
        rows = self._wait_log(send, "THCA-122")
        self.assertEqual(1, len(self.thehive.alerts_by_title_prefix(self.prefix)),
                         "TheHive refused the copy: still exactly one alert")
        self.assertTrue(any("THCA-122" in r for r in rows),
                        "the refusal is recognised as 'already exists' "
                        f"(job resultCount={state.get('resultCount')})")
        self.assertEqual([], [r[:200] for r in rows if "THCA-123" in r],
                         "an 'already exists' answer must never be retried")
        self.assert_clean_log(send)
        self.assertEqual(IN_PROGRESS, self._wait_notable(title).get("status"),
                         "the notable stays handled")


if __name__ == "__main__":
    unittest.main()
