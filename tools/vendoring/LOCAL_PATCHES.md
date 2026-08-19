# Local patches applied to the vendored libraries

`thehive4py` and `cortex4py` are **vendored**: copied into this tree rather than
installed, so they can live beside other Splunk add-ons without version
clashes. The price is that every local change is invisible — nothing in the
tree says which lines are ours and which came from upstream.

This file is that record, and `tools/vendoring/replay_thehive4py.py` is its
enforcement. **Every graft goes in here, in the same commit that adds it.**
Without it, the next upgrade overwrites local work in silence — which has
already happened once in this repository: the UCC migration erased
`cortex4py/__init__.py` and nobody noticed for years.

## Upstream baselines

| Library | Vendored base | How we know | Upstream state |
| :--- | :--- | :--- | :--- |
| `thehive4py` | **2.1.0** (`2.1.0-revised`) | `thehive4py/__version__.py`; the `-revised` suffix is ours | Active. 2.1.0 is the latest release |
| `cortex4py` | **2.x, exact version unknown** | No `setup.py`, no `__version__`, no metadata — upstream keeps its version in `setup.py` only, so it was never copied in | **Archived.** There is no upstream to return to |

### ⚠️ How the divergence was mis-measured, and what it really is

A first measurement compared the fork against upstream **2.0.3** and reported
~1 265 local-only lines against ~900 upstream-only ones. That figure is
misleading: it mixes **our grafts** with **upstream's own evolution** between
2.0.0b11 and 2.0.3. Comparing against the fork's TRUE base — 2.0.0b11, the
release it was actually taken from — gives **559 added and 154 removed**.

And **299 of those 713 lines, 42 %, were a single mechanical transformation**:
`TypedDict` → `Dict` and `class X(Y, total=False)` → `class X(Y)`, repeated
across eighteen `types/*.py` files. A compatibility patch for an old Python,
not a business graft.

**It is now obsolete.** Upstream 2.1.0 uses `TypedDict` from `typing` and
`NotRequired` from `typing_extensions`, and it imports cleanly on CPython
3.9.25 — verified by execution, not assumed. So the upgrade did not have to
carry it forward, and the real graft series is a third of what it looked like.

⚠️ This is why `typing-extensions` stays pinned in
`package/lib/requirements.txt` even though nothing imported it before: 2.1.0
declares it as a **hard** dependency. Removing it would have failed at import
time.

## The graft series

`patches/thehive4py/*.patch` — ten patches, generated against upstream 2.1.0,
replayable by `tools/vendoring/replay_thehive4py.py`.

| Patch | What it carries |
| :--- | :--- |
| `__version__.py` | the `-revised` suffix, so the tree never claims to be pristine upstream |
| `client.py`, `session.py` | `proxies` / `cert` in the signatures, and the HTTP timeout (G1) |
| `endpoints/alert.py` | `count_observables`, `get_alert_observables`, `count_attachments`, `get_alert_attachments` |
| `endpoints/case.py` | `count_pages`, `get_case_pages`, and the other paginated reads |
| `endpoints/task.py` | `get_tasks`, `count_case_tasks`, `get_case_tasks` |
| `endpoints/procedure.py` | `find_list_catalog`, `get_catalog` — the MITRE catalog |
| `endpoints/observable_type.py` | `list` |
| `endpoints/organisation.py` | audit log reads |
| `endpoints/__init__.py` | exports `FunctionEndpoint` |

**Files that exist only here** (no patch: upstream has no such file):
`endpoints/function.py` (TheHive Functions, which
`modalert_thehive_run_function_helper.py` depends on), `types/catalog.py`,
`types/pattern.py`.

### ⚠️ The replay checks the RESULT, not the process

A patch can apply cleanly and still leave the method missing — applied with
fuzz, or applied to the wrong place. So the script imports the rebuilt tree and
asserts that **every grafted method is actually reachable**. Proven: renaming
one method inside a patch leaves all ten applying cleanly and the replay still
refuses, naming `TaskEndpoint.get_tasks`.

It also distinguishes **a missing dependency** from **a lost graft**. Without
that pre-flight, an interpreter lacking `requests` reported every graft as
lost, which sends the reader hunting in entirely the wrong place.

## Grafts, by subject

### G1 — HTTP timeout on every call *(2026-08-19)*

Neither library passed `timeout=` anywhere. `requests` has no default, so a
server that accepts the connection and then says nothing holds the caller until
the operating system gives up — minutes. Inside Splunk that is a search command
or a modular input pinning its worker while the search merely looks slow.

- `thehive4py/session.py` — `timeout` on the session, and `request()` is
  **overridden** to inject it. One method covers every request the session will
  ever make, including endpoints nobody has wired up yet.
- `cortex4py/api.py` — `timeout` on the `Api`; three calls pass it explicitly,
  the two that forward `**kwargs` get `kwargs.setdefault` before the call.

⚠️ The timeout bounds each **attempt**, not the total wait: `DEFAULT_RETRY`
ships `total=5` with `backoff_factor=1`, so six attempts plus 0+2+4+8+16 s of
backoff. Guarded by `tools/checks/requests_timeout.py`.

### G2 — proxy and client certificate *(pre-existing)*

`client.py` and `session.py` add `proxies={}` and `cert=None`. ⚠️ The
`TheHiveApi.__init__` docstring does not mention them — a sign they were added
by hand and never written up. `cortex4py/api.py` carries the equivalent for
HTTPS instances (`1c5ab88`).

### G3 — endpoint methods absent upstream *(pre-existing)*

Counts and paginated reads the Splunk modular inputs need and upstream does not
expose. Listed in the patch table above.

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
