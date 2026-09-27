"""UC3 -- a correlation search, one case, and the reserved `th_*` overrides.

Replays `docs/alert_actions_and_adaptive_responses.md` § UC3. Two things only
this case exercises:

* the **case** action rather than the alert one -- a different creation path,
  86 % shared with the alert one but not 100 %;
* the reserved fields `th_severity`, `th_tlp`, `th_pap`, which override what
  the dialog was configured with. The dialog here deliberately says something
  else (severity Low, TLP WHITE, PAP WHITE) so that a passing assertion can
  only mean the search won -- with matching values, the test would pass even
  if the overrides were ignored entirely.

⚠️ `th_tlp="AMBER+STRICT"` is the value the documentation uses, and it maps to
TLP 3 -- a level that did not exist in TheHive 4. It is the interesting one.
"""

import unittest

from . import _config
from ._case import E2ECampaign
from ._thehive import custom_fields

ACTION = "thehive_create_a_new_case"

#: Verbatim from the documentation, with the title carrying the run prefix.
SEARCH = """| makeresults
| eval other="account-12345", hostname="mycloud.aws.instance.corp"
| eval cert-alerted-on=now(), risk="Medium", th_severity=4, th_tlp="AMBER+STRICT", th_pap="2"
| eval name = "{title}", unique = "{unique}"
"""


class TestUC3SingleCase(E2ECampaign):

    def test_the_case_arrives_and_reserved_fields_win(self):
        title = f"{self.prefix} Correlation search - single case"
        search = SEARCH.format(title=title, unique=f"{self.prefix}_uc3")

        name = self.play(
            "uc3",
            search,
            ACTION,
            {
                "thehive_instance_id": self.instance_name,
                "case_mode": "regular_mode",
                "unique_id_field": "unique",
                "case_template": "",
                "source": "splunk",
                "timestamp_field": "",
                "title": "name",
                "description": "name",
                "tags": "e2e,uc3",
                "scope": "0",
                # Deliberately NOT what the search asks for: the point is to
                # watch `th_severity` / `th_tlp` / `th_pap` win.
                "severity": "1",
                "tlp": "0",
                "pap": "0",
                "description_results_enable": "0",
                "description_results_keep_observable": "0",
                "attach_results": "0",
                "attach_format": "0",
            },
        )

        cases = self.thehive.wait_for_cases(self.prefix, 1, _config.THEHIVE_TIMEOUT)
        self.assertEqual(1, len(cases), "exactly one case should have been created")
        the_case = cases[0]

        self.assertEqual(title, the_case.get("title"))
        self.assertEqual(4, the_case.get("severity"), "th_severity=4 must beat the dialog's 1")
        self.assertEqual(3, the_case.get("tlp"), 'th_tlp="AMBER+STRICT" must beat the dialog\'s WHITE')
        self.assertEqual(2, the_case.get("pap"), 'th_pap="2" must beat the dialog\'s WHITE')

        observables = {
            (obs.get("data"), obs.get("dataType"))
            for obs in self.thehive.wait_for_case_observables(
                the_case["_id"], 2, _config.THEHIVE_TIMEOUT
            )
        }
        self.assertEqual(
            {("account-12345", "other"), ("mycloud.aws.instance.corp", "hostname")},
            observables,
            "both fields are declared in thehive_datatypes.csv and must keep their type",
        )

        fields = custom_fields(the_case)
        self.assertEqual("Medium", fields.get("risk"))
        self.assertIsNotNone(fields.get("cert-alerted-on"))

        # The documentation states it plainly: a correlation search cannot
        # reach its own TTPs, so none is expected here. Asserting the absence
        # keeps that documented limitation from silently becoming a defect.
        self.assertEqual(
            [], self.thehive.case_procedures(the_case["_id"]),
            "UC3 documents that no TTP can come from a correlation search",
        )

        self.assert_clean_log(name)


if __name__ == "__main__":
    unittest.main()
