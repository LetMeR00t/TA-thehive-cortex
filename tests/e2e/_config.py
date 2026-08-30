"""What the end-to-end campaign needs, and how it refuses to run without it.

⚠️ This suite talks to a REAL Splunk and a REAL TheHive, and it CREATES then
DELETES objects in both. It must therefore be impossible to run by accident:
every setting comes from the environment (or from a local, unversioned
`.env` next to this file), and **nothing here carries a default that would
point at somebody's instance**. A fallback URL is how a test suite ends up
writing into a colleague's production.

The one value derived rather than declared is the TheHive host: it is read
from the add-on instance the run targets, so the test necessarily speaks to
the same TheHive the configuration under test speaks to. That is not a
default, it is a measurement.

Missing configuration means **skip**, never `sys.exit`. A suite that kills the
interpreter hides every test after it.
"""

import os
import unittest

#: Read once. `.env` never overrides a value already present in the real
#: environment: the shell wins, so a run can be redirected without editing a
#: file that someone else may also be using.
_ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")


def _charger_env_local():
    if not os.path.isfile(_ENV_FILE):
        return
    with open(_ENV_FILE, encoding="utf-8") as fh:
        for ligne in fh:
            ligne = ligne.strip()
            if not ligne or ligne.startswith("#") or "=" not in ligne:
                continue
            cle, _, valeur = ligne.partition("=")
            cle = cle.strip()
            valeur = valeur.strip().strip('"').strip("'")
            os.environ.setdefault(cle, valeur)


_charger_env_local()


#: Everything the campaign needs, and what each one is for. Keep the list here
#: rather than scattered across the tests: `manque()` below is what decides
#: whether the suite runs at all, and it can only be honest if it is complete.
REQUIS = {
    "SPLUNK_USER": "Splunk account able to create saved searches and add-on configuration",
    "SPLUNK_PASSWORD": "its password",
    "THEHIVE_USER": "TheHive account the test authenticates as",
    "THEHIVE_PASSWORD": "its password",
    "E2E_TEMPLATE_INSTANCE": (
        "id of an existing add-on instance whose host, port, uri and organisation "
        "the run copies (for example the one pointing at your test organisation)"
    ),
}

#: Optional, with defaults that cannot point anywhere but this machine.
SPLUNK_MGMT = os.environ.get("E2E_SPLUNK_MGMT", "https://localhost:8089")
APP = "TA-thehive-cortex"

#: Seconds. A dispatched saved search is polled, never slept on: a fixed sleep
#: is either too short (flaky) or too long (a suite nobody runs).
DELAI_JOB = int(os.environ.get("E2E_JOB_TIMEOUT", "180"))
#: TheHive is not synchronous with Splunk: the alert action returns before the
#: object is queryable. Same rule -- poll, do not sleep.
DELAI_THEHIVE = int(os.environ.get("E2E_THEHIVE_TIMEOUT", "90"))


def manque():
    """Return the names of the required variables that are not set."""
    return [nom for nom in REQUIS if not os.environ.get(nom)]


def raison_du_saut():
    absents = manque()
    if not absents:
        return None
    details = ", ".join(f"{nom} ({REQUIS[nom]})" for nom in absents)
    return (
        "end-to-end campaign not configured; set " + details + " in the environment "
        "or in tests/e2e/.env"
    )


#: Use as `@unittest.skipIf(*SAUT)` -- a skipped test that says why.
SAUT = (raison_du_saut() is not None, raison_du_saut() or "")


def valeur(nom):
    """Read a required value. Never log it, never put it on a command line."""
    return os.environ[nom]
