# The repository checks, and what each one exists to prevent

> Trigger: read this when you add, change or silence a check under `tools/checks/`, or one of them fails.

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
python tools/checks/complexity_ceiling.py
python tools/checks/module_size_and_cycles.py
python tools/checks/secrets_never_logged.py
python tools/checks/vendored_grafts_present.py
python tools/checks/log_ids_unique.py
python tools/checks/vendored_path_bootstrap.py
python tools/checks/unused_imports.py
python tools/checks/local_imports_resolve.py
python tools/checks/views_are_reachable.py
python tools/checks/settings_are_used.py
python tools/checks/alert_action_params.py
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
`tools/vendoring/LOCAL_PATCHES.md`); this check exists so the
next upgrade cannot quietly undo the patch.

### `complexity_ceiling.py`

Per-function cyclomatic complexity, as a ratchet. `parse_events` reached
**CC 126** in one function — and nobody ever added complexity to it, everybody
added a field type, one `elif` at a time, each reasonable on its own day.

The ceilings in `CEILINGS` are **measured** values, not ambitions: a check that
is red from birth gets switched off, after which it guards nothing. Anything
not named there gets the default of 15. Raising a ceiling means editing the
file, which is the point — the next `elif` has to argue for itself in a diff.

⚠️ It also fails when a ceiling names a function that no longer exists. A
ceiling for a renamed function protects nothing, and silently.

```bash
python tools/checks/complexity_ceiling.py --report   # every function, worst first
```

⚠️ **When you extract, move the floors and ceilings with the code.** A
`coverage_floors.py` entry left on the shrunken function goes on reporting a
comfortable green over what is now fifteen lines, while the branching it was
written to watch sits somewhere else with no floor at all. That happened here,
and it was caught by reading the number rather than the colour.

### `module_size_and_cycles.py`

Two guards that fail the same way from a diff: a **line ceiling** per module,
and the **absence of an import cycle**.

`thehive.py` is at 1293 lines and `common.py` at 893. Neither arrived there in
a commit anyone would have questioned — a file grows one line at a time, and
nobody sees it cross 400. The ceilings for those files are their measured size,
so they are debts with a number on them; everything else gets 400.

The cycle half ships with the split on purpose: `a imports b imports a` runs
fine until the day an import moves to the top of a module, and splitting a
large file is exactly when that happens.

⚠️ Files generated by `ucc-gen` are excluded by name, and not out of taste: the
next build overwrites anything changed there, so a fix disappears without a
trace and the defect comes back looking new.

### `secrets_never_logged.py`

A log message may say whether a credential is **there**. Nothing else.

This add-on shipped, **in four versions**, a debug line carrying the last four
characters of the API key — into a file Splunk indexes, that any account with
access to the internal index can read, and that travels verbatim into a
`splunk diag`: the one file people send to a third party. It was then reduced to
the key's **length**, which looks harmless and is not. A length says *which* key
is in play, across every log, ticket and screenshot it reaches. So does a
prefix, a suffix, a fingerprint, a hash.

The rule is therefore narrow: the only reduction allowed is a **boolean of
presence** — `bool(x)`, or a comparison with `None`. The check reads
expressions, not prose, so a message that merely says "API Key" is not a match.

A legitimate case is declared **on the call**, with its reason:

```python
self.logger_file.debug(
    id="S4",
    # credential-free: the KEYS of this mapping are account names, never values.
    message=f"Passwords retrieved for accounts: {list(self._passwords.keys())}",
)
```

⚠️ Never an allow-list kept somewhere else: it is read by nobody and outlives
the reason it was written for. And the marker is searched across the whole call,
not one line — a message long enough to be a finding is long enough to be
wrapped, and refusing a reason written above would get you no reason at all.
