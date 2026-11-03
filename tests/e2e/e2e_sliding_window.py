"""Sliding window: overlapping runs re-send the same alerts, again and again.

A scheduled search over "the last N minutes" run more often than N sees the same
events several times, so the add-on keeps sending alerts TheHive already holds
(in production: 5,101 refusals for 40 distinct alerts in a day, each retried).
Three overlapping runs here: A | A+B | B+C. Expected in TheHive: A, B, C once
each. Expected in the add-on log: no retry, no error.
"""

import time
import unittest

from . import _config
from ._case import E2ECampaign

ACTION = "thehive_create_a_new_alert"

#: `window` picks which of the three events the run still sees.
SEARCH = """| makeresults count=3
| streamstats count as n
| eval name = "{prefix} event " . n, unique = "{prefix}_w" . n
| search n IN ({window})
"""


class TestSlidingWindow(E2ECampaign):

    def test_overlapping_runs_create_each_alert_once_without_retry(self):
        parameters = {
            "thehive_instance_id": self.instance_name,
            "alert_mode": "regular_mode",
            "unique_id_field": "unique",
            "case_template": "",
            "type": "alert",
            "source": "splunk",
            "timestamp_field": "",
            "title": "name",
            "description": "name",
            "tags": "e2e,window",
            "scope": "0",
            "severity": "2",
            "tlp": "2",
            "pap": "2",
            "description_results_enable": "0",
            "description_results_keep_observable": "0",
            "attach_results": "0",
            "attach_format": "0",
        }

        names = []
        for step, window in enumerate(("1", "1,2", "2,3")):
            name = f"{self.prefix}_win{step}"
            self.splunk.create_saved_search(
                name, SEARCH.format(prefix=self.prefix, window=window), ACTION, parameters)
            self._searches.append(name)
            sid = self.splunk.dispatch(name)
            state = self.splunk.wait_for_job(sid, _config.JOB_TIMEOUT)
            self.assertNotEqual("FAILED", state.get("dispatchState"))
            names.append(name)

        alerts = self.thehive.wait_for_alerts(self.prefix, 3, _config.THEHIVE_TIMEOUT)
        self.assertEqual(3, len(alerts), "A, B and C once each, never twice")
        self.assertEqual(3, len({a.get("sourceRef") for a in alerts}))

        # Run 2 re-sends A, run 3 re-sends B: TheHive refuses both ("already
        # exists", HTTP 400) and the add-on must take each as a success.
        # The action log is indexed with a delay: wait for it, never guess.
        deadline = time.time() + 90
        while time.time() < deadline and sum(
                "THCA-122" in r for n in names for r in self.splunk.action_log(n)) < 2:
            time.sleep(5)
        refusals = 0
        for name in names:
            rows = self.splunk.action_log(name)
            refusals += sum("THCA-122" in r for r in rows)
            self.assertEqual([], [r[:200] for r in rows if "THCA-123" in r],
                             "a re-sent alert must never be retried")
            self.assert_clean_log(name)
        self.assertEqual(2, refusals, "A and B were each re-sent once")


if __name__ == "__main__":
    unittest.main()
