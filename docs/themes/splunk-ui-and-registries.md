# The Splunk UI, its registries and its panels

> Trigger: read this when you touch a dashboard, a panel, a generated registry, or an identifier carried as data.

### An identifier can travel as DATA

`log_ids_unique.py` first read only `id=` on logger calls, and was blind to the
identifiers passed in the `ids={...}` mapping the shared helpers take. It
therefore missed `125` used both as the `exhausted` identifier and as a success
line in the same file -- a collision **shipped in v4.2.2**, not introduced by
the refactor, but carried forward by it.

A guard that scans call sites misses everything passed as an argument. When a
value moves from a literal to a parameter, every check that watched the literal
goes quiet without failing.

### The code is English, including the identifiers

Comments and docstrings were English from the start; the identifiers were not.
`si_vide`, `etiquettes`, `horodatage`, `contexte`, `derniere_erreur` shipped in
`package/bin/`. An independent review named it for what it is: a **permanent**
maintenance cost in a public, English-speaking repository, for no benefit -- the
next contributor has to translate before they can read.

278 identifiers were renamed. Two things worth keeping from how it went:

⚠️ **Translate identifiers, never prose.** A word-boundary substitution over a
file will happily turn "la valeur attendue" into "la value attendue" inside a
comment. Check the diff for damaged sentences, not just for a green suite.

⚠️ **Some names belong to the framework.** Renaming a test helper to `run`
silently overrode `unittest.TestCase.run`, so `setUp` never executed and the
failure surfaced as a missing attribute three frames away. `run`, `id`, `debug`,
`fail` and friends are reserved on a `TestCase`; a rename that lands on one
replaces the framework's own method without a word.

### A registry a machine writes, an interpretation a human writes

`docs/log_ids.md` has two halves and the split is deliberate:

* **generated**, between the `INVENTAIRE` markers: every code the source emits.
  A machine keeps this exhaustive, because a hand-maintained inventory drifts
  within a release and then documents a past state while looking authoritative.
* **hand-written**, above the markers: what a code *means*, and for the ones
  that signal a problem, what to do next. No generator can produce that — the
  message text says what happened, not what to check.

⚠️ The check closes the gap: **every code logged at error or warning level must
be explained by name in the hand-written part.** A new code shipped without an
explanation turns the build red. So the document is allowed to be incomplete —
it is not allowed to quietly stop matching reality.

It earned its keep on the first run, twice. It found five error codes that were
emitted and explained nowhere. And it caught a mistake in the interpretation
itself: `126` means "creation failed, will retry" in one helper and "the server
returned no id" in the other, and the first draft conflated them. A code without
its component prefix designates nothing — which is why the check accepts
`THCC-135` as covering `135` for that module, and why the document is written
that way.

### A panel that cannot appear says nothing about it

Two views shipped dead for four releases, and neither logged a thing.

`thehive_statistics.xml` hid two panels behind `depends="$always_hidden$"`, a
token nothing ever set. ⚠️ **A hidden panel does not dispatch its search** — and
those two searches were the only producers of the tokens the main chart
consumed. The chart waited for input forever: no error, no "no results", just a
pie that never filled.

`thehive_alerts.xml` gated its results panel on a token set by
`<condition value="list">`, while the input's own `<default>` is already
`list`. A `<change>` does not fire for the value an input already carries at
load, so the panel was absent on arrival and appeared only after the user
picked another mode and came back. Its twin `cases.xml` has no such gate — two
files 86 % identical, behaving in opposite ways.

Two rules:

* **A token consumed by a panel must be produced by something that always
  runs.** A view-level `<search id=…>` runs; a panel's search runs only if the
  panel is visible. Putting a producer inside a hidden panel is a cycle.
* **State the load-time truth in `<init>`, next to the default it mirrors.** A
  `<change>` describes transitions, never the starting point.

`tools/checks/views_are_reachable.py` enforces both, plus the XML comment trap
below. ⚠️ Note how narrowly the second rule is expressed: a token set inside a
`<change>` is normally deliberate — a panel that appears once you pick "CREATE"
is the whole point of a mode form. The check reports **only** the mismatch with
the input's default value. Its first, broader version produced 22 findings of
which 21 were correct behaviour, which is a guard on its way to being switched
off.

⚠️ And the third trap, hit twice in one hour while writing those fixes: **a
double dash is illegal inside an XML comment** and makes the whole view
unparseable. Worse, the naive fix hits it again — a substitution replacing `--`
everywhere destroys the `<!--` and `-->` delimiters themselves. Sanitise the
comment *body*, never the whole match.

