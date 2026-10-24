"""Cortex -- the "Run a new job" alert action, then `cortexjobs` reads it back.

The only case of the campaign that talks to Cortex. It exercises the path that
ships (a scheduled saved search carrying `cortex_run_a_new_job`), leaves TLP
and PAP to the shipped `.conf` defaults on purpose, and asserts on the job
record Cortex holds.

⚠️ The read-back goes through the add-on's own `cortexjobs`, not through an
independent client: the Cortex API key lives only in Splunk's credential store,
and the campaign never copies a credential out of it. `cortexjobs` is a
different code path from the alert action (another module, another call), so it
still catches what the action sent wrong -- #45's TLP one step too high was
exactly that kind of defect.

⚠️ Cortex jobs are left in place. A job is analysis history, not an object the
add-on creates for later use, and deleting one needs the very key the campaign
refuses to read. The data analysed carries the run prefix, so a leftover is
recognisable.
"""

import os
import time
import unittest

from . import _config
from ._case import E2ECampaign

ACTION = "cortex_run_a_new_job"

#: `cortexjobs` with a server-side hold: a job read while still running would
#: carry no report, and the assertion below is about the finished record.
READ_BACK = """| makeresults
| eval data="{data}", wait=30
| cortexjobs {instance}
| table cortex_job_id, cortex_job_status, cortex_job_finished, cortex_job_dataType,
        cortex_job_analyzerName, cortex_job_tlp, cortex_job_pap, cortex_job_report,
        cortex_job_errorMessage"""

CORTEX_SETTINGS = {
    "E2E_CORTEX_INSTANCE": "id of an add-on instance of type Cortex3",
    "E2E_CORTEX_ANALYZER": "an analyzer enabled on it that accepts the `domain` datatype",
}


def _cortex_skip_reason():
    missing = [name for name in CORTEX_SETTINGS if not os.environ.get(name)]
    if not missing:
        return None
    return "Cortex case not configured; set " + ", ".join(
        f"{name} ({CORTEX_SETTINGS[name]})" for name in missing
    )


@unittest.skipIf(_cortex_skip_reason(), _cortex_skip_reason())
class TestCortexRunANewJob(E2ECampaign):

    def test_the_job_reaches_cortex_with_the_shipped_defaults(self):
        instance = os.environ["E2E_CORTEX_INSTANCE"]
        analyzer = os.environ["E2E_CORTEX_ANALYZER"]
        # A domain, not an IP: the run prefix keeps it unique and recognisable.
        data = f"{self.prefix}.example.com"

        name = self.play(
            "cortex",
            f'| makeresults | eval data="{data}", datatype="domain"',
            ACTION,
            {
                "cortex_instance_id": instance,
                "analyzers": analyzer,
                "data_field_name": "data",
                "datatype_field_name": "datatype",
                # tlp and pap deliberately absent: the .conf defaults are under test
            },
        )

        rows = []
        deadline = time.time() + _config.JOB_TIMEOUT
        while time.time() < deadline:
            rows = self.splunk.search_events(READ_BACK.format(data=data, instance=instance))
            if rows and rows[0].get("cortex_job_finished") == "1":
                break
            time.sleep(5)

        self.assertEqual(1, len(rows), "exactly one Cortex job should carry the run's data")
        job = rows[0]
        self.assertEqual("domain", job.get("cortex_job_dataType"))
        self.assertEqual(analyzer, job.get("cortex_job_analyzerName"))
        # Cortex counts WHITE=0 .. RED=3: the shipped default must be a real AMBER.
        # Checked BEFORE the status: an analyzer refuses a TLP above its maximum
        # (AMBER by default), so a wrong TLP surfaces as a Failure further down.
        self.assertEqual("2", job.get("cortex_job_tlp"), "TLP should be AMBER (2)")
        self.assertEqual("2", job.get("cortex_job_pap"), "PAP should be AMBER (2)")
        self.assertEqual("1", job.get("cortex_job_finished"), "the job never finished")
        self.assertEqual(
            "Success", job.get("cortex_job_status"),
            "the analyzer failed on the Cortex side: " + str(job.get("cortex_job_errorMessage")),
        )
        self.assertTrue(job.get("cortex_job_report"), "a finished job comes back with its report")

        self.assert_clean_log(name)


if __name__ == "__main__":
    unittest.main()
