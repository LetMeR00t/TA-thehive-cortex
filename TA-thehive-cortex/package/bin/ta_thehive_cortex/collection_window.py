# encoding = utf-8
#
# Copyright: LGPLv3 (https://www.gnu.org/licenses/lgpl-3.0.txt)
#
"""The time window a live input collects next, remembered across runs.

5.0.0 asked for exactly the last interval on every run and kept no state. A run
that failed, hung, was skipped (splunkd restarting, the previous run still
going) or simply asked a little too early -- TheHive had not yet made the
newest entries visible -- lost its window for good: no later run asks for it
again.

Each pull of a live input now has a WATERMARK: the end of the last window it
collected completely. A run collects ``[watermark, now - lag)``; TheHive's
``_between`` is from-inclusive and to-exclusive, so back-to-back windows cover
time exactly once. The watermark moves only after every event of the window
was written: a failed run leaves it where it was and the next run collects the
missed time, at most ``max_catchup`` seconds per run.

The watermarks live in the KV store, so a search head cluster shares them. An
instance with the KV store disabled (some heavy forwarders) keeps them in the
input's checkpoint directory instead; one whose KV store is not ready yet
skips the run (see ``store_choice``). Splunk runs a modular input on EVERY member of a cluster (``run_only_one`` is
documented as not supported yet), so only the captain collects; the member
that becomes captain carries on from the same watermark.
"""

from __future__ import annotations

import json
import os
import re

COLLECTION = "thehive_cortex_checkpoints"
APP = "TA-thehive-cortex"
DEFAULT_LAG_S = 60
DEFAULT_MAX_CATCHUP_S = 6 * 3600


def plan(previous_end_ms, now_s: float, interval_s: int, lag_s: int = DEFAULT_LAG_S,
         max_catchup_s: int = DEFAULT_MAX_CATCHUP_S):
    """Return the window ``(start_ms, end_ms)`` to collect, or None when nothing is due yet.

    Without a watermark (first run, or after a reset) the window is one
    interval ending ``lag`` seconds ago -- what 5.0.0 collected, a lag later.
    """
    end_ms = int((now_s - lag_s) * 1000)
    start_ms = int(previous_end_ms) if previous_end_ms is not None else end_ms - int(interval_s) * 1000
    end_ms = min(end_ms, start_ms + int(max_catchup_s) * 1000)
    return (start_ms, end_ms) if end_ms > start_ms else None


def should_collect(shc_mode, captain_label, server_name):
    """Decide from the cluster state whether this instance collects. Returns ``(bool, reason)``.

    Not clustered (a heavy forwarder, a standalone search head): collect.
    A cluster member: collect only when it is the captain; when the captain is
    unknown (an election is going on), do not -- the watermark waits for the
    next run instead of two members collecting the same window.
    """
    if shc_mode in (None, "", "disabled"):
        return True, "not in a search head cluster"
    if not captain_label:
        return False, "search head cluster without a known captain"
    if captain_label == server_name:
        return True, "captain of the search head cluster"
    return False, f"search head cluster member, captain is {captain_label}"


def store_choice(kv_disabled, kv_status):
    """Decide where this instance keeps the watermarks. Returns ``(store, reason)``, store in kv / file / wait.

    ⚠️ The state is read from Splunk BEFORE any checkpointer is opened. solnlib's
    KV store checkpointer opens without error when the KV store is disabled and
    fails only on its first read (HTTP 503), so "try the KV store, fall back on
    error" never fell back: on a heavy forwarder with the KV store disabled every
    run failed and nothing was collected.

    - KV store disabled in server.conf (some heavy forwarders): the input's
      checkpoint directory, on this instance only.
    - Enabled but not ready (starting after a restart, or failed): this run does
      not collect. A file fallback here would start a second watermark that the
      KV one later contradicts; instead the KV watermark waits and the next run
      catches up.
    """
    if _is_true(kv_disabled):
        return "file", "KV store disabled on this instance"
    if kv_status == "ready":
        return "kv", "KV store ready"
    return "wait", f"KV store not ready (status={kv_status or 'unavailable'})"


def _is_true(value) -> bool:
    """A Splunk boolean: JSON gives True/False, a .conf file 1/true/yes/..."""
    return value is True or str(value).strip().lower() in ("1", "true", "t", "yes", "y", "on")


def setting(input_item, name: str, default: int) -> int:
    """An optional integer input setting; empty or invalid means the default."""
    try:
        value = int(str(input_item.get(name) or "").strip())
    except ValueError:
        return default
    return value if value >= 0 else default


def _key(stanza: str, pull: str) -> str:
    """A KV store _key for one pull of one input: stable and URL-safe."""
    return re.sub(r"[^A-Za-z0-9_.-]", "_", f"{stanza}__{pull}")