⚠️ **`git checkout <file>` to prove a guard works also restores the defect the
guard was written for.** Twice in one session: the check went red as intended,
and the "restore" wiped an hour of uncommitted work in the same file. Prove a
guard red on a COPY, or commit first — a demonstration must not be able to
destroy what it demonstrates.

### The frontier of what the suite can prove

`docs/live_instance_checklist.md` lists everything that only a running Splunk
can answer: sourcetype assignment, view rendering, token resolution, a remote
API's response shape, the contents of a built archive.

⚠️ Keep it current as work lands. A claim made in a release note is an assertion
about behaviour; if nothing here can check it, it belongs on that list. The
alternative is discovering the gap the way this repository already has — a
dashboard dead for four releases, logging nothing.

### Auto-refresh belongs to panels reading the index, never to inputs

A refreshing panel is useful. A refreshing **dropdown** makes the analyst's
selection jump under their fingers every cycle — and a substitution applied to
"every panel search" hits the inputs declared *inside* panels, which is how
three of them got one here.

And never on a view that calls the TheHive API: 60 s means one HTTP round-trip
per minute **per open tab**, and on a `sendalert` panel it would create an
object every cycle. `audit_logs.xml` reads the Splunk index, so its cycles cost
the remote server nothing — that is why it is the only one.

### A setting read and dropped looks wired from every angle

`thehive_ttp_catalog_name` was on the Settings page, had a getter, the getter
was called, and the value was placed into the `defaults` dictionary. Every hop
existed except the last: **nothing read it back**. A user could change it, save,
and see nothing happen.

Meanwhile a TTP's MITRE `patternId` was validated by `startswith("T")` — which
accepts `T`, `TOTO` and `T99999`. The setting that did nothing existed precisely
for the check that was missing; each hid the other.

`tools/checks/settings_are_used.py` enforces the narrow decidable rule: every
key placed into a `defaults` dictionary must be read as `defaults["KEY"]`
somewhere. That dictionary is the add-on's own hand-off between "I read the
configuration" and "I use it", so a key that enters and never leaves is a value
dropped on the floor.

⚠️ Its blind spot, measured on 2026-10-24: a setting read through the alert
actions' `helper.get_global_setting()` never enters `defaults`, so the check
cannot see it. `splunk_es_alerts_index` is exactly that -- read into the alert
arguments since at least v3.9.0, consumed by nothing, and green here.

⚠️ And when the check *cannot* be performed, do not turn it into a rejection.
An unreachable catalogue forwards the ids with a warning: refusing would let an
outage on our side silently drop legitimate data — punishing the user for our
own failure. `None` ("I could not check") and the empty set ("the catalogue is
empty") are different answers, and the code says so explicitly.

### `X | Y` in an annotation is an expression, evaluated at import

`set | None` needs Python 3.10. Splunk ≤ 10.1 serves 3.9 only, so a module
using it raises `TypeError` **while loading** — and it does not fall alone:
everything importing it goes down too. One new file broke four test modules and
both creation alert actions.

`from __future__ import annotations` makes annotations strings and the problem
disappears. The 3.9/3.13 matrix caught this in seconds, which is exactly what it
exists for — no separate check was added, because one guard finding it reliably
is enough.

⚠️ Related, and self-inflicted twice in one session: **new code written after a
translation pass arrives in French again.** The rule is not "translate once", it
is "the repository is English"; check the file you just created, not only the
ones you swept.

## A Simple XML view you changed is not done until it ran

*A guard that was never seen working is not a guard.* Nothing here executes a
dashboard: the XML parses, the checks pass, the tests are green — and none of
that says a token was set, a panel appeared, or a search returned. Token
resolution, `<change>` handlers, `<init>`, `depends` / `rejects` and `| loadjob`
exist only inside a running Splunk.

So: **a modified Simple XML view stays open until it has been exercised on a
real instance.** Not "should" — the ticket does not close.

### The protocol, reusable as is

For each token the view gates a panel on, walk these four, in this order:

1. **Nominal** — the legitimate value. The panel appears. *(If this fails,
   nothing else you test means anything.)*
2. **Empty, then blanks** — clear the field, then type a single **space**.
   ⚠️ The second is the one that gets missed: `$value$==""` is false for `" "`,
   so the token is set and the panel unlocks on a value that is not one.
3. **Injected** — load the view with the token in the **URL**
   (`?form.create_sid=whatever`), and again through a drilldown if one leads
   here. A `<change>` handler does **not** fire for a value the input already
   carries, so without an `<init>` unsetting it, the guard is simply walked
   around.
4. **Stale** — a value that was valid and no longer is (an expired search job,
   a deleted object). Well-formed is not the same as still there, and the
   failure that follows names neither.

Record what you saw, per step, in the ticket — "tested on a real instance" with
no detail is indistinguishable from "opened the page once".
