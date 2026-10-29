# encoding = utf-8
#
# Copyright: LGPLv3 (https://www.gnu.org/licenses/lgpl-3.0.txt)
#
"""How long a call to TheHive may take before it fails, and which failures are retried.

thehive4py's default retries every error 5 times, connect AND read timeouts
included, each waiting the full HTTP timeout (60 s by default). An unreachable
TheHive behind a proxy that drops packets therefore held a run for about 6.5
minutes before it failed, and a query TheHive was too slow to answer was sent
six times in a row, adding load to a server that was already struggling.

- Connecting gets its own short timeout: a server that does not accept the
  connection within CONNECT_TIMEOUT_S will not later.
- A read timeout is not retried: the request reached TheHive, so repeating it
  repeats the work (and, for a POST that creates an object, may create it
  twice). A live input collects the same window again on its next run.
- Connection errors and 500/502/503/504 answers are still retried with
  backoff, as before: those are the short blips a retry is for.
"""

from __future__ import annotations

from urllib3 import Retry

CONNECT_TIMEOUT_S = 10.0
RETRIES = 5


def timeout(http_timeout_s) -> tuple:
    """``(connect, read)`` seconds for requests; the setting stays the read timeout."""
    read_s = float(http_timeout_s)
    return (min(CONNECT_TIMEOUT_S, read_s), read_s)


def retries() -> Retry:
    """thehive4py's default retry, without retrying read timeouts."""
    return Retry(
        total=RETRIES,
        connect=RETRIES,
        read=0,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        raise_on_status=False,
    )
