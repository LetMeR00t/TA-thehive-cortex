"""UC2 -- one saved search, several alerts, and the composite observable fields.

Replays `docs/alert_actions_and_adaptive_responses.md` § UC2, whose parameter
table the documentation does give in full; the values below are copied from
it, not reinvented.

This is the case that earns the campaign its keep. UC1 proves the happy path;
UC2 exercises the per-observable metadata carried by `ip:<attribute>` fields
-- description, tags, TLP, PAP, ioc, sighted, sighted_at, ignore_similarity.
Every one of those can be dropped in silence: the alert still arrives, the
observable is still there, and only the attribute is missing.
"""

import unittest

from . import _config
from ._case import E2ECampaign
from ._thehive import custom_fields

ACTION = "thehive_create_a_new_alert"

#: Verbatim from the documentation, except for `{title}` (so the run can find
#: its own objects) and `{u1}` / `{u2}` (so the two groups are stable rather
#: than derived from `now()`, which would make the assertion depend on when
#: the test ran).
SEARCH = """| makeresults
| eval ip="5.6.7.8", "ip:description" = "another description for this specific ip", "ip:tags" = "hello,world", ttp="reconnaissance::T1595.001::"+tostring(strftime(now(),"%Y-%m-%d")), unique="{u1}"
| table ip, "ip:description", "ip:tags", ttp, unique
| append
    [| makeresults
| eval ip="1.2.3.4", ttp="reconnaissance::T1593.002::"+tostring(strftime(now(),"%Y-%m-%d")), unique="{u1}", "ip:tlp" = "GREEN", "ip:pap" = "RED", "ip:is_ioc" = 1
| table ip, "ip:tlp", "ip:pap", "ip:is_ioc", ttp, unique]
| append
    [| makeresults
| eval ip="1.3.5.8", "ip:description" = "description for this ip", ttp="reconnaissance::T1593.002::"+tostring(strftime(now(),"%Y-%m-%d")), unique="{u2}", "ip:sighted" = 1, "ip:sighted_at" = relative_time(now(),"-6h"), "ip:ignore_similarity" = 1
| table ip, "ip:description", "ip:sighted", "ip:sighted_at", "ip:ignore_similarity", ttp, unique]
| eventstats values(ip) as all_ip by unique
| eval all_ip = mvjoin(all_ip,", ")
| eval name = "{title} scan from "+all_ip, cert-alerted-on=now(), risk="Medium", info="A custom info added to the event"
| fields - all_ip
"""


class TestUC2SeveralAlerts(E2ECampaign):

    def test_two_alerts_and_their_observable_attributes(self):
        title = f"{self.prefix} Massive scan on website company.corp"
        search = SEARCH.format(
            title=title, u1=f"{self.prefix}.1", u2=f"{self.prefix}.2"
        )

        name = self.play(
            "uc2",
            search,
            ACTION,
            {
                # Copied from the UC2 table in the documentation.
                "thehive_instance_id": self.instance_name,
                "alert_mode": "regular_mode",
                "unique_id_field": "unique",
                "case_template": "",
                "type": "alert",
                "source": "splunk",
                "timestamp_field": "",
                "title": "name",
                "description": "info",
                "tags": "malicious,external,steganography",
                "scope": "0",
                "severity": "2",
                "tlp": "2",
                "pap": "2",
                "description_results_enable": "1",
                "description_results_keep_observable": "1",
                "attach_results": "0",
                "attach_format": "0",
            },
        )

        alerts = self.thehive.wait_for_alerts(self.prefix, 2, _config.THEHIVE_TIMEOUT)
        self.assertEqual(
            2, len(alerts),
            "the unique id field groups three rows into two alerts, so two must arrive",
        )

        by_observables = {}
        for alert in alerts:
            observables = self.thehive.wait_for_alert_observables(
                alert["_id"], 1, _config.THEHIVE_TIMEOUT
            )
            by_observables[alert["_id"]] = {
                obs.get("data"): obs for obs in observables
            }

        group_two = [
            (aid, obs) for aid, obs in by_observables.items() if len(obs) == 2
        ]
        group_one = [(aid, obs) for aid, obs in by_observables.items() if len(obs) == 1]
        self.assertEqual(1, len(group_two), "one alert carries two observables")
        self.assertEqual(1, len(group_one), "the other carries one")

        # -- the alert grouping two rows ---------------------------------
        _, observables = group_two[0]
        self.assertEqual({"5.6.7.8", "1.2.3.4"}, set(observables))
        self.assertTrue(
            all(obs.get("dataType") == "ip" for obs in observables.values()),
            "both must arrive typed as ip, not as `other`",
        )

        described = observables["5.6.7.8"]
        self.assertEqual("another description for this specific ip", described.get("message"))
        # ⚠️ The add-on adds a `field:<name>` tag of its own, so this is a
        # subset check, not an equality: measured, the observable arrives with
        # {"hello", "world", "field:ip"}. Asserting equality would make the
        # test fail on a feature rather than on a defect.
        self.assertLessEqual({"hello", "world"}, set(described.get("tags") or []))
        self.assertIn("field:ip", described.get("tags") or [],
                      "the add-on records which Splunk field produced the observable")

        qualified = observables["1.2.3.4"]
        self.assertEqual(1, qualified.get("tlp"), "ip:tlp = GREEN")
        self.assertEqual(3, qualified.get("pap"), "ip:pap = RED")
        self.assertTrue(qualified.get("ioc"), "ip:is_ioc = 1")

        # -- the alert with the sighted observable ------------------------
        _, single = group_one[0]
        seen = single["1.3.5.8"]
        self.assertEqual("ip", seen.get("dataType"))
        self.assertEqual("description for this ip", seen.get("message"))
        self.assertTrue(seen.get("sighted"), "ip:sighted = 1")
        self.assertIsNotNone(seen.get("sightedAt"), "ip:sighted_at was given")
        self.assertTrue(seen.get("ignoreSimilarity"), "ip:ignore_similarity = 1")

        # -- what both alerts share --------------------------------------
        for alert in alerts:
            fields = custom_fields(alert)
            self.assertEqual("Medium", fields.get("risk"))
            self.assertIsNotNone(fields.get("cert-alerted-on"))
            self.assertEqual(
                {"malicious", "external", "steganography"},
                set(alert.get("tags") or []),
            )
            self.assertIn(
                "A custom info added to the event",
                alert.get("description") or "",
                "the Description parameter names the field holding the text",
            )

        self.assert_clean_log(name)


if __name__ == "__main__":
    unittest.main()
