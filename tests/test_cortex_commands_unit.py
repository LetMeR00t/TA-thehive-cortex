"""Cortex commands: two defects that make them fail on the very first call.

Both are invisible to every existing test because nothing ever exercises these
code paths offline. They are not edge cases -- they are the nominal path.

1. `cortex_refresh_analyzers.py` calls `initialize_cortex_instance()` without
   the mandatory positional `acronym`, so the command raises TypeError and has
   never been able to run. This is why it is the only command missing from both
   `docs/commands.md` and `searchbnf.conf`: it was never documented because it
   was never used.

2. `Cortex.addJob()` reads `self.logger` while `Cortex.__init__` only ever sets
   `self.logger_file`, so `cortexrun` raises AttributeError. The mirror defect
   lives in `CortexJob.__init__`, which sets `self.logger` and then reads
   `self.logger_file` on its error branch.

The first test walks EVERY call site rather than the one known to be broken:
a signature mismatch is a class of defect, and pinning a single caller would
let the next one through.
"""

import ast
import inspect
import os
import sys
import unittest
from unittest.mock import MagicMock

# Mock EVERYTHING that is not available locally
mocks = [
    'splunklib', 'splunklib.client', 'solnlib', 'solnlib.log',
    'solnlib.modular_input', 'solnlib.utils', 'ta_thehive_cortex_declare',
    'certifi', 'common', 'ta_logging', 'requests', 'requests.adapters',
    'requests.auth', 'urllib3', 'splunk', 'splunk.Intersplunk', 'globals',
]


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _isolation import temporary_mocks  # noqa: E402

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(APP_ROOT, 'TA-thehive-cortex', 'package', 'bin')
for p in (BIN,
          os.path.join(BIN, 'ta_thehive_cortex'),
          os.path.join(BIN, 'ta_thehive_cortex', 'libs')):
    if p not in sys.path:
        sys.path.insert(0, p)

with temporary_mocks(mocks):
    import cortex as cortex_module  # noqa: E402


class TestInitializeCortexInstanceCallSites(unittest.TestCase):
    """Every caller must bind against the real signature.

    Reading the source rather than importing it is deliberate: these modules
    are Splunk scripts that execute work at import time.
    """

    #: Arguments we can substitute for any expression, since only ARITY and
    #: keyword NAMES decide whether the call binds.
    TOKEN = object()

    #: Every locally-defined callable whose call sites must bind. Adding a name
    #: here is cheaper than discovering the mismatch in production: a keyword
    #: that does not exist is a TypeError on the FIRST call, not an edge case.
    TARGETS = ("initialize_cortex_instance", "create_cortex_instance", "Cortex")

    def _call_sites(self):
        signatures = {}
        for name_ in self.TARGETS:
            obj = getattr(cortex_module, name_, None)
            if obj is None:
                continue
            signatures[name_] = inspect.signature(obj)
        for name_ in sorted(os.listdir(BIN)):
            if not name_.endswith('.py'):
                continue
            file_path = os.path.join(BIN, name_)
            with open(file_path, encoding='utf-8') as fh:
                tree = ast.parse(fh.read(), filename=name_)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                target = node.func
                if isinstance(target, ast.Name) and target.id in signatures:
                    yield name_, node, signatures[target.id], target.id

    def test_every_call_binds(self):
        found = 0
        offenders = []
        for name_, node, signature, callee in self._call_sites():
            found += 1
            positional = [self.TOKEN] * len(node.args)
            named = {kw.arg: self.TOKEN for kw in node.keywords if kw.arg}
            try:
                signature.bind(*positional, **named)
            except TypeError as err:
                offenders.append(f"{name_}:{node.lineno} {callee}(): {err}")

        self.assertGreater(found, 0, "no call site found -- the test is blind")
        self.assertEqual(
            [], offenders,
            "call sites that do not bind against their signature:\n  "
            + "\n  ".join(offenders),
        )


class TestCortexAddJobAttributes(unittest.TestCase):
    """`addJob` must only read attributes that `__init__` actually sets."""

    def _cortex_without_network(self):
        """A Cortex whose __init__ is bypassed: it performs a live API call."""
        instance = object.__new__(cortex_module.Cortex)
        instance.logger_file = MagicMock()
        instance.analyzers = MagicMock()
        instance.analyzers.get_by_type.return_value = [MagicMock(id="a1", name="an")]
        instance._Cortex__jobs = []
        instance._Cortex__sid = "sid"
        return instance

    def test_addjob_does_not_read_an_undefined_attribute(self):
        instance = self._cortex_without_network()
        # A dataType from the hardcoded list, so the type gate is not what fails.
        instance.addJob(data="1.2.3.4", dataType="ip")
        self.assertEqual(1, len(instance.getJobs()))

    def test_addjob_accepts_a_datatype_outside_the_frozen_list(self):
        """Cortex is the authority on its own dataTypes, not a frozen copy.

        `hostname` and `autonomous-system` are absent from cortex.py's list
        while being present in the one carried by modalert_thehive_common.py --
        the two copies disagree, and the stricter one used to call sys.exit().
        """
        instance = self._cortex_without_network()
        instance.addJob(data="a-host", dataType="hostname")
        self.assertEqual(1, len(instance.getJobs()))


