"""`cortexjobs`: waiting, distinguishing, and harvesting.

Three defects, all on the nominal path, none reachable by a test before this
file existed -- the whole loop lived inside `if __name__ == '__main__'`:

1. the report of a job that is still running comes back EMPTY, and an empty
   report is written out exactly like an analyzer that found nothing;
2. `get_report_async` -- the call that lets Cortex hold the answer server-side
   -- was never used, so the add-on could only ask and give up;
3. `get_artifacts` was never called either, so the observables an analyzer
   EXTRACTS never came back to Splunk at all.

Every response here is a stub. No Cortex instance is contacted, deliberately:
these are the shapes of the answers, not the answers of one server.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock

# Mock EVERYTHING that is not available locally
mocks = [
    'splunklib', 'splunklib.client', 'solnlib', 'solnlib.log',
    'solnlib.modular_input', 'solnlib.utils', 'ta_thehive_cortex_declare',
    'certifi', 'common', 'ta_logging', 'requests', 'requests.adapters',
    'requests.auth', 'urllib3', 'splunk', 'splunk.Intersplunk', 'globals',
    'cortex',
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
    import cortex_search_jobs  # noqa: E402


class Stub:
    """An object whose `vars()` is exactly the dict it was given.

    ⚠️ Matches how cortex4py builds its models: `self.__dict__ = data`. A
    MagicMock would answer every attribute and hide a missing field.
    """

    def __init__(self, **data):
        self.__dict__ = dict(data)


def a_job(**overrides):
    data = {
        "id": "job-1",
        "status": "InProgress",
        "analyzerName": "Abuse_Finder_3_0",
        "dataType": "ip",
        "data": "192.0.2.10",
        "createdAt": 1700000000000,
        "updatedAt": 1700000001000,
    }
    data.update(overrides)
    return Stub(**data)


class TestCollectJob(unittest.TestCase):

    def setUp(self):
        self.logger = MagicMock()
        self.cortex = MagicMock()

    def _report(self, **overrides):
        data = {"id": "job-1", "status": "Success", "report": {"taxonomies": "2"}}
        data.update(overrides)
        return Stub(**data)

    def test_running_job_is_reported_as_running_not_as_empty(self):
        """⚠️ The defect this file exists for: an unfinished job used to be
        written out with an empty report, which reads as "nothing found"."""
        self.cortex.jobs.get_report.return_value = self._report(
            status="InProgress", report={}
        )

        event = cortex_search_jobs.collect_job(
            self.cortex, a_job(), 0, self.logger
        )

        self.assertEqual(event["cortex_job_status"], "InProgress")
        self.assertEqual(event["cortex_job_finished"], 0)
        # The field is ABSENT, not empty: absence cannot be mistaken for a
        # result, an empty list can.
        self.assertNotIn("cortex_job_report", event)
        self.cortex.jobs.get_artifacts.assert_not_called()

    def test_wait_zero_does_not_ask_cortex_to_hold(self):
        self.cortex.jobs.get_report.return_value = self._report()

        cortex_search_jobs.collect_job(self.cortex, a_job(), 0, self.logger)

        self.cortex.jobs.get_report.assert_called_once_with("job-1")
        self.cortex.jobs.get_report_async.assert_not_called()

    def test_wait_makes_cortex_hold_the_answer(self):
        self.cortex.jobs.get_report_async.return_value = self._report()

        event = cortex_search_jobs.collect_job(
            self.cortex, a_job(status="Waiting"), 30, self.logger
        )

        self.cortex.jobs.get_report_async.assert_called_once_with(
            "job-1", timeout="30seconds"
        )
        self.cortex.jobs.get_report.assert_not_called()
        # The status of the ANSWER wins over the one the search returned
        self.assertEqual(event["cortex_job_status"], "Success")
        self.assertEqual(event["cortex_job_finished"], 1)

    def test_a_finished_job_is_never_held(self):
        """Waiting on something already finished would spend the timeout for
        nothing, on every row."""
        self.cortex.jobs.get_report.return_value = self._report()

        cortex_search_jobs.collect_job(
            self.cortex, a_job(status="Success"), 30, self.logger
        )

        self.cortex.jobs.get_report_async.assert_not_called()
        self.cortex.jobs.get_report.assert_called_once_with("job-1")

    def test_artifacts_extracted_by_the_analyzer_come_back(self):
        self.cortex.jobs.get_report.return_value = self._report()
        self.cortex.jobs.get_artifacts.return_value = [
            Stub(id="a1", dataType="domain", data="evil.example"),
            Stub(id="a2", dataType="ip", data="203.0.113.4"),
        ]

        event = cortex_search_jobs.collect_job(
            self.cortex, a_job(status="Success"), 0, self.logger
        )

        self.assertEqual(
            event["cortex_job_artifacts"],
            ["domain::evil.example", "ip::203.0.113.4"],
        )
        self.assertEqual(event["cortex_job_artifacts_count"], 2)

    def test_unreachable_artifacts_do_not_discard_the_report(self):
        """⚠️ Two separate calls: losing the second must not lose the first."""
        self.cortex.jobs.get_report.return_value = self._report()
        self.cortex.jobs.get_artifacts.side_effect = Exception("503")

        event = cortex_search_jobs.collect_job(
            self.cortex, a_job(status="Success"), 0, self.logger
        )

        self.assertEqual(event["cortex_job_report"], ["taxonomies::2"])
        self.assertNotIn("cortex_job_artifacts", event)
        self.logger.warn.assert_called()

    def test_a_failed_job_reports_its_failure_and_asks_for_no_artifact(self):
        self.cortex.jobs.get_report.return_value = self._report(
            status="Failure", report={"errorMessage": "analyzer crashed"}
        )

        event = cortex_search_jobs.collect_job(
            self.cortex, a_job(status="Failure"), 0, self.logger
        )

        self.assertEqual(event["cortex_job_finished"], 1)
        self.assertEqual(
            event["cortex_job_report"], ["errorMessage::analyzer crashed"]
        )
        self.cortex.jobs.get_artifacts.assert_not_called()

    def test_a_finished_job_without_report_key_does_not_raise(self):
        """A `Deleted` job is final and carries no report at all. The previous
        code indexed the key directly and died on it."""
        self.cortex.jobs.get_report.return_value = Stub(
            id="job-1", status="Deleted"
        )

        event = cortex_search_jobs.collect_job(
            self.cortex, a_job(status="Deleted"), 0, self.logger
        )

        self.assertEqual(event["cortex_job_report"], [])
        self.assertEqual(event["cortex_job_finished"], 1)

    def test_dates_are_converted_and_a_missing_one_is_not_fatal(self):
        self.cortex.jobs.get_report.return_value = self._report()
        job = a_job(status="Success", startDate=1700000000000)
        del job.__dict__["updatedAt"]

        event = cortex_search_jobs.collect_job(self.cortex, job, 0, self.logger)

        self.assertEqual(event["cortex_job_startDate"], 1700000000)
        self.assertEqual(event["cortex_job_createdAt"], 1700000000)
        self.assertNotIn("cortex_job_updatedAt", event)


if __name__ == '__main__':
    unittest.main()
