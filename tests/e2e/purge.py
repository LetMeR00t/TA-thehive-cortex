"""Sweep up what a previous run left behind, and report what is still there.

    python -m tests.e2e.purge            # list, change nothing
    python -m tests.e2e.purge --purge    # delete every e2e_ object

⚠️ A recovery that needs a human is not a recovery. A run killed between
creating its saved search and its teardown leaves a scheduled search and an
add-on instance behind; this is what removes them without anyone having to
remember which run it was.

It only ever touches names starting with the campaign prefix. That is the
whole reason every object carries it.
"""

import sys

from . import _config
from ._case import PREFIX
from ._splunk import SplunkClient
from ._thehive import TheHiveClient


def _clients():
    splunk = SplunkClient(
        _config.SPLUNK_MGMT,
        _config.value("SPLUNK_USER"),
        _config.value("SPLUNK_PASSWORD"),
        _config.APP,
    )
    template = splunk.read_instance(_config.value("E2E_TEMPLATE_INSTANCE"))
    schema = "https" if str(template.get("port")) == "443" else "http"
    thehive = TheHiveClient(
        f"{schema}://{template['host']}:{template.get('port', '443')}",
        _config.value("THEHIVE_USER"),
        _config.value("THEHIVE_PASSWORD"),
        template.get("organisation"),
    )
    return splunk, thehive


def inventory(splunk, thehive):
    return {
        "saved searches": splunk.searches_by_prefix(PREFIX),
        "instances": splunk.instances_by_prefix(PREFIX),
        "accounts": splunk.accounts_by_prefix(PREFIX),
        "thehive alerts": [a.get("title") for a in thehive.alerts_by_title_prefix(PREFIX)],
        "thehive cases": [c.get("title") for c in thehive.cases_by_title_prefix(PREFIX)],
    }


def main(argv):
    reason = _config.skip_reason()
    if reason:
        print(reason)
        return 2

    splunk, thehive = _clients()
    leftovers = inventory(splunk, thehive)
    total = sum(len(v) for v in leftovers.values())

    for kind, names in leftovers.items():
        print(f"{kind}: {len(names)}")
        for name in names:
            print(f"    {name}")

    if "--purge" not in argv:
        print("\nnothing was deleted; pass --purge to remove the objects listed above")
        return 0 if total == 0 else 1

    for name in leftovers["saved searches"]:
        splunk.delete_saved_search(name)
    for name in leftovers["instances"]:
        splunk.delete_instance(name)
    for name in leftovers["accounts"]:
        splunk.delete_account(name)
    erased = thehive.delete_by_prefix(PREFIX)

    leftover = inventory(splunk, thehive)
    still = sum(len(v) for v in leftover.values())
    print(f"\ndeleted {total - still} object(s) ({erased} of them in TheHive)")
    if still:
        # Saying "cleaned" while something is left is exactly the lie this
        # script exists to prevent.
        print(f"⚠️  {still} object(s) still carry the prefix; see the listing above")
    return 1 if still else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
