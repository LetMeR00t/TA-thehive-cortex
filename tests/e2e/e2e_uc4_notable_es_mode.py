"""UC4 -- the ES notable path, which is exactly one thing: where sourceRef comes from.

Replays `docs/alert_actions_and_adaptive_responses.md` § UC4. The search is
the documented one, plus the `event_id` a notable carries.

⚠️ **This case does NOT create a real notable event.** Read
`modalert_thehive_common.py`: `es_mode` changes one decision and only one --
when the configured `unique_id_field` is absent from the row, the alert's
`sourceRef` is taken from `event_id` (the notable's identifier) instead of
from the search id. Everything else is the ordinary alert path, already
covered by UC1 and UC2.

Standing up a correlation search would therefore prove nothing more, and it
would write into the `notable` index -- which this campaign could not clean
up afterwards. A test that leaves rows behind in a production index is worse
than the coverage it buys. What it does instead is drive the *decision*: the
row carries an `event_id`, the configured unique id field is deliberately
absent, and the assertion is on the sourceRef TheHive ended up with.

⚠️ And the sourceRef is not cosmetic: rows sharing one are MERGED into a
single alert. Getting it wrong does not produce a visibly wrong alert, it
silently merges or splits alerts that should not be.
"""

import unittest

from . import _config
from ._case import E2ECampaign
from ._thehive import custom_fields

ACTION = "thehive_create_a_new_alert"

#: The documented UC4 search, plus the `event_id` an ES notable carries. Note
#: what is NOT here: any field called `unique`. That absence is the point.
SEARCH = """| makeresults
| eval other="account-12345", hostname="mycloud.aws.instance.corp"
| eval cert-alerted-on=now(), risk="Medium"
| eval event_id = "{event_id}", name = "{title}"
"""


class TestUC4NotableEsMode(E2ECampaign):

    def test_the_sourceref_comes_from_the_notable_event_id(self):
        title = f"{self.prefix} Notable - adaptive response"
        event_id = f"{self.prefix}_notable_event_id"
        search = SEARCH.format(title=title, event_id=event_id)

        name = self.play(
            "uc4",
            search,
            ACTION,
            {
                "thehive_instance_id": self.instance_name,
                "alert_mode": "es_mode",
                # Declared, and deliberately absent from the rows: that is the
                # condition under which es_mode reaches for `event_id`.
                "unique_id_field": "unique",
                "case_template": "",
                "type": "alert",
                "source": "splunk",
                "timestamp_field": "",
                "title": "name",
                "description": "name",
                "tags": "e2e,uc4",
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
        self.assertEqual(1, len(alerts), "exactly one alert should have been created")
        alert = alerts[0]

        self.assertEqual(
            event_id,
            alert.get("sourceRef"),
            "in es_mode with the unique id field absent, sourceRef is the notable's event_id",
        )
        self.assertEqual(title, alert.get("title"))

        observables = {
            (obs.get("data"), obs.get("dataType"))
            for obs in self.thehive.wait_for_alert_observables(
                alert["_id"], 2, _config.THEHIVE_TIMEOUT
            )
        }
        self.assertEqual(
            {("account-12345", "other"), ("mycloud.aws.instance.corp", "hostname")},
            observables,
        )

        fields = custom_fields(alert)
        self.assertEqual("Medium", fields.get("risk"))
        self.assertIsNotNone(fields.get("cert-alerted-on"))

        self.assert_clean_log(name)


if __name__ == "__main__":
    unittest.main()
