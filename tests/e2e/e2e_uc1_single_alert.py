"""UC1 -- one saved search, one alert, three observables, one TTP.

Replays `docs/alert_actions_and_adaptive_responses.md` § UC1. The search is
taken verbatim from the documentation apart from the title, which carries the
run prefix so the campaign can find and destroy exactly what it created.

⚠️ UC1 is the only use case whose **parameter table is missing** from the
documentation: it exists as screenshots only. The values below are therefore
derived from the search itself (which field holds the title, which holds the
unique id) and not copied from a table. That gap is worth closing in the doc.
"""

import unittest

from . import _config
from ._case import E2ECampaign
from ._thehive import custom_fields

ACTION = "thehive_create_a_new_alert"

#: Verbatim from the documentation, with `{title}` substituted for the value
#: of `name` so the alert can be identified. Everything else is unchanged.
SEARCH = """| makeresults
| eval ip="1.2.3.4", fqdn="fake-website.com"
| table ip, fqdn
| append
    [| makeresults
| eval hash="a27fa23e7316cb8fb7a57bd11664f2ff"
| table hash]
| eval name = "{title}", cert-alerted-on=now(), risk="Medium", ttp="defense-evasion::T1027.003::"+tostring(strftime(now(),"%Y-%m-%d"))
| eval unique = "{unique}"
"""


class TestUC1SingleAlert(E2ECampaign):

    def test_the_alert_arrives_with_all_its_content(self):
        title = f"{self.prefix} T1027.003 - Obfuscated Files or Information: Steganography"
        search = SEARCH.format(title=title, unique=f"{self.prefix}_uc1")

        name = self.play(
            "uc1",
            search,
            ACTION,
            {
                "thehive_instance_id": self.instance_name,
                "alert_mode": "regular_mode",
                "unique_id_field": "unique",
                "case_template": "",
                "type": "alert",
                "source": "splunk",
                "timestamp_field": "",
                "title": "name",
                "description": "name",
                "tags": "e2e,uc1",
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

        # -- the envelope ------------------------------------------------
        self.assertEqual(title, alert.get("title"))
        self.assertEqual("alert", alert.get("type"))
        self.assertEqual("splunk", alert.get("source"))
        self.assertEqual(2, alert.get("severity"), "Medium")
        self.assertEqual(2, alert.get("tlp"), "AMBER")
        self.assertEqual(2, alert.get("pap"), "AMBER")
        self.assertIn("e2e", alert.get("tags") or [])

        # -- the observables: value AND type -----------------------------
        # ⚠️ Checking only the values would let a whole class of defect
        # through: an observable that arrives as `other` is present, visible,
        # and useless -- no analyzer will ever run on it.
        observables = {
            (obs.get("data"), obs.get("dataType"))
            for obs in self.thehive.wait_for_alert_observables(
                alert["_id"], 3, _config.THEHIVE_TIMEOUT
            )
        }
        self.assertEqual(
            {
                ("1.2.3.4", "ip"),
                ("fake-website.com", "fqdn"),
                ("a27fa23e7316cb8fb7a57bd11664f2ff", "hash"),
            },
            observables,
        )

        # -- the custom fields -------------------------------------------
        fields = custom_fields(alert)
        self.assertEqual("Medium", fields.get("risk"),
                         "a string custom field must survive the trip")
        self.assertIsNotNone(fields.get("cert-alerted-on"),
                             "a date custom field must survive the trip")
        # ⚠️ Measured, and deliberately NOT asserted as a custom field: `name`
        # is what the `title` parameter names, and a field consumed as the
        # title is not mapped a second time -- even though TheHive declares a
        # custom field of the same name. Asserting the opposite would be the
        # test inventing a requirement the add-on never claimed.
        self.assertNotIn("name", fields, "documented behaviour: the title source is consumed")

        # -- the TTP ------------------------------------------------------
        procedures = self.thehive.alert_procedures(alert["_id"])
        self.assertEqual(1, len(procedures), "one TTP was sent, one must arrive")
        self.assertEqual("T1027.003", procedures[0].get("patternId"))

        # -- and Splunk's own account of it ------------------------------
        self.assert_clean_log(name)


if __name__ == "__main__":
    unittest.main()
