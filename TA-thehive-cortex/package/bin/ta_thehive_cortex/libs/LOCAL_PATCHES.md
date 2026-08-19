# Local patches applied to the vendored libraries

`thehive4py` and `cortex4py` are **vendored**: copied into this tree rather than
installed, so they can live beside other Splunk add-ons without version
clashes. The price is that every local change is invisible — nothing in the
tree says which lines are ours and which came from upstream.

This file is that record. **Every graft goes in here, in the same commit that
adds it.** Without it, the next library upgrade overwrites local work in
silence — which has already happened once in this repository: the UCC migration
erased `cortex4py/__init__.py` and nobody noticed for years.

## Upstream baselines

| Library | Vendored base | How we know | Upstream state |
| :--- | :--- | :--- | :--- |
| `thehive4py` | **2.0.0b11** (a *beta*) | `thehive4py/__version__.py` reads `"2.0.0b11-revised"`; the `-revised` suffix is ours | Active. Latest is **2.1.0** (`Requires-Python >=3.10`), and **2.0.3** is the last stable that still declares `>=3.9` |
| `cortex4py` | **2.x, exact version unknown** | No `setup.py`, no `__version__`, no metadata — upstream keeps its version in `setup.py` only, so it was never copied in | **Archived.** There is no upstream to return to |

⚠️ The `thehive4py` divergence has been measured against upstream 2.0.3:
**50 files differ**, ~1 265 lines exist here and not upstream, ~900 exist
upstream and not here. Upstream carries `endpoints/misp.py` and
`endpoints/page_template.py` that we lack; we carry `endpoints/function.py`
that upstream does not have. Upgrading is a **reconciliation of two branches
that both moved**, not a drop-in replacement.

## Grafts

### G1 — HTTP timeout on every call *(2026-08-19)*

**Why.** Neither library passed `timeout=` anywhere. `requests` has no default,
so a server that accepts the connection and then says nothing holds the caller
until the operating system gives up — minutes. Inside Splunk that is a search
command or a modular input pinning its worker while the search merely looks
slow. It is the only proven way this add-on can block.

| File | What |
| :--- | :--- |
| `thehive4py/session.py` | `TheHiveSession.__init__` gains `timeout` (default 60) stored on the session; `request()` is **overridden** to `setdefault("timeout", self.timeout)` |
| `cortex4py/api.py` | `Api.__init__` gains `timeout` (default 60); the three explicit calls pass `timeout=`, and the two that forward `**kwargs` get `kwargs.setdefault('timeout', …)` before the call |

⚠️ **Why an override rather than per-call edits in `thehive4py`.** One method
covers *every* request the session will ever make, including endpoints the
add-on does not call today. Patching `make_request()` alone would have left a
hole open for the next endpoint someone wires up.

⚠️ **Why `setdefault` on the two `**kwargs` calls of `cortex4py`.** They could
in principle receive a timeout from their caller — but no caller passes one.
Setting the default inside bounds them whatever the caller does.

**Guarded by** `tools/checks/requests_timeout.py`, so an upgrade that drops the
graft goes red instead of silently restoring the old behaviour.

### G2 — proxy and client certificate *(pre-existing, undocumented until now)*

`thehive4py/client.py:33-34` and `thehive4py/session.py:44-45` add `proxies={}`
and `cert=None` to the signatures. ⚠️ The `TheHiveApi.__init__` docstring
(`client.py:39-53`) does **not** mention them — a sign they were added by hand
and never written up.

`cortex4py/api.py` carries the equivalent for HTTPS instances: `__verify_cert`
and `cert` propagated to all verbs (commit `1c5ab88`, « Fix issues with HTTPS
Cortex instances »).

### G3 — endpoint methods absent upstream *(pre-existing)*

Added for the Splunk modular inputs, which need counts and paginated reads that
upstream does not expose:

- `endpoints/alert.py` — `count_observables`, `get_alert_observables`,
  `count_attachments`, `get_alert_attachments`
- `endpoints/case.py` — `count_pages`, `get_case_pages`, `get_case_observables`,
  `get_case_attachments`, …
- `endpoints/task.py` — `get_tasks` (later widened with `extra_data`)
- `endpoints/function.py` — the whole file (TheHive Functions)

## Known divergence NOT yet repaired

⚠️ **`cortex4py/` has no `__init__.py`.** The empty file was lost in the UCC
migration (`c8dd4c3`). The directory therefore becomes an implicit *namespace
package*, and since `libs` is inserted at `sys.path[0]`, another Splunk add-on
shipping its own `cortex4py` can **shadow our root modules** — `api.py`,
`query.py`, `exceptions.py`, which is exactly what `cortex.py` imports.

Measured: `cortex4py/controllers/` and `cortex4py/models/` **do** have their
`__init__.py` and are therefore safe — a regular package always wins over a
namespace portion, whatever the `sys.path` order. Only the root is exposed.
Restoring an **empty** file closes it.
