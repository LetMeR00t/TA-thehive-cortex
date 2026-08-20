# Release Notes - UNRELEASED

> ⚠️ This file accumulates what the **next** release must tell its users. It is
> renamed to `vX.Y.Z.md` when that version is tagged. Writing the upgrade note
> at the moment the fix is made is the only way it survives to the release: an
> upgrade instruction remembered at tagging time is an upgrade instruction lost.

## ⚠️ Manual step required after upgrading — sourcetypes of the add-on logs

### What was broken

Since **v4.0.0**, the search commands write their log as
`TA-thehive-cortex_<command>.log`, but `props.conf` still enumerated the
**v3.x** file names. The result: **23 of the add-on's 27 log files carried no
sourcetype at all**, and Splunk auto-learned one from the file name instead —
which is where `..-2`, `..-3` and `..-too_small` sourcetypes come from.

The symptom was misleading, and that is why it survived three minor versions:
the four `*_modalert` stanzas kept matching, so `props.conf` still looked
alive. Only the search commands were affected — plus, unnoticed until now, the
`thehive_create_a_new_alert` and `thehive_run_function` alert actions, which
never had a stanza of their own.

`props.conf` now matches the **shape** of the name rather than a list of
today's commands, so a command added tomorrow is covered on the day it ships.
The sourcetype `tathehivecortex:log` is also **defined** at last: until now it
was assigned everywhere and described nowhere, so line breaking and
timestamping fell back to Splunk's defaults on a format that begins with a
plain ISO date.

### 🖐️ What you must do — otherwise the fix will look like it did nothing

Once Splunk has **learned** a sourcetype it persists it into
`$SPLUNK_HOME/etc/apps/learned/local/props.conf`, as an **exact**
`[source::<full path>]` stanza. An exact-path stanza is *more specific* than
the wildcard stanza this add-on ships, so **it keeps winning** after the
upgrade.

1. Open `$SPLUNK_HOME/etc/apps/learned/local/props.conf`.
2. Remove every stanza whose source path points at a
   `TA-thehive-cortex_*.log` or a `*_modalert.log` file.
3. Restart Splunk.

Events indexed **before** the upgrade keep the sourcetype they were indexed
with — a sourcetype is decided at index time and is not rewritten
retroactively. To search across both, use the source rather than the
sourcetype:

```
index=_internal source=*TA-thehive-cortex_*.log
```

### Migration instructions of v4.0.0 are readable again

`release_notes/v4.0.0.md` disappeared in **v4.2.0**, while v4.2.0, v4.2.1 and
v4.2.2 all linked to it with a **relative** link — which resolves inside the
current tag, where the file no longer existed. Those instructions are labelled
*mandatory*, so the file is restored rather than the link rewritten: a relative
link to an absent file would break again at the next tag.


## ⚠️ Breaking: some log identifiers changed

Fifteen identifiers designated **two call sites at once**, which makes them
useless for the one thing they exist for: tracing an incident back to a line.
`135` labelled a TTPs success *and* an observable failure in the same file;
`140` a TTPs failure *and* the start of attachment processing.

Only the **second** occurrence of each was renumbered, so a search built on the
first still matches. Scope was kept minimal on purpose: gaps in the numbering
are left alone -- a gap bothers nobody, a collision does.

If you have saved searches or alerts keyed on one of these, update them:

| module | was | now | that site is |
| :--- | :--- | :--- | :--- |
| `backfill_alerts_cases.py` | `MI-ERR` | `MI-ERR-DATES` | the date range could not be parsed |
| `backfill_alerts_cases.py` | `MI-ERR` | `MI-ERR-COLLECT` | the collection itself failed |
| `backfill_audit.py` | `MI-ERR` | `MI-ERR-DATES` | the date range could not be parsed |
| `backfill_audit.py` | `MI-ERR` | `MI-ERR-COLLECT` | the collection itself failed |
| `common.py` | `S30` | `S32` | the resolved instance is returned |
| `common.py` | `S45` | `S46` | reading `thehive_max_cases` |
| `common.py` | `S54` | `S58` | reading `thehive_creation_max_retry` |
| `thehive.py` | `TH1` | `TH2` | the detected TheHive version |
| `thehive.py` | `TH30` | `TH31` | password AND API key are both empty |
| `thehive.py` | `TH40` | `TH41` | the connection test request |
| `thehive.py` | `TH50` | `TH51` | the connection succeeded |
| `thehive.py` | `TH115` | `TH118` | a case number could not be resolved |
| `thehive.py` | `TH139` | `TH141` | tasks recovered, with their filters |
| `thehive.py` | `TH140` | `TH142` | an event after size reduction |
| `thehive.py` | `TH_DEBUG_VERIFY` | `TH119` | the CA certificate path check |
| create-a-new-case | `130` | `131` | the observable was added |
| create-a-new-case | `135` | `132` | the case creation failed |
| create-a-new-case | `135` | `137` | the observable update failed |
| create-a-new-case | `140` | `139` | the TTPs update failed |
| create-a-new-case | `141` | `146` | the attachment format is unsupported |

`docs/log_ids.md` lists every identifier the add-on can emit. It is generated
from the source and the CI fails when it stops matching, so it cannot quietly
describe a past release.

## 🔒 A secret fragment no longer reaches the logs

`thehive.py` logged `Secret length: N, ends with: XXXX` at debug level -- the
last four characters of the API key, into a file Splunk indexes and anyone with
access to the index can read. It now logs the length alone, which is what
distinguishes "empty" from "truncated" from "looks right".

If you have run this add-on at debug level, those lines are in your index. They
expire with your retention; purging them earlier is a local decision.


## 🖥️ Three dashboards now do what they always claimed

### `TheHive: Statistics` displayed nothing at all

Two panels carried `depends="$always_hidden$"`, a token nothing ever set. A
hidden panel does not run its search — and those two searches were the only
producers of the tokens the main chart consumed. The chart waited for input
forever: no error, no "no results", just a pie that never filled. This has been
the case since **v4.0.0**, when the other two views were migrated and this one
was overlooked.

⚠️ A side effect worth knowing: the old date handling compared against the
literal `1970-01-01T01:00:00.000+01:00`. That sentinel only matched on a server
in UTC+1 outside summer time, so the "all time" branch was unreachable
elsewhere. The view now derives its range from the time picker directly, like
the Cases and Alerts views.

### `TheHive: Alerts` opened empty

The results panel was gated on a token that only the Action input's *change*
handler produces — and a change handler does not fire for the value an input
already carries at load. The Action selector said "LIST" while no list existed:
you had to pick another mode and come back. Its twin, the Cases view, has no
such gate, which is how two nearly identical views ended up behaving in
opposite ways.

### `Cortex: Analyzers` — REFRESH now refreshes

The only panel that runs `cortexrefreshanalyzers` and rewrites the analyzer
lookup was gated on **Debug = Yes**. Choosing Action = REFRESH turned the status
banner red on "Waiting for input" and did nothing else — the refresh ran only
for someone who also switched Debug on, with no indication anywhere that the two
were linked.

The panel is now gated on the action that asks for it. ⚠️ **The Debug control is
removed**: with the gate corrected it drove nothing at all, and a switch a user
can flip with no visible effect is worse than no switch. The panel's sub-title
also claimed the search "is used to add a new instance", which it never did.
