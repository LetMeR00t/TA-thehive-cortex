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
from ._case import CampagneE2E
from ._thehive import champs_personnalises

ACTION = "thehive_create_a_new_alert"

#: Verbatim from the documentation, except for `{titre}` (so the run can find
#: its own objects) and `{u1}` / `{u2}` (so the two groups are stable rather
#: than derived from `now()`, which would make the assertion depend on when
#: the test ran).
RECHERCHE = """| makeresults
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
| eval name = "{titre} scan from "+all_ip, cert-alerted-on=now(), risk="Medium", info="A custom info added to the event"
| fields - all_ip
"""


class TestUC2PlusieursAlertes(CampagneE2E):

    def test_deux_alertes_et_leurs_attributs_d_observable(self):
        titre = f"{self.prefixe} Massive scan on website company.corp"
        recherche = RECHERCHE.format(
            titre=titre, u1=f"{self.prefixe}.1", u2=f"{self.prefixe}.2"
        )

        nom = self.jouer(
            "uc2",
            recherche,
            ACTION,
            {
                # Copied from the UC2 table in the documentation.
                "thehive_instance_id": self.nom_instance,
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

        alertes = self.thehive.attendre_alertes(self.prefixe, 2, _config.DELAI_THEHIVE)
        self.assertEqual(
            2, len(alertes),
            "the unique id field groups three rows into two alerts, so two must arrive",
        )

        par_observables = {}
        for alerte in alertes:
            observables = self.thehive.observables_de_l_alerte(alerte["_id"])
            par_observables[alerte["_id"]] = {
                obs.get("data"): obs for obs in observables
            }

        groupe_deux = [
            (aid, obs) for aid, obs in par_observables.items() if len(obs) == 2
        ]
        groupe_un = [(aid, obs) for aid, obs in par_observables.items() if len(obs) == 1]
        self.assertEqual(1, len(groupe_deux), "one alert carries two observables")
        self.assertEqual(1, len(groupe_un), "the other carries one")

        # -- the alert grouping two rows ---------------------------------
        _, observables = groupe_deux[0]
        self.assertEqual({"5.6.7.8", "1.2.3.4"}, set(observables))
        self.assertTrue(
            all(obs.get("dataType") == "ip" for obs in observables.values()),
            "both must arrive typed as ip, not as `other`",
        )

        decrit = observables["5.6.7.8"]
        self.assertEqual("another description for this specific ip", decrit.get("message"))
        # ⚠️ The add-on adds a `field:<name>` tag of its own, so this is a
        # subset check, not an equality: measured, the observable arrives with
        # {"hello", "world", "field:ip"}. Asserting equality would make the
        # test fail on a feature rather than on a defect.
        self.assertLessEqual({"hello", "world"}, set(decrit.get("tags") or []))
        self.assertIn("field:ip", decrit.get("tags") or [],
                      "the add-on records which Splunk field produced the observable")

        qualifie = observables["1.2.3.4"]
        self.assertEqual(1, qualifie.get("tlp"), "ip:tlp = GREEN")
        self.assertEqual(3, qualifie.get("pap"), "ip:pap = RED")
        self.assertTrue(qualifie.get("ioc"), "ip:is_ioc = 1")

        # -- the alert with the sighted observable ------------------------
        _, seul = groupe_un[0]
        vu = seul["1.3.5.8"]
        self.assertEqual("ip", vu.get("dataType"))
        self.assertEqual("description for this ip", vu.get("message"))
        self.assertTrue(vu.get("sighted"), "ip:sighted = 1")
        self.assertIsNotNone(vu.get("sightedAt"), "ip:sighted_at was given")
        self.assertTrue(vu.get("ignoreSimilarity"), "ip:ignore_similarity = 1")

        # -- what both alerts share --------------------------------------
        for alerte in alertes:
            champs = champs_personnalises(alerte)
            self.assertEqual("Medium", champs.get("risk"))
            self.assertIsNotNone(champs.get("cert-alerted-on"))
            self.assertEqual(
                {"malicious", "external", "steganography"},
                set(alerte.get("tags") or []),
            )
            self.assertIn(
                "A custom info added to the event",
                alerte.get("description") or "",
                "the Description parameter names the field holding the text",
            )

        self.assert_journal_propre(nom)


if __name__ == "__main__":
    unittest.main()