class CollectionWindows:
    """Watermarks of one input run: where each pull continues, and whether this instance collects at all."""

    def __init__(self, inputs_metadata: dict, stanza: str, input_item: dict, logger_file):
        self._session_key = inputs_metadata.get("session_key")
        self._checkpoint_dir = inputs_metadata.get("checkpoint_dir")
        self._stanza = stanza
        self._logger = logger_file
        self.interval_s = setting(input_item, "interval", 60)
        self.lag_s = setting(input_item, "lag_seconds", DEFAULT_LAG_S)
        self.max_catchup_s = setting(input_item, "max_catchup_seconds", DEFAULT_MAX_CATCHUP_S)
        self._store = None

    def collect_here(self) -> bool:
        """True when this instance collects and its watermark store is usable; logs the reason when not."""
        collect, reason = should_collect(*self._cluster_state())
        if not collect:
            self._logger.info(id="SKIP", message=f"input={self._stanza} not collected here: {reason}")
            return False
        return self._store is not None or self._open_store()

    def next(self, pull: str, now_s: float):
        """The window to collect for ``pull`` (e.g. ``audit``, ``alerts:_updatedAt``), or None."""
        state = self._get(pull)
        span = plan(state.get("end") if state else None, now_s, self.interval_s, self.lag_s, self.max_catchup_s)
        if span:
            behind_s = round(now_s - span[0] / 1000)
            self._logger.info(id="WIN", message=f"input={self._stanza} pull={pull} window={span[0]}-{span[1]} behind_s={behind_s}"
                              + (" catch-up" if span[1] < int((now_s - self.lag_s) * 1000) else ""))
        return span

    def done(self, pull: str, span, events: int) -> None:
        """Move the watermark of ``pull`` to the end of ``span``: call only once every event was written."""
        try:
            self._put(pull, {"end": span[1], "input": self._stanza, "pull": pull})
        except Exception as e:
            self._logger.error(id="CKPT", message=f"input={self._stanza} pull={pull} watermark not saved, the next run collects this window again: {type(e).__name__}: {e}")
            return
        self._logger.info(id="DONE", message=f"input={self._stanza} pull={pull} events={events} watermark={span[1]}")

    # --- storage: KV store, else (KV store disabled) the input's checkpoint directory ------------

    def _open_store(self) -> bool:
        """Open the store ``store_choice`` names; False (logged) when this run must not collect."""
        store, reason = store_choice(*self._kv_state())
        if store == "wait":
            self._logger.warn(id="KVWAIT", message=f"input={self._stanza} not collected this run: {reason}; the watermark waits and the next run catches up")
            return False
        try:
            self._store = self._make_store(store)
        except Exception as e:
            self._logger.warn(id="KVOPEN", message=f"input={self._stanza} not collected this run: the {store} watermark store could not be opened ({type(e).__name__}); the next run catches up")
            return False
        if store == "file":
            self._logger.warn(id="KV", message=f"input={self._stanza} {reason}: watermarks kept in the checkpoint directory of this instance only")
        return True

    def _make_store(self, store: str):
        if store == "kv":
            from solnlib.modular_input.checkpointer import KVStoreCheckpointer
            return KVStoreCheckpointer(COLLECTION, self._session_key, APP)
        from solnlib.modular_input.checkpointer import FileCheckpointer
        os.makedirs(self._checkpoint_dir, exist_ok=True)
        return FileCheckpointer(self._checkpoint_dir)

    def _open(self):
        if self._store is None and not self._open_store():
            raise RuntimeError("no usable watermark store on this instance")
        return self._store

    def _get(self, pull: str):
        state = self._open().get(_key(self._stanza, pull))
        return json.loads(state) if isinstance(state, str) else state

    def _put(self, pull: str, state: dict) -> None:
        self._open().update(_key(self._stanza, pull), state)

    def _rest_content(self, path) -> dict:
        """The first entry's content of a REST endpoint of this instance; {} on any non-200 answer."""
        import splunk.rest as rest
        response, body = rest.simpleRequest(path, sessionKey=self._session_key, getargs={"output_mode": "json"}, raiseAllErrors=False)
        if int(response.status) != 200:
            return {}
        entries = json.loads(body).get("entry", [])
        return entries[0].get("content", {}) if entries else {}

    def _cluster_state(self):
        """``(shc_mode, captain_label, server_name)`` of this instance, from its own REST API."""
        mode = self._rest_content("/services/shcluster/config").get("mode")
        if mode in (None, "", "disabled"):
            return mode, None, None
        return mode, self._rest_content("/services/shcluster/captain/info").get("label"), self._rest_content("/services/server/info").get("serverName")

    def _kv_state(self):
        """``(kv_disabled, kv_status)`` of this instance. A disabled KV store answers its status endpoint with 503."""
        if _is_true(self._rest_content("/services/configs/conf-server/kvstore").get("disabled")):
            return True, None
        current = self._rest_content("/services/kvstore/status").get("current")
        return False, current.get("status") if isinstance(current, dict) else None
