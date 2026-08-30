"""A thin TheHive 5 client, used to check what TheHive REALLY received.

⚠️ It deliberately does NOT go through the add-on's own code. Reading back
with `thehivealerts` would ask the write path and the read path to agree with
each other, which they can do while both being wrong. The defects this
campaign exists to catch -- a custom field silently dropped, an observable
that arrives with the wrong type -- are exactly the ones a self-consistent
round-trip cannot see.

Nothing here prints a credential, an id or a payload: assertions are written
against counts and names, and the session cookie never leaves the object.
"""

import time

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class ErreurTheHive(RuntimeError):
    pass


class ClientTheHive:
    def __init__(self, base_url, utilisateur, mot_de_passe, organisation, verifier_tls=False):
        self.base = base_url.rstrip("/")
        self.organisation = organisation
        self._session = requests.Session()
        # The lab certificate is signed by an internal CA that this test host
        # does not necessarily trust. The campaign is not the place to prove
        # the PKI: it is the place to prove the add-on's field mapping.
        self._session.verify = verifier_tls
        reponse = self._session.post(
            f"{self.base}/api/v1/login",
            json={"user": utilisateur, "password": mot_de_passe},
            timeout=30,
        )
        if not reponse.ok:
            raise ErreurTheHive(f"login refused with HTTP {reponse.status_code}")

    # -- plumbing ---------------------------------------------------------

    @property
    def _entetes(self):
        return {"X-Organisation": self.organisation}

    def _query(self, *operations):
        reponse = self._session.post(
            f"{self.base}/api/v1/query",
            json={"query": list(operations)},
            headers=self._entetes,
            timeout=60,
        )
        if not reponse.ok:
            raise ErreurTheHive(
                f"query {operations[0].get('_name')} failed with HTTP {reponse.status_code}"
            )
        return reponse.json()

    @staticmethod
    def _page(taille=200):
        return {"_name": "page", "from": 0, "to": taille}

    # -- reading ----------------------------------------------------------

    @staticmethod
    def _commence_par(prefixe):
        return {"_name": "filter", "_startsWith": {"_field": "title", "_value": prefixe}}

    def _par_prefixe(self, operation, prefixe):
        """Objects whose title starts with `prefixe`, filtered SERVER-side.

        ⚠️ The filter is not an optimisation. Listing and filtering in Python
        looked identical on alerts and quietly failed on cases: this
        organisation holds more than 3 600 of them, `listCase` does not
        promise the newest first, and a page of 500 simply did not contain the
        case that had just been created. The campaign reported "no case" about
        a case the log said it had created -- and then failed to clean it up,
        because the cleanup used the same blind listing.

        The campaign also never searches by "the most recent": two runs in
        parallel would steal each other's objects.
        """
        return [
            objet
            for objet in self._query(
                {"_name": operation}, self._commence_par(prefixe), self._page(500)
            )
            if str(objet.get("title", "")).startswith(prefixe)
        ]

    def alertes_par_prefixe_de_titre(self, prefixe):
        return self._par_prefixe("listAlert", prefixe)

    def cas_par_prefixe_de_titre(self, prefixe):
        return self._par_prefixe("listCase", prefixe)

    def attendre_alertes(self, prefixe, combien, delai):
        """Poll until `combien` alerts carry the prefix, or give up.

        ⚠️ Polling, not sleeping. The alert action returns as soon as TheHive
        has accepted the request; the object becomes queryable slightly later.
        A fixed sleep is a coin toss dressed as a test.
        """
        limite = time.time() + delai
        vues = []
        while time.time() < limite:
            vues = self.alertes_par_prefixe_de_titre(prefixe)
            if len(vues) >= combien:
                return vues
            time.sleep(2)
        return vues

    def attendre_cas(self, prefixe, combien, delai):
        limite = time.time() + delai
        vus = []
        while time.time() < limite:
            vus = self.cas_par_prefixe_de_titre(prefixe)
            if len(vus) >= combien:
                return vus
            time.sleep(2)
        return vus

    def observables_de_l_alerte(self, alerte_id):
        return self._query(
            {"_name": "getAlert", "idOrName": alerte_id},
            {"_name": "observables"},
            self._page(500),
        )

    def procedures_de_l_alerte(self, alerte_id):
        """The TTPs. TheHive calls them procedures once attached."""
        return self._query(
            {"_name": "getAlert", "idOrName": alerte_id},
            {"_name": "procedures"},
            self._page(500),
        )

    def observables_du_cas(self, cas_id):
        return self._query(
            {"_name": "getCase", "idOrName": cas_id},
            {"_name": "observables"},
            self._page(500),
        )

    def procedures_du_cas(self, cas_id):
        return self._query(
            {"_name": "getCase", "idOrName": cas_id},
            {"_name": "procedures"},
            self._page(500),
        )

    def attendre_observables_de_l_alerte(self, alerte_id, combien, delai):
        return self._attendre(self.observables_de_l_alerte, alerte_id, combien, delai)

    def attendre_observables_du_cas(self, cas_id, combien, delai):
        return self._attendre(self.observables_du_cas, cas_id, combien, delai)

    @staticmethod
    def _attendre(lecture, identifiant, combien, delai):
        """Poll until `combien` items are there, then return what there is.

        ⚠️ The add-on creates the alert or the case FIRST and attaches the
        observables afterwards, one API call each. Measured on UC3: the case
        appeared, the first observable landed one second later and the second
        one a second after that. Reading them the instant the case exists
        makes the campaign report a missing observable that was merely late --
        a flake that looks exactly like the silent loss this campaign was
        written to catch, which is the worst kind.
        """
        limite = time.time() + delai
        vus = []
        while time.time() < limite:
            vus = lecture(identifiant)
            if len(vus) >= combien:
                return vus
            time.sleep(2)
        return vus

    def champs_personnalises_declares(self):
        """name -> type, as TheHive declares them.

        A test that asserts on a custom field it invented proves nothing; this
        is how the campaign checks it is asking for something that exists.
        """
        return {
            champ["name"]: champ.get("type")
            for champ in self._query({"_name": "listCustomField"}, self._page(500))
        }

    # -- demolition -------------------------------------------------------

    def supprimer_alerte(self, alerte_id):
        reponse = self._session.delete(
            f"{self.base}/api/v1/alert/{alerte_id}", headers=self._entetes, timeout=30
        )
        return reponse.ok or reponse.status_code == 404

    def supprimer_cas(self, cas_id):
        reponse = self._session.delete(
            f"{self.base}/api/v1/case/{cas_id}", headers=self._entetes, timeout=30
        )
        return reponse.ok or reponse.status_code == 404

    def supprimer_par_prefixe(self, prefixe):
        """Remove every alert and case carrying the prefix. Returns the count.

        Used both by the per-test teardown and by `purge.py`; a cleanup that
        needs a human is not a cleanup.
        """
        efface = 0
        for alerte in self.alertes_par_prefixe_de_titre(prefixe):
            efface += bool(self.supprimer_alerte(alerte["_id"]))
        for cas in self.cas_par_prefixe_de_titre(prefixe):
            efface += bool(self.supprimer_cas(cas["_id"]))
        return efface


def champs_personnalises(objet):
    """Normalise the customFields of an alert or a case to {name: value}.

    TheHive returns them as a list of dicts whose value key depends on the
    declared type (`value`, or the older per-type keys). Flattening here keeps
    every test from re-deriving the same shape -- and from quietly reading
    `None` because it guessed the wrong key.
    """
    plat = {}
    for champ in objet.get("customFields") or []:
        if not isinstance(champ, dict):
            continue
        nom = champ.get("name")
        if nom is None:
            continue
        if "value" in champ:
            plat[nom] = champ["value"]
        else:
            for cle in ("string", "integer", "float", "boolean", "date", "url"):
                if cle in champ:
                    plat[nom] = champ[cle]
                    break
    return plat
