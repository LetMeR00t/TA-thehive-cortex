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
import types
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


class _Argument:
    """Real stand-in for splunklib.modularinput.Argument."""

    def __init__(self, name, title=None, description=None, **options):
        self.name = name
        self.title = title
        self.description = description
        self.options = options


class _Scheme:
    """Real stand-in for splunklib.modularinput.Scheme."""

    def __init__(self, title):
        self.title = title
        self.description = None
        self.use_external_validation = False
        self.streaming_mode_xml = True
        self.use_single_instance = False
        self.arguments = []

    def add_argument(self, argument):
        self.arguments.append(argument)


class _Event:
    """Real stand-in for splunklib.modularinput.Event.

    The attribute names are copied from splunk-sdk 2.1.1
    (splunklib/modularinput/event.py), INCLUDING the capital T of `sourceType`.
    A stub that invents its own names is worse than no stub: assertions written
    against it pass while the production code reads something else.
    """

    def __init__(self, data=None, stanza=None, time=None, host=None,
                 index=None, source=None, sourcetype=None, done=True,
                 unbroken=True):
        self.data = data
        self.done = done
        self.host = host
        self.index = index
        self.source = source
        self.sourceType = sourcetype
        self.stanza = stanza
        self.time = time
        self.unbroken = unbroken


class _Script:
    """Real stand-in for splunklib.modularinput.Script.

    ⚠️ THIS CLASS IS THE WHOLE POINT of stub_modularinput(). Mocking
    `splunklib.modularinput` wholesale makes `smi.Script` a MagicMock, and
    `class X(smi.Script)` then evaluates to a MagicMock instead of a class:
    instantiating X returns a mock, and calling X().stream_events() calls a
    mock on a mock. The test goes green having executed not one line of
    production code. A real base class is what makes the inheritance real.
    """

    def __init__(self):
        pass


def stub_modularinput():
    """A module object exposing the four names the modular inputs actually use."""
    module = types.ModuleType("splunklib.modularinput")
    module.Script = _Script
    module.Scheme = _Scheme
    module.Argument = _Argument
    module.Event = _Event
    return module


def stub_splunklib():
    """Replacements for BOTH `splunklib` and `splunklib.modularinput`.

    ⚠️ Replacing only the submodule is not enough, and the reason is easy to
    miss. The production code writes:

        from splunklib import modularinput as smi

    which resolves `modularinput` as an ATTRIBUTE of the `splunklib` object.
    When `splunklib` is a MagicMock, that attribute access happily returns a
    child mock and the entry we carefully placed in
    `sys.modules['splunklib.modularinput']` is never consulted. The parent mock
    silently wins over the real stub.

    So the parent must be a real module too, carrying the stub as an attribute.
    """
    modularinput = stub_modularinput()
    paquet = types.ModuleType("splunklib")
    paquet.modularinput = modularinput
    paquet.client = MagicMock()
    return {"splunklib": paquet, "splunklib.modularinput": modularinput}


@contextlib.contextmanager
def mocks_temporaires(noms, remplacements=None):
    """Stub `noms` in sys.modules, then restore the table exactly as it was.

    Restoring matters more than stubbing: a name that was ABSENT must go back
    to absent, not to None, otherwise a later `import` finds a null entry and
    fails in a way that looks nothing like the cause.
    """
    remplacements = remplacements or {}
    sentinelle = object()
    precedent = {nom: sys.modules.get(nom, sentinelle) for nom in noms}
    for nom in noms:
        sys.modules[nom] = remplacements.get(nom) or MagicMock()
    try:
        yield
    finally:
        for nom, ancien in precedent.items():
            if ancien is sentinelle:
                sys.modules.pop(nom, None)
            else:
                sys.modules[nom] = ancien
