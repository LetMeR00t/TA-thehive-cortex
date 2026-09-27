"""Install, or show, the TheHive Function the UC5 case pushes to.

    python -m tests.e2e.uc5_function            # is it there?
    python -m tests.e2e.uc5_function --install  # create it (once)

The Function is `e2e-uc5-echo` (type `api`, mode `Enabled`); its source is
`uc5_echo_function.js`, next to this file. It is the ONLY global TheHive object
the campaign keeps between runs (user decision 2026-09-27): a Function cannot
be created per run without being a configuration change each time.

The creation body -- `name`, `mode`, `definition`, `types`, `description` --
is TheHive 5.7.5's `InputFunction` (thehive-dto), posted to
`/api/v1/function`; types are `api`, `notification`, `action:alert`,
`action:case`. Functions need a Platinum licence and the
`manageFunction/create` permission.

Removing it is deliberately NOT scripted here (the campaign never deletes it):
Organisation > Functions > `e2e-uc5-echo` > delete, in TheHive's UI. Then
unset `E2E_THEHIVE_FUNCTION` and UC5 skips again, saying why.
"""

import argparse
import os
import sys

from . import _config
from .purge import _clients

NAME = "e2e-uc5-echo"
SOURCE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uc5_echo_function.js")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--install", action="store_true", help="create the Function if absent")
    args = parser.parse_args(argv)

    reason = _config.skip_reason()
    if reason:
        print(reason, file=sys.stderr)
        return 2
    _, thehive = _clients()

    present = NAME in thehive.function_names()
    print(f"Function {NAME}: {'present' if present else 'absent'}")
    if present or not args.install:
        return 0 if present else 1

    with open(SOURCE, encoding="utf-8") as fh:
        definition = fh.read()
    thehive.create_function(
        NAME, definition, types=["api"], mode="Enabled",
        description="End-to-end campaign UC5 target: turns pushed events into one "
                    "alert (TA-thehive-cortex tests/e2e).",
    )
    present = NAME in thehive.function_names()
    print(f"Function {NAME}: {'created' if present else 'NOT created'}")
    return 0 if present else 1


if __name__ == "__main__":
    sys.exit(main())
