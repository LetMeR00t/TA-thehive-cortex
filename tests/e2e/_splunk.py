"""The Splunk side of the campaign: build the configuration, fire it, tear it down.

Everything created here carries the run prefix, so the teardown can be total
and still be safe: it deletes what matches the prefix and nothing else. That
is also what lets two runs share an instance without stealing each other's
objects.
"""

import re
import time
import xml.etree.ElementTree as ET

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_ATOM = "{http://www.w3.org/2005/Atom}"
_SPL = "{http://dev.splunk.com/ns/rest}"


class SplunkError(RuntimeError):
    pass


class SplunkClient:
    def __init__(self, mgmt_url, user, password, app):
        self.base = mgmt_url.rstrip("/")
        self.app = app
        self._session = requests.Session()
        self._session.verify = False
        self._session.auth = (user, password)

    # -- plumbing ---------------------------------------------------------

    def _ns(self, file_path):
        return f"{self.base}/servicesNS/nobody/{self.app}/{file_path}"

    def _call(self, method, url, **kwargs):
        kwargs.setdefault("timeout", 60)
        params = kwargs.setdefault("params", {})
        params.setdefault("output_mode", "json")
        response = self._session.request(method, url, **kwargs)
        if not response.ok:
            # The body carries Splunk's own explanation; it never contains a
            # credential, only the object and the reason.
            raise SplunkError(
                f"{method} {url.rsplit('/', 1)[-1]} -> HTTP {response.status_code}: "
                f"{response.text[:300]}"
            )
        return response

    # -- add-on configuration --------------------------------------------

    def create_account(self, name, user, password):
        self._call(
            "POST",
            self._ns("thehive_cortex_accounts"),
            data={"name": name, "username": user, "password": password},
        )

    def delete_account(self, name):
        self._delete_quietly(self._ns(f"thehive_cortex_accounts/{name}"))

    def read_instance(self, name):
        response = self._call("GET", self._ns(f"thehive_cortex_instances/{name}"))
        entries = response.json().get("entry") or []
        if not entries:
            raise SplunkError(f"instance {name!r} does not exist")
        return entries[0]["content"]

    def create_instance(self, name, template, account, authentication="password"):
        """Clone an existing instance's target, but point it at our account.

        Copying the template rather than declaring a host is what keeps this
        file free of anybody's URL: the run necessarily talks to the TheHive
        the operator already configured.
        """
        fields = {
            "name": name,
            "account_name": account,
            "authentication_type": authentication,
            "type": template.get("type", "TheHive5"),
            "environment": template.get("environment", "DEVELOPMENT"),
            "host": template["host"],
            "port": template.get("port", "443"),
            "uri": template.get("uri", "/"),
            "organisation": template.get("organisation", ""),
            "proxy_url": template.get("proxy_url", "-"),
            "client_cert": template.get("client_cert", "-"),
            "ca_cert_path": template.get("ca_cert_path", "-"),
        }
        self._call("POST", self._ns("thehive_cortex_instances"), data=fields)

    def delete_instance(self, name):
        self._delete_quietly(self._ns(f"thehive_cortex_instances/{name}"))

    # -- saved searches ---------------------------------------------------

    def create_saved_search(self, name, search, action, parameters):
        """A scheduled saved search carrying one alert action.

        ⚠️ It is scheduled on purpose. Alert actions belong to the scheduler:
        an ad-hoc `| sendalert` would exercise a different path from the one
        UC1 and UC2 describe, and it is the described path that ships.
        """
        payload = {
            "name": name,
            "search": search,
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
        for key, value in parameters.items():
            payload[f"action.{action}.param.{key}"] = value
        self._call("POST", self._ns("saved/searches"), data=payload)

    def delete_saved_search(self, name):
        self._delete_quietly(self._ns(f"saved/searches/{name}"))

    def dispatch(self, name):
        """Dispatch the saved search AND its actions, and return the sid.

        `trigger_actions=1` is the whole point: without it Splunk runs the
        search and skips the alert action, which would make this campaign an
        elaborate way of proving that `makeresults` works.
        """
        response = self._call(
            "POST",
            self._ns(f"saved/searches/{name}/dispatch"),
            data={"trigger_actions": "1", "dispatch.now": str(int(time.time()))},
        )
        return response.json()["sid"]

    def wait_for_job(self, sid, timeout_s):
        """Poll the job until it is done. Returns its final state."""
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            response = self._session.get(
                f"{self.base}/services/search/jobs/{sid}",
                params={"output_mode": "json"},
                timeout=30,
                verify=False,
            )
            if response.ok:
                content = response.json()["entry"][0]["content"]
                if content.get("isDone"):
                    return content
            time.sleep(2)
        raise SplunkError(f"job did not finish within {timeout_s}s")

    # -- the collection side ----------------------------------------------

    def create_index(self, name):
        """A throwaway index for the return trip.

        ⚠️ Indexed events cannot be deleted. Sending the collected data into
        the operator's own `thehive` index would leave rows behind that no
        teardown could remove, so the campaign gives itself an index and drops
        the whole thing afterwards -- data included.
        """
        self._call(
            "POST", f"{self.base}/services/data/indexes", data={"name": name}
        )

    def delete_index(self, name):
        self._delete_quietly(f"{self.base}/services/data/indexes/{name}")

    def create_collection_input(self, name, template, instance, index, interval="60"):
        """A modular input pulling alerts and cases back from TheHive."""
        fields = {
            "name": name,
            "instance_id": instance,
            "index": index,
            "interval": interval,
            "type": template.get("type", "alerts,cases"),
            "date": template.get("date", "_createdAt,_updatedAt,date,startDate"),
            "additional_information": template.get("additional_information", ""),
            "extra_data": template.get("extra_data", ""),
            "max_size_value": template.get("max_size_value", "1000"),
        }
        self._call(
            "POST", self._ns("thehive_cortex_thehive_alerts_cases"), data=fields
        )

    def read_collection_input(self, name):
        response = self._call(
            "GET", self._ns(f"thehive_cortex_thehive_alerts_cases/{name}")
        )
        entries = response.json().get("entry") or []
        if not entries:
            raise SplunkError(f"input {name!r} does not exist")
        return entries[0]["content"]

    def delete_collection_input(self, name):
        self._delete_quietly(
            self._ns(f"thehive_cortex_thehive_alerts_cases/{name}")
        )

    def collection_inputs_by_prefix(self, prefix):
        return self._names_by_prefix("thehive_cortex_thehive_alerts_cases", prefix)

    def indexes_by_prefix(self, prefix):
        response = self._call(
            "GET", f"{self.base}/services/data/indexes",
            params={"output_mode": "json", "count": "0"},
        )
        return [
            entry["name"]
            for entry in response.json().get("entry", [])
            if entry["name"].startswith(prefix)
        ]

    # -- searching --------------------------------------------------------

    def search_events(self, spl, timeout_s=120, earliest="-15m", latest="now"):
        """Run a one-shot search and return its rows as dictionaries."""
        response = self._call(
            "POST",
            f"{self.base}/services/search/jobs/export",
            data={
                "search": spl,
                "earliest_time": earliest,
                "latest_time": latest,
                "output_mode": "json",
                "exec_mode": "oneshot",
            },
            timeout=timeout_s,
            stream=False,
        )
        rows = []
        for row in response.text.splitlines():
            row = row.strip()
            if not row:
                continue
            try:
                obj = __import__("json").loads(row)
            except ValueError:
                continue
            if "result" in obj:
                rows.append(obj["result"])
        return rows

    def action_log(self, search_name, since="-15m"):
        """The alert action's own log lines for one saved search.

        ⚠️ It reads `index=cim_modactions`, not `_internal`. Splunk_SA_CIM
        applies index-time TRANSFORMS to `*_modalert.log` that force the index
        AND the sourcetype; on any instance carrying CIM -- every ES
        deployment -- the add-on's own props.conf never gets a say.

        ⚠️ Filtering on the search name alone returns only the FRAMEWORK's
        lines ("Initializing modaction. search_name=... pid=N"): the add-on's
        own lines -- its errors included -- carry an exec_id and the pid, never
        the search name. Measured on 2026-09-27 (#38): `THCA-TH110-ERROR` was
        in the log, and `assert_clean_log` saw nothing, in every case of the
        campaign. So the lines naming the search only give the run's pid(s);
        every line of those pids is then read.
        """
        base = 'search index=cim_modactions source="*_modalert.log*" '
        named = self._raw_search(f'{base}"{search_name}" | table _time, _raw', since)
        pids = sorted(set(re.findall(r"\bpid=(\d+)", " ".join(named))))
        if not pids:
            return named
        terms = " OR ".join(f'"pid={pid}"' for pid in pids)
        return self._raw_search(f"{base}({terms}) | table _time, _raw", since)

    def _raw_search(self, spl, since):
        return [row.get("_raw", "") for row in self.search_events(spl, earliest=since)]

    # -- demolition -------------------------------------------------------

    def _delete_quietly(self, url):
        try:
            self._session.delete(url, params={"output_mode": "json"}, timeout=60, verify=False)
        except requests.RequestException:
            # Teardown must not raise: it runs in a `finally`, and an
            # exception here would replace the real assertion failure with a
            # cleanup error, which is how a test lies about what broke.
            pass

    def searches_by_prefix(self, prefix):
        response = self._call(
            "GET", self._ns("saved/searches"), params={"output_mode": "json", "count": "0"}
        )
        return [
            entry["name"]
            for entry in response.json().get("entry", [])
            if entry["name"].startswith(prefix)
        ]

    def instances_by_prefix(self, prefix):
        return self._names_by_prefix("thehive_cortex_instances", prefix)

    def accounts_by_prefix(self, prefix):
        return self._names_by_prefix("thehive_cortex_accounts", prefix)

    def _names_by_prefix(self, endpoint, prefix):
        response = self._call(
            "GET", self._ns(endpoint), params={"output_mode": "json", "count": "0"}
        )
        return [
            entry["name"]
            for entry in response.json().get("entry", [])
            if entry["name"].startswith(prefix)
        ]
