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
from ._splunk import SplunkClient
from ._thehive import TheHiveClient

#: ⚠️ Underscore, not hyphen. The add-on's REST handlers validate account and
#: instance names against `^[a-zA-Z]\w*$`: a hyphen is rejected with a 400 that
#: names a pattern and not the field. One prefix for every object, on both
#: sides, is what makes the cleanup provably total.
PREFIX = "e2e_"


def new_identifier():
    """Short, unique, and readable in a TheHive list without scrolling."""
    return uuid.uuid4().hex[:8]


@unittest.skipIf(*_config.SKIP_REASON)
class E2ECampaign(unittest.TestCase):
    """Base class: builds the configuration once, destroys everything after."""

    #: Overridden by the tests that need the alert action to see a specific
    #: organisation; by default the template instance's own.
    organisation = None

    @classmethod
    def setUpClass(cls):
        cls.runid = new_identifier()
        cls.prefix = f"{PREFIX}{cls.runid}"

        cls.splunk = SplunkClient(
            _config.SPLUNK_MGMT,
            _config.value("SPLUNK_USER"),
            _config.value("SPLUNK_PASSWORD"),
            _config.APP,
        )

        template = cls.splunk.read_instance(_config.value("E2E_TEMPLATE_INSTANCE"))
        cls.organisation = cls.organisation or template.get("organisation")

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
        cls.instance_name = f"{cls.prefix}_instance"
        cls._splunk_objects = []

        cls.splunk.create_instance(cls.instance_name, template, template.get("account_name"),
                                  template.get("authentication_type", "api_key"))
        cls._splunk_objects.append(("instance", cls.instance_name))

        schema = "https" if str(template.get("port")) == "443" else "http"
        base = f"{schema}://{template['host']}:{template.get('port', '443')}"
        cls.thehive = TheHiveClient(
            base,
            _config.value("THEHIVE_USER"),
            _config.value("THEHIVE_PASSWORD"),
            cls.organisation,
        )

    @classmethod
    def tearDownClass(cls):
        for kind, name in reversed(getattr(cls, "_splunk_objects", [])):
            if kind == "instance":
                cls.splunk.delete_instance(name)
            elif kind == "account":
                cls.splunk.delete_account(name)

    def setUp(self):
        self._searches = []

    def tearDown(self):
        for name in self._searches:
            self.splunk.delete_saved_search(name)
        # TheHive last: if deleting an alert fails we still want the Splunk
        # side gone, otherwise the next run inherits a scheduled search.
        self.thehive.delete_by_prefix(self.prefix)

    # -- helpers used by the use cases ------------------------------------

    def play(self, suffix, search, action, parameters):
        """Create the saved search, fire it with its action, wait for the job."""
        name = f"{self.prefix}_{suffix}"
        self.splunk.create_saved_search(name, search, action, parameters)
        self._searches.append(name)
        sid = self.splunk.dispatch(name)
        state = self.splunk.wait_for_job(sid, _config.JOB_TIMEOUT)
        self.assertNotEqual(
            "FAILED",
            state.get("dispatchState"),
            "the saved search itself failed before the alert action could run",
        )
        return name

    def assert_clean_log(self, search_name, tolerated=()):
        """No ERROR, and no silent-loss warning, unless the case expects one.

        ⚠️ This is half of what makes the campaign worth running. The defects
        that hurt here do not fail: they log a warning and return success. A
        test that only checks TheHive would miss the ones where TheHive was
        never told, and a test that only checks Splunk would miss the ones
        where Splunk was told and got it wrong.
        """
        rows = self.splunk.action_log(search_name)
        offending = [
            row
            for row in rows
            if ("ERROR" in row or "THC-117" in row)
            and not any(code in row for code in tolerated)
        ]
        self.assertEqual(
            [],
            [row[:200] for row in offending],
            "the alert action logged an error or a silent-loss warning",
        )