class TestCortexAddJobAnalyzerCaching(unittest.TestCase):
    """Gitea #32: resolving analyzers is invariant across rows in one run.

    `cortexrun` calls `addJob()` once per search result. Before this, a named
    analyzer was re-resolved by name on every single row (2*N*A avoidable
    calls for N rows and A analyzers), and "all" was re-resolved by type on
    every row sharing the same dataType. Both are now memoised on the
    instance -- its lifetime already matches one execution.

    Addresses are the RFC 5737 documentation range, as in
    test_cortex_jobs_unit.py.
    """

    def _cortex_without_network(self):
        instance = object.__new__(cortex_module.Cortex)
        instance.logger_file = MagicMock()
        instance.analyzers = MagicMock()
        instance.analyzers.get_by_name.return_value = MagicMock(id="a1", name="VirusTotal")
        instance.analyzers.get_by_type.return_value = [MagicMock(id="a2", name="Abuse_Finder")]
        instance._Cortex__jobs = []
        instance._Cortex__sid = "sid"
        return instance

    def test_named_analyzer_is_resolved_once_across_rows(self):
        instance = self._cortex_without_network()

        instance.addJob(data="192.0.2.10", dataType="ip", analyzers="VirusTotal")
        instance.addJob(data="192.0.2.11", dataType="ip", analyzers="VirusTotal")
        instance.addJob(data="evil.example", dataType="domain", analyzers="VirusTotal")

        instance.analyzers.get_by_name.assert_called_once_with("VirusTotal")
        self.assertEqual(3, len(instance.getJobs()))

    def test_all_analyzers_resolved_once_per_datatype(self):
        instance = self._cortex_without_network()

        instance.addJob(data="192.0.2.10", dataType="ip", analyzers="all")
        instance.addJob(data="192.0.2.11", dataType="ip", analyzers="all")
        instance.addJob(data="evil.example", dataType="domain", analyzers="all")

        instance.analyzers.get_by_type.assert_any_call("ip")
        instance.analyzers.get_by_type.assert_any_call("domain")
        self.assertEqual(2, instance.analyzers.get_by_type.call_count)

    def test_an_unresolved_analyzer_still_exits_every_time_it_recurs(self):
        """Caching a failure must not turn a hard stop into a silent skip."""
        instance = self._cortex_without_network()
        instance.analyzers.get_by_name.return_value = None

        with self.assertRaises(SystemExit):
            instance.addJob(data="192.0.2.10", dataType="ip", analyzers="Ghost")


class TestCortexHonoursTheInstanceCaBundle(unittest.TestCase):
    """Gitea #45: the Cortex client ignored the instance's CA Certificate Path.

    `common.Settings` resolves `verify` per instance -- the PEM bundle under
    local/, or True -- and every TheHive construction passes it on. The Cortex
    one hardcoded `verify=True`, so a Cortex behind a private authority failed
    TLS against the bundled certifi store, which cortex4py then reported as
    `C26 SERVICE UNAVAILABLE`. Found on a real Cortex 4.2.0, not by reading.
    """

    def test_verify_comes_from_the_instance(self):
        bundle = os.path.join("local", "cacert.crt")
        settings = MagicMock()
        settings.getInstanceUsernameApiKey.return_value = ("user", "key")
        settings.getInstanceURL.return_value = "https://cortex.example:443"
        settings.getHttpTimeout.return_value = "60"
        settings.getInstanceSetting.side_effect = lambda _id, name: {
            "authentication_type": "api_key",
            "verify": bundle,
        }.get(name)

        with unittest.mock.patch.object(cortex_module, "client"), \
             unittest.mock.patch.object(cortex_module, "LoggerFile"), \
             unittest.mock.patch.object(cortex_module, "Settings", return_value=settings), \
             unittest.mock.patch.object(cortex_module, "Cortex") as cortex_cls:
            cortex_module.create_cortex_instance(
                "cortex", {"session_key": "s", "sid": "1"}, MagicMock(), acronym="T")

        self.assertEqual(cortex_cls.call_args.kwargs["verify"], bundle)


if __name__ == '__main__':
    unittest.main()
