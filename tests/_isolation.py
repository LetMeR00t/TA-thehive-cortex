"""Install import-time mocks WITHOUT leaking them into the rest of the suite.

Every test module here has to stub what is not available outside Splunk
(`splunklib`, `solnlib`, `splunk.Intersplunk`, ...) *before* importing the
production module under test. The straightforward way to do that --

    for mod in mocks:
        sys.modules[mod] = MagicMock()

-- writes into a process-wide table and never takes it back. The consequence
is not theoretical: `unittest discover` walks modules in alphabetical order, so
whichever file runs first decides what every later file sees. A module that
stubs `ta_logging` makes the tests OF `ta_logging` import a MagicMock; tests
that pass in isolation then fail in the full suite, and the failure points at
the innocent file.

The fix is to keep the mocks only for the duration of the import:

    with mocks_temporaires(MOCKS):
        import modalert_thehive_common

The imported module keeps the mocked dependencies it bound at import time --
which is what the test wants -- while `sys.modules` is put back exactly as it
was, so the next test module starts from a clean table.
"""

import contextlib
import sys
from unittest.mock import MagicMock

#: Absent outside a Splunk installation. Stubbed at import time so the module
#: under test can be loaded at all.
MOCKS_SPLUNK = [
    'splunklib', 'splunklib.client', 'splunklib.modularinput',
    'solnlib', 'solnlib.log', 'solnlib.modular_input', 'solnlib.utils',
    'splunk', 'splunk.Intersplunk',
    'ta_thehive_cortex_declare',
]

#: Third-party libraries vendored in the add-on, not installed on a dev machine.
MOCKS_TIERS = [
    'certifi', 'requests', 'requests.adapters', 'requests.auth',
    'urllib3', 'tomark',
]


@contextlib.contextmanager
def mocks_temporaires(noms):
    """Stub `noms` in sys.modules, then restore the table exactly as it was.

    Restoring matters more than stubbing: a name that was ABSENT must go back
    to absent, not to None, otherwise a later `import` finds a null entry and
    fails in a way that looks nothing like the cause.
    """
    sentinelle = object()
    precedent = {nom: sys.modules.get(nom, sentinelle) for nom in noms}
    for nom in noms:
        sys.modules[nom] = MagicMock()
    try:
        yield
    finally:
        for nom, ancien in precedent.items():
            if ancien is sentinelle:
                sys.modules.pop(nom, None)
            else:
                sys.modules[nom] = ancien
