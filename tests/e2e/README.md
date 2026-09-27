# The end-to-end campaign

Replays the documented use cases against a **real Splunk** and a **real
TheHive**, checks what each side actually did, and destroys everything it
created — including after a failure.

> ⚠️ **Never run this in the public CI.** It needs real credentials, and this
> repository is public. `.github/workflows/ci.yml` runs `tests/` only, and the
> files here are named `e2e_*.py` precisely so that `-p "test_*.py"` cannot
> pick them up by accident. Two guards, because one of them is a convention.

## What it needs

| Variable | What for |
| :--- | :--- |
| `SPLUNK_USER` / `SPLUNK_PASSWORD` | an account that can create saved searches and add-on configuration |
| `THEHIVE_USER` / `THEHIVE_PASSWORD` | the account the **verification** client authenticates with |
| `E2E_TEMPLATE_INSTANCE` | id of an existing add-on instance whose host, port, uri, organisation and account the run copies |
| `E2E_SPLUNK_MGMT` | optional, defaults to `https://localhost:8089` |
| `E2E_JOB_TIMEOUT`, `E2E_THEHIVE_TIMEOUT` | optional, seconds |

Put them in the environment, or in an **unversioned** `tests/e2e/.env`
(`KEY=value` per line; the real environment always wins). There is **no
default host anywhere**: a fallback URL is how a test suite ends up writing
into somebody else's production. Missing configuration makes every test
**skip, with the reason** — never `sys.exit`.

## Running it

```bash
python -m unittest discover -s tests/e2e -p "e2e_*.py" -t .
python -m unittest discover -s tests/e2e -p "e2e_uc2*.py" -t .   # one case
```

## Cleaning up after a killed run

Every object carries an `e2e_<runid>` prefix — Splunk instance, saved search,
and the title of every TheHive alert and case. That is what lets the cleanup
be total and still safe.

```bash
python -m tests.e2e.purge            # list what is left, change nothing
python -m tests.e2e.purge --purge    # delete it
```

`--purge` re-counts afterwards and says so if anything survived. Claiming
"cleaned" while something is left is the failure this script exists to
prevent.

## What each case is for

| File | What only this can catch |
| :--- | :--- |
| `e2e_uc1_single_alert.py` | the happy path: one alert, three observables **with their types**, a string and a date custom field, one TTP |
| `e2e_uc2_several_alerts.py` | grouping by `unique_id_field`, and the per-observable `ip:<attribute>` metadata — description, tags, TLP, PAP, ioc, sighted, sighted_at, ignore_similarity |
| `e2e_uc3_correlation_case.py` | the **case** creation path, and the reserved `th_severity` / `th_tlp` / `th_pap` overrides beating the dialog — the dialog is configured with different values on purpose, so a pass can only mean the search won |
| `e2e_uc4_notable_es_mode.py` | the one decision `es_mode` actually changes: `sourceRef` taken from the notable's `event_id`. ⚠️ It deliberately does **not** create a real notable — that would write into the `notable` index, which the campaign could not clean up |
| `e2e_collection_roundtrip.py` | the **return trip**: an alert created from Splunk, collected back by the modular input into a throwaway index, checked on its content. ⚠️ Creates and drops its own index — indexed events cannot be deleted, so writing into the operator's `thehive` index would leave rows no teardown could remove |
| `e2e_uc5_thehive_function.py` | pushing to a TheHive **Function**. Skips **with the reason** unless `E2E_THEHIVE_FUNCTION` is set: Functions are licensed and `listFunction` is empty on the lab instance |
| `e2e_password_auth_mode.py` | the `password` authentication mode, on an account of its own (#38): either the alert is created, or the action says in terms of the **mode** (`TH111`) why TheHive refused it — never a bare `TH110`. ⚠️ The only case that writes `THEHIVE_USER`/`THEHIVE_PASSWORD` into Splunk's credential store; the account carries the run prefix and is deleted with the run |

⚠️ Asserting that the alert **exists** proves almost nothing. The defects that
hurt in this add-on do not fail: the alert is created, Splunk reports success,
and one field is missing. Every case here asserts on **content** — the value
*and* the type of each observable, each custom field, each TTP — and on what
the alert action wrote in its own log.

## Five things measured here that are worth knowing

- The run creates its own **instance** but reuses the template's **account**.
  The add-on's `password` authentication mode sends HTTP Basic, and TheHive
  reads Basic as `user:password[:otp]`, splitting on **every** `:` (scalligraph
  `BasicAuthSrv`, 5.7.5): a password containing `:` is truncated and answered
  `401`, while `/api/v1/login` accepts it. Basic itself is on by default.
- The alert action's log is read by **pid**, not by search name. Only the
  framework's lines name the saved search; the add-on's own lines — its errors
  included — carry an `exec_id` and the pid. Filtering on the name made
  `assert_clean_log` blind to every add-on error, in every case, until
  2026-09-27.
- TheHive listings are filtered **server-side** with `_startsWith`. Listing and
  filtering in Python looked identical on alerts and quietly failed on cases:
  the lab organisation holds more than 3 600 of them, `listCase` does not
  promise the newest first, and a page of 500 did not contain the case that had
  just been created — the campaign reported "no case" about a case its own log
  said it had created, and then failed to clean it up.
- Observables are **polled**, not read the instant the alert appears. The
  add-on creates the alert first and attaches observables afterwards, one API
  call each: measured, one second apart. Reading too early produces a flake
  that looks exactly like the silent loss this campaign exists to catch.
- The saved search is created with an explicit `dispatch.ttl`. Without it the
  dispatch directory of a manually triggered saved search is reaped before the
  alert action opens `results.csv.gz`, and the action reports *"No search
  result"* — an `IOError` described as an empty search, on a job that really
  did return its rows.
