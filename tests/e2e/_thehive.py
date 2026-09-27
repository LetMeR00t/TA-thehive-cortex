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


class TheHiveError(RuntimeError):
    pass


class TheHiveClient:
    def __init__(self, base_url, user, password, organisation, verify_tls=False):
        self.base = base_url.rstrip("/")
        self.organisation = organisation
        self._session = requests.Session()
        # The lab certificate is signed by an internal CA that this test host
        # does not necessarily trust. The campaign is not the place to prove
        # the PKI: it is the place to prove the add-on's field mapping.
        self._session.verify = verify_tls
        response = self._session.post(
            f"{self.base}/api/v1/login",
            json={"user": user, "password": password},
            timeout=30,
        )
        if not response.ok:
            raise TheHiveError(f"login refused with HTTP {response.status_code}")

    # -- plumbing ---------------------------------------------------------

    @property
    def _headers(self):
        return {"X-Organisation": self.organisation}

    def _query(self, *operations):
        response = self._session.post(
            f"{self.base}/api/v1/query",
            json={"query": list(operations)},
            headers=self._headers,
            timeout=60,
        )
        if not response.ok:
            raise TheHiveError(
                f"query {operations[0].get('_name')} failed with HTTP {response.status_code}"
            )
        return response.json()

    @staticmethod
    def _page(size=200):
        return {"_name": "page", "from": 0, "to": size}

    # -- reading ----------------------------------------------------------

    @staticmethod
    def _starts_with(prefix):
        return {"_name": "filter", "_startsWith": {"_field": "title", "_value": prefix}}

    def _by_prefix(self, operation, prefix):
        """Objects whose title starts with `prefix`, filtered SERVER-side.

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
            obj
            for obj in self._query(
                {"_name": operation}, self._starts_with(prefix), self._page(500)
            )
            if str(obj.get("title", "")).startswith(prefix)
        ]

    def alerts_by_title_prefix(self, prefix):
        return self._by_prefix("listAlert", prefix)

    def cases_by_title_prefix(self, prefix):
        return self._by_prefix("listCase", prefix)

    def wait_for_alerts(self, prefix, how_many, timeout_s):
        """Poll until `how_many` alerts carry the prefix, or give up.

        ⚠️ Polling, not sleeping. The alert action returns as soon as TheHive
        has accepted the request; the object becomes queryable slightly later.
        A fixed sleep is a coin toss dressed as a test.
        """
        deadline = time.time() + timeout_s
        seen_ones = []
        while time.time() < deadline:
            seen_ones = self.alerts_by_title_prefix(prefix)
            if len(seen_ones) >= how_many:
                return seen_ones
            time.sleep(2)
        return seen_ones

    def wait_for_cases(self, prefix, how_many, timeout_s):
        deadline = time.time() + timeout_s
        seen_set = []
        while time.time() < deadline:
            seen_set = self.cases_by_title_prefix(prefix)
            if len(seen_set) >= how_many:
                return seen_set
            time.sleep(2)
        return seen_set

    def alert_observables(self, alert_id):
        return self._query(
            {"_name": "getAlert", "idOrName": alert_id},
            {"_name": "observables"},
            self._page(500),
        )

    def alert_procedures(self, alert_id):
        """The TTPs. TheHive calls them procedures once attached."""
        return self._query(
            {"_name": "getAlert", "idOrName": alert_id},
            {"_name": "procedures"},
            self._page(500),
        )

    def case_observables(self, case_id):
        return self._query(
            {"_name": "getCase", "idOrName": case_id},
            {"_name": "observables"},
            self._page(500),
        )

    def case_procedures(self, case_id):
        return self._query(
            {"_name": "getCase", "idOrName": case_id},
            {"_name": "procedures"},
            self._page(500),
        )

    def wait_for_alert_observables(self, alert_id, how_many, timeout_s):
        return self._wait(self.alert_observables, alert_id, how_many, timeout_s)

    def wait_for_case_observables(self, case_id, how_many, timeout_s):
        return self._wait(self.case_observables, case_id, how_many, timeout_s)

    @staticmethod
    def _wait(reading, identifier, how_many, timeout_s):
        """Poll until `how_many` items are there, then return what there is.

        ⚠️ The add-on creates the alert or the case FIRST and attaches the
        observables afterwards, one API call each. Measured on UC3: the case
        appeared, the first observable landed one second later and the second
        one a second after that. Reading them the instant the case exists
        makes the campaign report a missing observable that was merely late --
        a flake that looks exactly like the silent loss this campaign was
        written to catch, which is the worst kind.
        """
        deadline = time.time() + timeout_s
        seen_set = []
        while time.time() < deadline:
            seen_set = reading(identifier)
            if len(seen_set) >= how_many:
                return seen_set
            time.sleep(2)
        return seen_set

    def declared_custom_fields(self):
        """name -> type, as TheHive declares them.

        A test that asserts on a custom field it invented proves nothing; this
        is how the campaign checks it is asking for something that exists.
        """
        return {
            field["name"]: field.get("type")
            for field in self._query({"_name": "listCustomField"}, self._page(500))
        }

    # -- demolition -------------------------------------------------------

    def delete_alert(self, alert_id):
        response = self._session.delete(
            f"{self.base}/api/v1/alert/{alert_id}", headers=self._headers, timeout=30
        )
        return response.ok or response.status_code == 404

    def delete_case(self, case_id):
        response = self._session.delete(
            f"{self.base}/api/v1/case/{case_id}", headers=self._headers, timeout=30
        )
        return response.ok or response.status_code == 404

    def delete_by_prefix(self, prefix):
        """Remove every alert and case carrying the prefix. Returns the count.

        Used both by the per-test teardown and by `purge.py`; a cleanup that
        needs a human is not a cleanup.
        """
        erased = 0
        for alert in self.alerts_by_title_prefix(prefix):
            erased += bool(self.delete_alert(alert["_id"]))
        for cases in self.cases_by_title_prefix(prefix):
            erased += bool(self.delete_case(cases["_id"]))
        return erased


def custom_fields(obj):
    """Normalise the customFields of an alert or a case to {name: value}.

    TheHive returns them as a list of dicts whose value key depends on the
    declared type (`value`, or the older per-type keys). Flattening here keeps
    every test from re-deriving the same shape -- and from quietly reading
    `None` because it guessed the wrong key.
    """
    flat = {}
    for field in obj.get("customFields") or []:
        if not isinstance(field, dict):
            continue
        name = field.get("name")
        if name is None:
            continue
        if "value" in field:
            flat[name] = field["value"]
        else:
            for key in ("string", "integer", "float", "boolean", "date", "url"):
                if key in field:
                    flat[name] = field[key]
                    break
    return flat
