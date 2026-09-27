# Testing: what a guard actually proves

> Trigger: read this when you write or change a test, a mock, or a coverage floor.

## Mocking a module wholesale makes all of it untestable

Every unit test in this repository used to start with

```python
sys.modules['common'] = MagicMock()
```

so that the module under test could be imported outside Splunk. The side effect
went unnoticed for a long time: **`common.py` itself could never be tested.**
Its instance resolution sat at 0 % coverage while calling `sys.exit()` on an
unknown id -- a code path that ends the Splunk process, and that nothing could
reach to prove it.

Mock the **dependencies**, never the module you are testing, and mock them only
for the duration of the import (`tests/_isolation.py`). When a constructor is
too entangled to call -- `Settings.__init__` is 234 lines and talks to Splunk's
configuration manager -- build the object with `object.__new__(Cls)` and set the
attributes the method under test actually reads. That tests the method rather
than the connection.

### Inheriting from a mock makes the `class` statement mute

A modular input is `class X(smi.Script)`. Mock `splunklib.modularinput`
wholesale and `smi.Script` is a `MagicMock` -- so the `class` statement
evaluates to a **mock**, not a class. `X()` returns a mock, `X().stream_events()`
calls a mock on a mock, and the test goes green having executed not one line
of production code. Two "integration" tests here did exactly that.

The template for any test of a UCC modular input is in `tests/_isolation.py`:

```python
from _isolation import temporary_mocks, stub_splunklib

with temporary_mocks(MOCKS, stub_splunklib()):
    import my_input
```

`stub_splunklib()` replaces **both** `splunklib` and `splunklib.modularinput`
with real modules carrying a real `Script` base class. Replacing only the
submodule is not enough: `from splunklib import modularinput` reads an
attribute of the parent, and a mocked parent wins silently. The stubs copy the
SDK's attribute names exactly (`sourceType`, capital T included): a stub that
invents its own names lets assertions pass against something production never
reads.

### Every test module must pass alone

`tools/checks/tests_run_alone.py` runs each module in a process of its own,
then the whole suite in **reversed** order. A module that only imports because
an earlier one put a folder on `sys.path`, or only passes because an earlier
one left a mock in `sys.modules`, is green in discovery and red alone -- two
modules were, for weeks, after a file moved into the package folder.

Remove what a test creates with `_isolation.remove_tree()`, never
`shutil.rmtree(..., ignore_errors=True)`: the latter swallows the WinError 32
that is Windows' way of saying the code under test left a file open.

⚠️ And prefer a **named exception** to `sys.exit()`. A search command already
turns any exception into a readable SPL error
(`Intersplunk.generateErrorResults`); calling `sys.exit()` instead gives the
user a search that stops without a word, and gives the tests nothing to catch.

## Never delete a value before knowing how to handle it

`parse_events()` removed a key from the row and only THEN looked at its type.
When the type was one the chain did not know, the field was not added and the
value was gone from the raw table reinjected into the description as well.
Losing it twice is what made GitHub #133 expensive: the alert reached TheHive,
it looked right, and the analyst had nowhere left to read the missing value.

The rule is one line: **consume, then delete.** Removal belongs on the success
path, never before the branch that decides. When a value cannot be mapped, keep
it where a human can still see it and say so with a named warning.

⚠️ And a dispatch chain needs a terminal branch. The composite-key branch had
`if mainkey in data_type:` with no `else` at all, so a prefix naming no known
datatype vanished without even a warning -- indistinguishable from a field that
was never sent.

The protection that matters is not a test per branch, it is the INVARIANT:
whatever key a row carries, its value must be findable somewhere in what
reaches TheHive -- observable, custom field, TTP, or the raw table. See
`tests/test_parse_events_losses_unit.py`; reinstating a single premature `del`
turns it red on its own.

## A test that shares its table of truth with production is a copy, not a guard

`tests/test_custom_fields_unit.py` enumerated the TheHive custom field types --
the same list the production chain carried. The test was green, and it would
have stayed green **on the very day TheHive introduced a new type**, which is
the only day it would have mattered. It reproduced the assumption it was
supposed to challenge.

The list of custom field types belongs to TheHive, not to this add-on. What the
add-on may legitimately hold is the list of types it knows how to **convert**
(`TYPES_CONNUS`); anything outside it is forwarded as text and TheHive decides.

So a guard must exercise something production does not already know:
an **invented** type, a value that does not fit its declared type, a shape the
code was never written for. If the test can only be red when production is
wrong about something it already lists, it is a mirror.

## Name the interpreter, never inherit it

`ucc-gen` wants Python 3.9, AppInspect refuses to install below 3.11, and a
machine's bare `python3` is whatever that machine happens to ship -- the
workspace pod has no `python` binary at all and its `python3` is 3.11. An
implicit interpreter produces a build that works on one machine and nowhere
else, and the failure surfaces far from its cause.

So `.github/workflows/ci.yml` names 3.9 for the build and 3.9 **and** 3.13 for
the tests. ⚠️ Both test runs must be green: this add-on declares
`python.required = 3.9, 3.13`, Splunk <= 10.1 serves 3.9 only, and 10.2 keeps
3.9 as its default. Testing one of the two proves nothing about most of the
installed base -- and the vendored `thehive4py` is heading for a release that
declares `Requires-Python >=3.10`.

## Coverage floors are a ratchet, not an ambition

`tools/checks/coverage_floors.py` enforces floors **per path**, never a global
one. A global floor over 8,685 lines is either trivially met or unreachable,
and says nothing either way: this repository sat at a respectable-looking
overall figure while instance resolution and credential arbitration were at
**0 %**.

Each floor sits at or just below what is measured today, so the build goes red
on a regression and only on that. ⚠️ A floor set above reality makes CI red
from birth, and a guard that is red from birth gets switched off -- after which
it guards nothing. The **target** is reported next to it and never enforced;
raising the floor towards it is a deliberate act, taken once the tests that
justify it exist.

## What the package contains is not what the folder shows

`ucc-gen` copies `package/bin` verbatim. A `__pycache__` left by a local test
run therefore ships inside the `.spl` and fails Splunk Cloud vetting -- while
`output/` and the source tree both look perfectly clean. That is why §3 says to
check the archive, and `tools/checks/package_contents.sh` is that check.

⚠️ It **refuses to run** when it finds no `.spl`, rather than passing. A check
that goes green because it had nothing to inspect is worse than no check: it
reports a verification that never happened.

It also **requires** one file to be present: `libs/cortex4py/__init__.py`. It is
zero bytes and it is load-bearing -- without it `cortex4py` becomes an implicit
namespace package and another Splunk add-on shipping the same name can shadow
its root modules, which is exactly what `cortex.py` imports. It was already lost
once, in the UCC migration, and nobody noticed for years. Nothing about a 0-byte
file suggests it matters, so the check says it instead.
