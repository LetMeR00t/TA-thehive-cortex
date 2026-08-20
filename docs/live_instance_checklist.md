# What still has to be tried on a real Splunk

> ⚠️ **This is the frontier of what the test suite can say.** 142 unit tests and
> 16 repository checks cover the logic. None of them can speak for what only
> exists at runtime inside Splunk: sourcetype assignment, view rendering, token
> resolution, a remote API's response shape, or the contents of a built archive.
>
> Every line below is an assertion the code makes today and that nothing in
> this repository can verify. Ordered by **what breaks silently if it is
> wrong**.
>
> Written 2026-08-20, against the work that will ship as v5.0.0.

## A. What unblocks an open ticket

### A1 — The command logs get their sourcetype back (#8)

```
index=_internal sourcetype=tathehivecortex:log
```

Must return events from the **search commands** and the **`backfill_*`**
inputs, not only from alert actions.

⚠️ **Before concluding the fix does not work.** A learned sourcetype is
persisted into `$SPLUNK_HOME/etc/apps/learned/local/props.conf` as an *exact*
`[source::<full path>]` stanza, which is more specific than the wildcard stanza
the add-on ships and therefore keeps winning. Remove those entries and restart,
or the fix will look inert.

Check as well that `[tathehivecortex:log]` breaks lines correctly: **a
multi-line traceback must stay ONE event**.

### A2 — What actually goes into the `.spl` (#10)

After `ucc-gen build`, against the **archive**:

```
tar -tzf TA-thehive-cortex-*.spl | grep -E "\.pyc|/patches/|thehive_cortex_helper|__pycache__"
```

Must return nothing. `tools/checks/package_contents.sh` does this, and has only
ever run on archives built by hand for the purpose.

### A3 — A CI run that is really red (#16)

Push a deliberately broken commit and **watch it fail**. The DoD says "proof,
not declaration": the YAML parses and the checks pass locally, but nobody has
seen the workflow execute.

## B. Repaired on 2026-08-20, never seen running

### B1 — `TheHive: Statistics` displays something

Open it. The pie must **fill**. It waited on a token nothing set, since v4.0.0.

### B2 — `TheHive: Alerts` is not empty on arrival

Land on the view and **touch nothing**: the alert table must be there. Before,
you had to pick CREATE and come back to LIST.

### B3 — `Cortex: Analyzers` — REFRESH refreshes

Choose Action = REFRESH and **change nothing else**: the lookup must be
rewritten and the banner turn "Done". ⚠️ The Debug control is **gone** — with
the gate corrected it drove nothing.

### B4 — `Audit Logs` — all five panels return something

Three of them queried a sourcetype this add-on never produced. Check the
"Modular alerts" panel and the two charts in particular, and that the event-code
chart shows `THCA-`, `THAO-`, `MI-…` codes and not only `CAA-`.

### B5 — Auto-refresh

The five panels refresh every 60 s. ⚠️ Confirm **no dropdown jumps** while it is
being used.

### B6 — ⚠️ The index-less macro: the likeliest problem in this release

```
`thehive_cortex_logs`
```

It names **no index**, by design. The add-on's logs land in `_internal`, which
is **not among the default search indexes of every role**.

**Try it with a non-admin account.** If the Audit view is empty for them while
the files exist on disk, add `index=_internal` to the macro — that is exactly
the decision this macro exists to make once instead of in nine panels.

### B7 — Form defaults

Open "Create a new case": **Severity must be MEDIUM and TLP AMBER**, not
CRITICAL and WHITE.

### B8 — The MITRE catalogue

Set `thehive_ttp_catalog_name`, then send a TTP with an **invented**
`patternId` (`T99999`). Expect `THC-122` naming the id, and **no** TTP created.
Clear the setting: everything must pass unchecked again, as before.

⚠️ Test the unavailable path too: a **non-existent** catalogue name must produce
`THC-120` and **let the TTP through**, not block it.

### B9 — Reconciled alert action parameters

`cortex_run_a_new_job` now declares `cortex_instance_id` and `analyzers`. Check
the form sends them, and that an **empty** `analyzers` produces a message rather
than an `AttributeError`.

⚠️ `sighted_field`: its shipped default forced `sighted = False` on every
observable. Confirm an observable created without touching that field is now
**sighted**.

## C. Only an instance can settle these

### C1 — The `jobs` view (#26)

`nav/default.xml` references `<view name="jobs"/>` and no `jobs.xml` is shipped.

```
ls $SPLUNK_HOME/etc/apps/*/default/data/ui/views/jobs.xml
```

or `curl` `/servicesNS/nobody/TA-thehive-cortex/data/ui/views/jobs`.

⚠️ **Remove nothing before this is answered**: if Splunk provides it, removing
the entry breaks a legitimate way in.

### C2 — The UCC-generated `dashboard` page

`globalConfig.json` declares `pages.dashboard` and `ucc-gen` generates the view
— and no nav entry mentions it. Shipped, unreachable. Run a build and list
`output/…/data/ui/views/` to learn its exact name.

### C3 — The Job SID guard (#27)

Never tried on a real Splunk, and three edges are known: a **whitespace-only**
entry, a value injected through the **URL or a drilldown**, and an **expired**
SID. Test all three SID shapes: numeric, `scheduler__…`, `subsearch_…`.

## D. Not implemented, and needing an instance anyway

### D1 — The KV store lookup (#19)

Decided, planned in the ticket, not written: KV store access goes through
Splunk's REST API, so none of it would be verifiable here.
