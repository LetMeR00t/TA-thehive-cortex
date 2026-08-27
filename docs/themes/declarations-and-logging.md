# Declarations that must resolve, and what a log line costs

> Trigger: read this when you touch a declaration split across two files, a log identifier, or a debug line.

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
