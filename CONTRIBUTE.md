# Contribution Guide - TA-thehive-cortex

## Commits

Follow this convention: [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/)

## Build & Packaging Lifecycle

### 1. Build (UCC Generation)
The Add-on uses the [Splunk UCC Generator](https://splunk.github.io/addonfactory-ucc-generator/). 

**Prerequisite:** You MUST use **Python 3.9** to run the UCC generator to ensure compatibility with Splunk's internal libraries.

To build the application:
```powershell
# Recommended build command
ucc-gen build --source TA-thehive-cortex/package --config TA-thehive-cortex/globalConfig.json --output output --ta-version 4.2.2 --overwrite -v --python-binary-name python
```
*Note: You may need to specify `--python-binary-name` (e.g., `python3.9` or the full path) if your default Python is not compatible.*

### Who decides the version

**`ucc-gen` does, and it writes the answer back into your sources.**

- `--ta-version` is the source of truth. The build stamps it into `app.conf`,
  `app.manifest`, `VERSION` — **and into `globalConfig.json` itself**
  (`meta.version` is rewritten, then saved). Editing `meta.version` by hand
  before a build is redundant: the build overwrites it either way.
- **Omit `--ta-version` and the version comes from the latest git tag.** With no
  usable tag, the build refuses to run rather than guess.
- `package/app.manifest` carries a stale `4.0.0` in the sources. It is **inert**
  — the generated manifest is rewritten from `--ta-version`. Do not trust it,
  and do not bother fixing it.

Practical consequence: after a build, `git status` shows `globalConfig.json` as
modified even if you changed nothing. That is the generator writing into its own
input, not a stray edit.

### 2. Packaging (.spl)
For the agent's environment, the following cleanup is applied to the `output/` folder before packaging:

```powershell
# Cleanup compiled-Python artifacts. ucc-gen copies the source bin/ as-is, so any
# stale __pycache__/*.pyc left in package/bin (e.g. from running tests locally)
# would ship inside the .spl and fail Splunk Cloud AppInspect.
Get-ChildItem "output/TA-thehive-cortex" -Recurse -Include *.pyc, *.pyo -File | Remove-Item -Force -ErrorAction SilentlyContinue;
Get-ChildItem "output/TA-thehive-cortex" -Recurse -Directory | Where-Object { $_.Name -eq "__pycache__" } | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue;

# Cleanup Windows binaries (keep Mako templates as they are required for UI)
Get-ChildItem "output/TA-thehive-cortex/lib" -Recurse -Include *.exe, *.pyd -File | Remove-Item -Force -ErrorAction SilentlyContinue;

# Create the .spl file
tar -czf TA-thehive-cortex.spl -C output TA-thehive-cortex
```

### 3. AppInspect (Splunk Cloud vetting)

Run the cloud checks on the `.spl` itself, never on `output/` -- the archive is
what Splunk receives.

```powershell
# Requires splunk-appinspect (Python 3.11; it does not install on 3.9).
splunk-appinspect inspect TA-thehive-cortex.spl --mode precert --included-tags cloud `
  --data-format json --output-file appinspect.json
```

Read the `summary` block of the JSON rather than the console log. Only
`failure` and `error` block a submission; `future_failure` announces a break in
a future Splunk release, and the `warning` entries here are informational
(frontend telemetry, deprecated SplunkJS, IPs inside vendored libraries).

---

## Autonomous Safe Deployment (CRITICAL)
**NEVER** delete the `local/` folder in the Splunk directory during a deployment. 

Deployment must be performed directly via shell commands (PowerShell) by strictly following these steps:
1. Stop Splunk to release file locks.
2. Temporarily move the existing `local/` folder to a backup directory outside the app's tree.
3. Remove the old version of the application.
4. Deploy the new build from `output/`.
5. Restore the backed-up `local/` folder.
6. Restart Splunk.

**Direct command example:**
```powershell
& "C:\Program Files\Splunk\bin\splunk.exe" stop; if (Test-Path "C:\Program Files\Splunk\etc\apps\TA-thehive-cortex\local") { Move-Item "C:\Program Files\Splunk\etc\apps\TA-thehive-cortex\local" "$env:TEMP\TA_local_backup" -Force }; Remove-Item "C:\Program Files\Splunk\etc\apps\TA-thehive-cortex" -Recurse -Force -ErrorAction SilentlyContinue; Copy-Item -Path "output\TA-thehive-cortex" -Destination "C:\Program Files\Splunk\etc\apps\" -Recurse -Force; if (Test-Path "$env:TEMP\TA_local_backup") { if (-not (Test-Path "C:\Program Files\Splunk\etc\apps\TA-thehive-cortex\local")) { New-Item -Path "C:\Program Files\Splunk\etc\apps\TA-thehive-cortex\local" -ItemType Directory }; Copy-Item -Path "$env:TEMP\TA_local_backup\*" -Destination "C:\Program Files\Splunk\etc\apps\TA-thehive-cortex\local" -Recurse -Force; Remove-Item "$env:TEMP\TA_local_backup" -Recurse -Force }; & "C:\Program Files\Splunk\bin\splunk.exe" start
```

---

## Lessons Learned & Best Practices

*This section is for sharing generic technical lessons learned during development. Do not include setup-specific or sensitive information.*

- **Python Compatibility**: Always use Splunk's internal Python version (3.9+) for builds and local testing to ensure library compatibility.
- **UCC Framework**: All UI changes MUST be made in `globalConfig.json`. Manual changes to `default/data/ui` will be overwritten during the next build. Note: custom XML views are stored in `package/default/data/ui/views`.
- **Splunk Tokens Evaluation**: When checking if a dashboard token is defined in an SPL `eval`, always escape the comparison token with `$$` (e.g., `"$token$" == "$$token$$"`). This prevents the condition from becoming always true after token substitution (e.g., `"-1d" == "-1d"`).
- **Library Isolation**: Third-party libraries must be placed in `package/bin/ta_thehive_cortex/libs` to avoid conflicts with other Splunk apps.
- **Mako `appserver/templates/base.html` is emitted by `ucc-gen` itself**: AppInspect flags it as a `future_failure` (removed in Splunk 10.4) and advises "regenerate the app with UCC framework version 6.3.0 or later". That advice is not actionable -- UCC **6.5.3** still generates the file, and the source tree has no `package/appserver/templates/` at all. Nothing can be done from this repository; wait for an UCC release that stops emitting it. Do **not** delete the template by hand: it backs the configuration UI.
- **`requirements.txt` is a source file, not a virtualenv**: the standard Python `.gitignore` carries a bare `lib/` rule, which silently swallowed `package/lib/requirements.txt` -- the file pinning every runtime dependency of the add-on. A fresh clone could not rebuild the same TA. The `.gitignore` now re-includes it explicitly. When a build reads a file, check `git check-ignore -v` on that file before assuming it is versioned.
- **`python.required` is a version list, not an interpreter name**: `python.version = python3` (still required by current checks) and `python.required = 3.9, 3.13` are two different keys. Declaring `python.required` asserts compatibility with those interpreters, third-party libraries included -- set it deliberately, and mirror it in `globalConfig.json` under `meta.supportedPythonVersion`.
- **`ucc-gen` pins its own floor for `splunktaucclib`**: upgrading the generator can fail the build with "found but has the wrong version" long before any code changes. Bump the pin in `package/lib/requirements.txt` to match the generator's minimum.
- **Clean `.spl` (no compiled Python)**: `ucc-gen` installs pip deps with `--no-compile`, but it copies the source `bin/` verbatim. Running tests or scripts locally leaves `__pycache__`/`*.pyc` in `package/bin`, which then get embedded in `output/` and the `.spl`, failing Splunk Cloud AppInspect. Always strip `*.pyc`, `*.pyo` and `__pycache__` (in addition to `*.exe`/`*.pyd`) before `tar`-ing the package, and verify the archive itself with `tar -tzf TA-thehive-cortex.spl` rather than just checking `output/`.

## Repository checks

Run before opening a pull request. They are cheap, offline, and they exist
because each one comes from a defect that shipped.

```bash
python -m unittest discover -s tests -p "test_*.py"
python tools/checks/no_bare_except.py
python tools/checks/requests_timeout.py
python tools/checks/declared_files_exist.py
python tools/checks/log_sourcetype_covered.py
python tools/checks/rule_not_duplicated.py
python tools/checks/duplication_threshold.py
python tools/checks/log_ids_unique.py
python tools/checks/vendored_path_bootstrap.py
PYTHON=python3.9 tools/checks/pins_match_build.sh
tools/checks/tests_on_both_pythons.sh
```

**And before every tag, on the ARCHIVE:**

```bash
tools/checks/package_contents.sh <app>.spl
```

### `no_bare_except.py`

Refuses `except:` and `except ...: pass` in `TA-thehive-cortex/package/bin`.
Both shapes make a failure indistinguishable from correct behaviour, and this
add-on has paid for it: `except Exception: pass` around the log level
resolution meant a user could configure DEBUG, keep getting INFO, and find no
explanation anywhere.

A silent handler is legitimate when the surrounding code reports the failure
anyway — a best-effort detail added to a message that is logged just below.
Say so **on the line**, with the reason:

```python
except ValueError:  # silent-except: reported by THC-117 below
    pass
```

A bare `except:` is never waivable: it also swallows `KeyboardInterrupt` and
`SystemExit`. Generated files (`cim_actions.py`, `alert_actions_base.py`, …)
are skipped — they are rewritten by `ucc-gen` at every build, so a finding
there cannot be acted upon in this repository.

### `pins_match_build.sh`

**A package that is installed but not pinned makes the build irreproducible,
and nothing signals it.** Two builds a month apart ship different code while
`requirements.txt` swears otherwise. Measured on 2026-08-19: `PySocks`,
`defusedxml` and `sortedcontainers` were shipped without being listed --
sixteen packages installed against thirteen declared.

This is the direct neighbour of the defect in §7: the bare `lib/` rule of the
standard Python `.gitignore` was swallowing `package/lib/requirements.txt`
itself, so the build was not reproducible from a clone. Same family -- what
ships gets decided somewhere nobody is looking.

⚠️ **Run it against the Python the add-on TARGETS**, not the one you happen to
have. Resolution depends on the version: `splunk-sdk` 3.0.0 requires `>=3.13`
and `requests` 2.33 requires `>=3.10`, so a 3.13 run and a 3.9 run do not
produce the same closure. Splunk defaults to 3.9, so 3.9 is what decides.

### `requests_timeout.py`

`requests` has no default timeout. Both vendored libraries shipped without a
single one, so a server that accepts the connection and then says nothing held
a Splunk worker until the kernel gave up. The libraries are patched (see
`package/bin/ta_thehive_cortex/libs/LOCAL_PATCHES.md`); this check exists so the
next upgrade cannot quietly undo the patch.

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

## A declaration must resolve, and neither file can shout on its own

`transforms.conf` declared `filename = thehive_datatypes.csv` while the package
had no `lookups/` directory at all. Both files were individually valid -- a
well-formed declaration, and a file that is simply absent -- so nothing
complained. The break lived **between** them, and it surfaced only on a fresh
installation, where `| inputlookup thehive_datatypes.csv` failed until an alert
action happened to create the file at runtime.

`tools/checks/declared_files_exist.py` closes the gap: every `filename =`
resolves inside `package/lookups/`, every kvstore lookup has its collection in
`collections.conf`, and every `<view name=…>` in the nav is provided by
something.

⚠️ It distinguishes what it can PROVE from what it merely suspects. `instances`
is declared as a configuration TAB in `globalConfig.json`, so a nav entry
pointing at it as a view is provably wrong and fails the check. `jobs` is
reported and does **not** fail: Splunk ships views this repository cannot
enumerate, and failing on a name we cannot resolve is how a guard starts crying
wolf -- after which it gets switched off and protects nothing.

### A rename on one side of a gap, and a symptom that lies

The same family, and the most expensive instance of it in this repository:
v4.0.0 changed the log file names in `ta_logging.py`, and `props.conf` kept
enumerating the v3.x ones. **23 of the 27 log files carried no sourcetype** for
three minor versions.

What made it survive was not the size of the gap, it was the shape of the
symptom. The four `*_modalert` stanzas kept matching -- their suffix had not
changed -- so `props.conf` still produced events and still looked alive. A
defect that breaks *everything* gets found in a day; one that breaks most
things while a visible part keeps working gets rationalised as intended
behaviour. The user who reported it wondered whether it was a bug at all.

Two rules came out of it:

* **Match the shape of a generated name, never the list of today's names.**
  Enumerating the commands signs a regression at every command added. The
  stanzas now key on `TA-thehive-cortex_*` and `*_modalert`.
* **Model every producer, not the one you remember.** Search commands go
  through `ta_logging.setup_logging()`; alert actions go through solnlib's
  `Logs().get_logger()`, which sets **no namespace** here and therefore writes
  an *unprefixed* file. Assuming a single scheme is what left
  `thehive_create_a_new_alert` and `thehive_run_function` uncovered -- two
  files nobody had noticed in the original report either.

`tools/checks/log_sourcetype_covered.py` derives both schemes from the source
(AST for the call sites, `alert_actions.conf` for the alert names) and fails
when a produced name matches no stanza. ⚠️ It also fails when the **shape** it
models stops existing -- if `ta_logging.py` builds its name differently, the
check refuses to answer rather than keep certifying an obsolete pattern. A
guard validating a rule that no longer holds is worse than no guard: it reports
a coverage that means nothing.

### A test that restates the production rule guards nothing

The clearest case in this repository was not a weak test, it was a **copy**.
The rule deciding *which stored value becomes the password an account
authenticates with* lived inline in `Instances.__init__` and, verbatim, inside
a manual diagnostic script. The script queried a real Splunk, was never
collected by the runner (a bare module-level function, no `TestCase`), asserted
**nothing**, and printed the first characters of a real API key to stdout.

It cost more than a missing test. It made the rule *look* exercised, so its
actual coverage -- **0 %** -- went unnoticed, on the one function in the add-on
that arbitrates secrets.

Two rules follow, and they are not the same rule:

* **Extract before testing.** A decision buried in a 234-line constructor that
  talks to Splunk cannot be tested without testing the connection. Pull it out
  as a pure function -- `common.pick_password()` is the pattern: it takes
  plain objects, returns a mapping plus the names it discarded, and **takes no
  logger**. A value that must never reach a log file is never handed to one.
* **Derive constants, never restate them.** `tests/test_pick_password_unit.py`
  reads `common.CRED_SEP` rather than spelling the separator out. A test that
  copies a constant keeps passing on the day production changes it.

`tools/checks/rule_not_duplicated.py` enforces the first half mechanically: a
marker literal belongs to exactly one file. ⚠️ It fails **both** ways -- an
extra carrier, and the owner losing the marker. A guard whose anchor has
quietly moved passes forever after and protects nothing.

⚠️ It also skips its own source. A check that spells a pattern out in its table
and then scans itself reports itself on its first run, and a guard that is red
from birth gets switched off.

### Duplication is a measurement, not a review finding

The case and the alert helpers had drifted to **419 shared lines out of
~1 050** -- 86 % -- and every review had passed. That is not carelessness:
nobody reads two files side by side, so a duplication of that size is
structurally invisible to the process meant to catch it.

What it cost, concretely: ~190 lines of attachment handling existed twice
**with the same log identifiers**, so a `[141]` in production designated two
places at once. And each copy carried the same latent crashes, so fixing one
left the other.

`tools/checks/duplication_threshold.py` compares the two files after folding
`case`/`alert` vocabulary onto a neutral name, so what it counts is structural
sameness. Its ceiling is a **ratchet** at today's measurement, exactly like a
coverage floor -- and it fails in both directions: too high catches a regrowth,
too low means the ceiling has stopped guarding and should be lowered
deliberately.

⚠️ When extracting shared code, watch for a variable the extracted block used
to bind. Removing the TTPs loop from the alert helper left `str(response)`
reading a name nothing assigned any more -- and reading it on the *failure*
path, where the message exists precisely to explain what went wrong. It was
already latent (the name was only bound when the object happened to carry
TTPs); the extraction made it unconditional. The fix is not to rebind it: it
is to make the message name the thing it reports.

### A log identifier is an address, and the registry is generated

A rendered line reads `[serial][<command_id>-<id>]`. **An identifier that names
two call sites names none** -- and it is exactly what someone reaches for when
a production incident has to be traced back to a line. Fifteen were ambiguous,
across five modules.

Two decisions worth keeping:

* **Uniqueness is required within a MODULE, not across the add-on.**
  `command_id` already namespaces the identifier per command, so a bare `id="45"`
  is unambiguous in context. Demanding global uniqueness would mean renumbering
  ~340 call sites and breaking every saved search built on one, to close an
  ambiguity that does not exist. Scope follows the defect, not the symmetry.
* **`docs/log_ids.md` is GENERATED** (`--write`), and the CI fails when it stops
  matching the code. A registry maintained by hand drifts within a release, and
  then documents a past state while looking authoritative -- which is worse
  than having none, because people trust it.

⚠️ Renumbering needs the same care as any rename: resolving `135` to `137`
created a **new** collision with an existing `137` three lines away. The check
caught it immediately, which is the point -- but the lesson is to re-run the
measurement after the fix, never to reason that the fix must have worked.

### A debug line is a log line

`thehive.py` logged `Secret length: N, ends with: XXXX` -- the last four
characters of a real API key, written to a file Splunk then indexes and anyone
with access to the index can read. The length alone tells "empty" from
"truncated" from "looks right", which is the entire reason the line exists.

Verifications print **lengths or counts, never values**. That holds for a
temporary debug line as much as for anything else: `TH_DEBUG_SECRET` was
plainly written as a one-off, and it shipped in four releases.

### Two path bootstraps, only one of which finds the vendored libraries

`thehive4py` and `cortex4py` live in `package/bin/ta_thehive_cortex/libs/`, a
directory Python knows nothing about until something puts it on `sys.path`.
There are two bootstraps and they are **not** equivalent:

* `ta_thehive_cortex_declare` (ours) adds `lib/`, `bin/ta_thehive_cortex/` and
  `bin/ta_thehive_cortex/libs/`;
* `import_declare_test` (generated by `ucc-gen`) adds `lib/` and
  `bin/TA-thehive-cortex` -- note the capitals, a directory that does not
  exist. It knows nothing of the vendored libraries.

`thehive_observables.py` and `backfill_observables.py` used the second one and
import `thehive4py` a dozen lines below. Measured: with only `bin/` on the
path, `thehive4py` does not resolve. They worked **by accident** -- an earlier
`from thehive import …` fixes `sys.path` as a SIDE EFFECT, before the line that
needs it runs.

⚠️ That is a trap, not a design, and it is armed by the most routine action
there is: **reordering imports**. Every linter does it, and the resulting
`ModuleNotFoundError` names the library rather than the reordering, sending the
reader to look at vendoring instead of at import order.

⚠️ It also nearly produced the wrong fix. `import_declare_test` looks like an
unused import -- nothing references the name -- so an unused-import sweep would
have DELETED it, breaking the modules outright instead of leaving them fragile.
A side-effect import is never unused; check what an import *does* before
concluding it does nothing.
