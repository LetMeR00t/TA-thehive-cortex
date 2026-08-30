"""The shared arrangement and, above all, the demolition.

Every object this campaign creates -- Splunk account, instance, saved search,
and the TheHive alerts and cases the action produces -- carries the same
`e2e-<runid>` prefix. Two consequences, both deliberate:

* two runs can happen at once without stealing each other's objects;
* the cleanup can be **total and safe**, because it removes exactly what
  matches the prefix and can never reach anything else.

⚠️ The teardown runs in `tearDown`/`tearDownClass`, so it happens **after a
failed assertion too**. A campaign that only cleans up when it passes leaves
its worst days behind in production.
"""

import os
import unittest
import uuid

from . import _config
from ._splunk import ClientSplunk
from ._thehive import ClientTheHive

#: ⚠️ Underscore, not hyphen. The add-on's REST handlers validate account and
#: instance names against `^[a-zA-Z]\w*$`: a hyphen is rejected with a 400 that
#: names a pattern and not the field. One prefix for every object, on both
#: sides, is what makes the cleanup provably total.
PREFIXE = "e2e_"


def nouvel_identifiant():
    """Short, unique, and readable in a TheHive list without scrolling."""
    return uuid.uuid4().hex[:8]


@unittest.skipIf(*_config.SAUT)
class CampagneE2E(unittest.TestCase):
    """Base class: builds the configuration once, destroys everything after."""

    #: Overridden by the tests that need the alert action to see a specific
    #: organisation; by default the template instance's own.
    organisation = None

    @classmethod
    def setUpClass(cls):
        cls.runid = nouvel_identifiant()
        cls.prefixe = f"{PREFIXE}{cls.runid}"

        cls.splunk = ClientSplunk(
            _config.SPLUNK_MGMT,
            _config.valeur("SPLUNK_USER"),
            _config.valeur("SPLUNK_PASSWORD"),
            _config.APP,
        )

        modele = cls.splunk.lire_instance(_config.valeur("E2E_TEMPLATE_INSTANCE"))
        cls.organisation = cls.organisation or modele.get("organisation")

        # ⚠️ The run creates its own INSTANCE but reuses the template's
        # ACCOUNT. Two measured reasons, both worth keeping written down:
        #
        # * the add-on's `password` authentication mode sends HTTP Basic, and
        #   this TheHive 5 answers 401 to Basic on /api/v1 while accepting
        #   /api/v1/login -- an account built from THEHIVE_USER/PASSWORD gets
        #   THCA-TH110 "AuthenticationError" and no alert is ever created;
        # * reusing the configured account means the campaign never writes a
        #   human's password into Splunk's credential store, which is exactly
        #   the kind of leftover a cleanup can fail to remove.
        #
        # THEHIVE_USER/PASSWORD are still required: they authenticate the
        # VERIFICATION client, which must reach TheHive independently of the
        # add-on to be worth anything.
        cls.nom_instance = f"{cls.prefixe}_instance"
        cls._objets_splunk = []

        cls.splunk.creer_instance(cls.nom_instance, modele, modele.get("account_name"),
                                  modele.get("authentication_type", "api_key"))
        cls._objets_splunk.append(("instance", cls.nom_instance))

        schema = "https" if str(modele.get("port")) == "443" else "http"
        base = f"{schema}://{modele['host']}:{modele.get('port', '443')}"
        cls.thehive = ClientTheHive(
            base,
            _config.valeur("THEHIVE_USER"),
            _config.valeur("THEHIVE_PASSWORD"),
            cls.organisation,
        )

    @classmethod
    def tearDownClass(cls):
        for genre, nom in reversed(getattr(cls, "_objets_splunk", [])):
            if genre == "instance":
                cls.splunk.supprimer_instance(nom)
            elif genre == "compte":
                cls.splunk.supprimer_compte(nom)

    def setUp(self):
        self._recherches = []

    def tearDown(self):
        for nom in self._recherches:
            self.splunk.supprimer_recherche_sauvegardee(nom)
        # TheHive last: if deleting an alert fails we still want the Splunk
        # side gone, otherwise the next run inherits a scheduled search.
        self.thehive.supprimer_par_prefixe(self.prefixe)

    # -- helpers used by the use cases ------------------------------------

    def jouer(self, suffixe, recherche, action, parametres):
        """Create the saved search, fire it with its action, wait for the job."""
        nom = f"{self.prefixe}_{suffixe}"
        self.splunk.creer_recherche_sauvegardee(nom, recherche, action, parametres)
        self._recherches.append(nom)
        sid = self.splunk.declencher(nom)
        etat = self.splunk.attendre_le_job(sid, _config.DELAI_JOB)
        self.assertNotEqual(
            "FAILED",
            etat.get("dispatchState"),
            "the saved search itself failed before the alert action could run",
        )
        return nom

    def assert_journal_propre(self, nom_recherche, tolere=()):
        """No ERROR, and no silent-loss warning, unless the case expects one.

        ⚠️ This is half of what makes the campaign worth running. The defects
        that hurt here do not fail: they log a warning and return success. A
        test that only checks TheHive would miss the ones where TheHive was
        never told, and a test that only checks Splunk would miss the ones
        where Splunk was told and got it wrong.
        """
        lignes = self.splunk.journal_de_l_action(nom_recherche)
        fautives = [
            ligne
            for ligne in lignes
            if ("ERROR" in ligne or "THC-117" in ligne)
            and not any(code in ligne for code in tolere)
        ]
        self.assertEqual(
            [],
            [ligne[:200] for ligne in fautives],
            "the alert action logged an error or a silent-loss warning",
        )
