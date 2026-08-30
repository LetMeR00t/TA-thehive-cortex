"""The Splunk side of the campaign: build the configuration, fire it, tear it down.

Everything created here carries the run prefix, so the teardown can be total
and still be safe: it deletes what matches the prefix and nothing else. That
is also what lets two runs share an instance without stealing each other's
objects.
"""

import time
import xml.etree.ElementTree as ET

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_ATOM = "{http://www.w3.org/2005/Atom}"
_SPL = "{http://dev.splunk.com/ns/rest}"


class ErreurSplunk(RuntimeError):
    pass


class ClientSplunk:
    def __init__(self, mgmt_url, utilisateur, mot_de_passe, app):
        self.base = mgmt_url.rstrip("/")
        self.app = app
        self._session = requests.Session()
        self._session.verify = False
        self._session.auth = (utilisateur, mot_de_passe)

    # -- plumbing ---------------------------------------------------------

    def _ns(self, chemin):
        return f"{self.base}/servicesNS/nobody/{self.app}/{chemin}"

    def _appel(self, methode, url, **kwargs):
        kwargs.setdefault("timeout", 60)
        params = kwargs.setdefault("params", {})
        params.setdefault("output_mode", "json")
        reponse = self._session.request(methode, url, **kwargs)
        if not reponse.ok:
            # The body carries Splunk's own explanation; it never contains a
            # credential, only the object and the reason.
            raise ErreurSplunk(
                f"{methode} {url.rsplit('/', 1)[-1]} -> HTTP {reponse.status_code}: "
                f"{reponse.text[:300]}"
            )
        return reponse

    # -- add-on configuration --------------------------------------------

    def creer_compte(self, nom, utilisateur, mot_de_passe):
        self._appel(
            "POST",
            self._ns("thehive_cortex_accounts"),
            data={"name": nom, "username": utilisateur, "password": mot_de_passe},
        )

    def supprimer_compte(self, nom):
        self._supprimer_silencieux(self._ns(f"thehive_cortex_accounts/{nom}"))

    def lire_instance(self, nom):
        reponse = self._appel("GET", self._ns(f"thehive_cortex_instances/{nom}"))
        entrees = reponse.json().get("entry") or []
        if not entrees:
            raise ErreurSplunk(f"instance {nom!r} does not exist")
        return entrees[0]["content"]

    def creer_instance(self, nom, modele, compte, authentification="password"):
        """Clone an existing instance's target, but point it at our account.

        Copying the template rather than declaring a host is what keeps this
        file free of anybody's URL: the run necessarily talks to the TheHive
        the operator already configured.
        """
        champs = {
            "name": nom,
            "account_name": compte,
            "authentication_type": authentification,
            "type": modele.get("type", "TheHive5"),
            "environment": modele.get("environment", "DEVELOPMENT"),
            "host": modele["host"],
            "port": modele.get("port", "443"),
            "uri": modele.get("uri", "/"),
            "organisation": modele.get("organisation", ""),
            "proxy_url": modele.get("proxy_url", "-"),
            "client_cert": modele.get("client_cert", "-"),
            "ca_cert_path": modele.get("ca_cert_path", "-"),
        }
        self._appel("POST", self._ns("thehive_cortex_instances"), data=champs)

    def supprimer_instance(self, nom):
        self._supprimer_silencieux(self._ns(f"thehive_cortex_instances/{nom}"))

    # -- saved searches ---------------------------------------------------

    def creer_recherche_sauvegardee(self, nom, recherche, action, parametres):
        """A scheduled saved search carrying one alert action.

        ⚠️ It is scheduled on purpose. Alert actions belong to the scheduler:
        an ad-hoc `| sendalert` would exercise a different path from the one
        UC1 and UC2 describe, and it is the described path that ships.
        """
        donnees = {
            "name": nom,
            "search": recherche,
            "is_scheduled": "1",
            # Far enough in the future that the scheduler never fires it on its
            # own: the test decides when it runs, and cleans up right after.
            "cron_schedule": "0 5 31 2 *",
            "dispatch.earliest_time": "-5m",
            "dispatch.latest_time": "now",
            "alert_type": "always",
            "alert.track": "0",
            # ⚠️ Without an explicit TTL the dispatch directory of a manually
            # triggered saved search is reaped before the alert action opens
            # it, and the action reports "No search result" -- an IOError on
            # results.csv.gz, described as an empty search. The job really did
            # return its rows; the evidence was simply deleted first.
            "dispatch.ttl": "600",
            "actions": action,
        }
        for cle, valeur in parametres.items():
            donnees[f"action.{action}.param.{cle}"] = valeur
        self._appel("POST", self._ns("saved/searches"), data=donnees)

    def supprimer_recherche_sauvegardee(self, nom):
        self._supprimer_silencieux(self._ns(f"saved/searches/{nom}"))

    def declencher(self, nom):
        """Dispatch the saved search AND its actions, and return the sid.

        `trigger_actions=1` is the whole point: without it Splunk runs the
        search and skips the alert action, which would make this campaign an
        elaborate way of proving that `makeresults` works.
        """
        reponse = self._appel(
            "POST",
            self._ns(f"saved/searches/{nom}/dispatch"),
            data={"trigger_actions": "1", "dispatch.now": str(int(time.time()))},
        )
        return reponse.json()["sid"]

    def attendre_le_job(self, sid, delai):
        """Poll the job until it is done. Returns its final state."""
        limite = time.time() + delai
        while time.time() < limite:
            reponse = self._session.get(
                f"{self.base}/services/search/jobs/{sid}",
                params={"output_mode": "json"},
                timeout=30,
                verify=False,
            )
            if reponse.ok:
                contenu = reponse.json()["entry"][0]["content"]
                if contenu.get("isDone"):
                    return contenu
            time.sleep(2)
        raise ErreurSplunk(f"job did not finish within {delai}s")

    # -- the collection side ----------------------------------------------

    def creer_index(self, nom):
        """A throwaway index for the return trip.

        ⚠️ Indexed events cannot be deleted. Sending the collected data into
        the operator's own `thehive` index would leave rows behind that no
        teardown could remove, so the campaign gives itself an index and drops
        the whole thing afterwards -- data included.
        """
        self._appel(
            "POST", f"{self.base}/services/data/indexes", data={"name": nom}
        )

    def supprimer_index(self, nom):
        self._supprimer_silencieux(f"{self.base}/services/data/indexes/{nom}")

    def creer_input_collecte(self, nom, modele, instance, index, intervalle="60"):
        """A modular input pulling alerts and cases back from TheHive."""
        champs = {
            "name": nom,
            "instance_id": instance,
            "index": index,
            "interval": intervalle,
            "type": modele.get("type", "alerts,cases"),
            "date": modele.get("date", "_createdAt,_updatedAt,date,startDate"),
            "additional_information": modele.get("additional_information", ""),
            "extra_data": modele.get("extra_data", ""),
            "max_size_value": modele.get("max_size_value", "1000"),
        }
        self._appel(
            "POST", self._ns("thehive_cortex_thehive_alerts_cases"), data=champs
        )

    def lire_input_collecte(self, nom):
        reponse = self._appel(
            "GET", self._ns(f"thehive_cortex_thehive_alerts_cases/{nom}")
        )
        entrees = reponse.json().get("entry") or []
        if not entrees:
            raise ErreurSplunk(f"input {nom!r} does not exist")
        return entrees[0]["content"]

    def supprimer_input_collecte(self, nom):
        self._supprimer_silencieux(
            self._ns(f"thehive_cortex_thehive_alerts_cases/{nom}")
        )

    def inputs_collecte_par_prefixe(self, prefixe):
        return self._noms_par_prefixe("thehive_cortex_thehive_alerts_cases", prefixe)

    def index_par_prefixe(self, prefixe):
        reponse = self._appel(
            "GET", f"{self.base}/services/data/indexes",
            params={"output_mode": "json", "count": "0"},
        )
        return [
            entree["name"]
            for entree in reponse.json().get("entry", [])
            if entree["name"].startswith(prefixe)
        ]

    # -- searching --------------------------------------------------------

    def rechercher(self, spl, delai=120, earliest="-15m", latest="now"):
        """Run a one-shot search and return its rows as dictionaries."""
        reponse = self._appel(
            "POST",
            f"{self.base}/services/search/jobs/export",
            data={
                "search": spl,
                "earliest_time": earliest,
                "latest_time": latest,
                "output_mode": "json",
                "exec_mode": "oneshot",
            },
            timeout=delai,
            stream=False,
        )
        lignes = []
        for ligne in reponse.text.splitlines():
            ligne = ligne.strip()
            if not ligne:
                continue
            try:
                objet = __import__("json").loads(ligne)
            except ValueError:
                continue
            if "result" in objet:
                lignes.append(objet["result"])
        return lignes

    def journal_de_l_action(self, nom_recherche, depuis="-15m"):
        """The alert action's own log lines for one saved search.

        ⚠️ It reads `index=cim_modactions`, not `_internal`. Splunk_SA_CIM
        applies index-time TRANSFORMS to `*_modalert.log` that force the index
        AND the sourcetype; on any instance carrying CIM -- every ES
        deployment -- the add-on's own props.conf never gets a say.
        """
        spl = (
            'search index=cim_modactions source="*_modalert.log*" '
            f'"{nom_recherche}" | table _time, _raw'
        )
        return self._rechercher_brut(spl, depuis)

    def _rechercher_brut(self, spl, depuis):
        return [ligne.get("_raw", "") for ligne in self.rechercher(spl, earliest=depuis)]

    # -- demolition -------------------------------------------------------

    def _supprimer_silencieux(self, url):
        try:
            self._session.delete(url, params={"output_mode": "json"}, timeout=60, verify=False)
        except requests.RequestException:
            # Teardown must not raise: it runs in a `finally`, and an
            # exception here would replace the real assertion failure with a
            # cleanup error, which is how a test lies about what broke.
            pass

    def recherches_par_prefixe(self, prefixe):
        reponse = self._appel(
            "GET", self._ns("saved/searches"), params={"output_mode": "json", "count": "0"}
        )
        return [
            entree["name"]
            for entree in reponse.json().get("entry", [])
            if entree["name"].startswith(prefixe)
        ]

    def instances_par_prefixe(self, prefixe):
        return self._noms_par_prefixe("thehive_cortex_instances", prefixe)

    def comptes_par_prefixe(self, prefixe):
        return self._noms_par_prefixe("thehive_cortex_accounts", prefixe)

    def _noms_par_prefixe(self, endpoint, prefixe):
        reponse = self._appel(
            "GET", self._ns(endpoint), params={"output_mode": "json", "count": "0"}
        )
        return [
            entree["name"]
            for entree in reponse.json().get("entry", [])
            if entree["name"].startswith(prefixe)
        ]
