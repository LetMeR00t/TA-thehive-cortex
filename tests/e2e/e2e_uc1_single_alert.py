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
from ._case import CampagneE2E
from ._thehive import champs_personnalises

ACTION = "thehive_create_a_new_alert"

#: Verbatim from the documentation, with `{titre}` substituted for the value
#: of `name` so the alert can be identified. Everything else is unchanged.
RECHERCHE = """| makeresults
| eval ip="1.2.3.4", fqdn="fake-website.com"
| table ip, fqdn
| append
    [| makeresults
| eval hash="a27fa23e7316cb8fb7a57bd11664f2ff"
| table hash]
| eval name = "{titre}", cert-alerted-on=now(), risk="Medium", ttp="defense-evasion::T1027.003::"+tostring(strftime(now(),"%Y-%m-%d"))
| eval unique = "{unique}"
"""


class TestUC1UneSeuleAlerte(CampagneE2E):

    def test_l_alerte_arrive_avec_tout_son_contenu(self):
        titre = f"{self.prefixe} T1027.003 - Obfuscated Files or Information: Steganography"
        recherche = RECHERCHE.format(titre=titre, unique=f"{self.prefixe}_uc1")

        nom = self.jouer(
            "uc1",
            recherche,
            ACTION,
            {
                "thehive_instance_id": self.nom_instance,
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

        alertes = self.thehive.attendre_alertes(self.prefixe, 1, _config.DELAI_THEHIVE)
        self.assertEqual(1, len(alertes), "exactly one alert should have been created")
        alerte = alertes[0]

        # -- the envelope ------------------------------------------------
        self.assertEqual(titre, alerte.get("title"))
        self.assertEqual("alert", alerte.get("type"))
        self.assertEqual("splunk", alerte.get("source"))
        self.assertEqual(2, alerte.get("severity"), "Medium")
        self.assertEqual(2, alerte.get("tlp"), "AMBER")
        self.assertEqual(2, alerte.get("pap"), "AMBER")
        self.assertIn("e2e", alerte.get("tags") or [])

        # -- the observables: value AND type -----------------------------
        # ⚠️ Checking only the values would let a whole class of defect
        # through: an observable that arrives as `other` is present, visible,
        # and useless -- no analyzer will ever run on it.
        observables = {
            (obs.get("data"), obs.get("dataType"))
            for obs in self.thehive.attendre_observables_de_l_alerte(
                alerte["_id"], 3, _config.DELAI_THEHIVE
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
        champs = champs_personnalises(alerte)
        self.assertEqual("Medium", champs.get("risk"),
                         "a string custom field must survive the trip")
        self.assertIsNotNone(champs.get("cert-alerted-on"),
                             "a date custom field must survive the trip")
        # ⚠️ Measured, and deliberately NOT asserted as a custom field: `name`
        # is what the `title` parameter names, and a field consumed as the
        # title is not mapped a second time -- even though TheHive declares a
        # custom field of the same name. Asserting the opposite would be the
        # test inventing a requirement the add-on never claimed.
        self.assertNotIn("name", champs, "documented behaviour: the title source is consumed")

        # -- the TTP ------------------------------------------------------
        procedures = self.thehive.procedures_de_l_alerte(alerte["_id"])
        self.assertEqual(1, len(procedures), "one TTP was sent, one must arrive")
        self.assertEqual("T1027.003", procedures[0].get("patternId"))

        # -- and Splunk's own account of it ------------------------------
        self.assert_journal_propre(nom)


if __name__ == "__main__":
    unittest.main()
