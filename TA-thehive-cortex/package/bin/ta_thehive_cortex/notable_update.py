# encoding = utf-8
#
# Copyright: LGPLv3 (https://www.gnu.org/licenses/lgpl-3.0.txt)
#
"""Mark a Splunk ES notable as handled once TheHive holds its alert.

Without this, a notable stays "New" and the next run of the correlation search
sends it again -- for days. TheHive refuses the copies, so nothing is wrong for
analysts, but every refusal is a failed transaction and noise in both logs.

The call is best effort by design: the alert already exists in TheHive, so a
failure here is logged and never raised. Opt-in: no status configured, no call.
"""

NOTABLE_UPDATE_PATH = "/services/notable_update"


def _simple_request(path, session_key, postargs):
    # Imported here: only present inside Splunk, and the tests inject their own.
    import splunk.rest as rest

    return rest.simpleRequest(
        path,
        sessionKey=session_key,
        postargs=postargs,
        method="POST",
        raiseAllErrors=False,
    )


def mark_notable_handled(session_key, event_id, status, logger_file,
                         request=_simple_request):
    """Set the review status of notable `event_id`. Returns True on success."""
    postargs = {
        "ruleUIDs": event_id,
        "status": str(status),
        "comment": "Sent to TheHive by TA-thehive-cortex",
    }
    try:
        response, content = request(NOTABLE_UPDATE_PATH, session_key, postargs)
    except Exception as e:  # silent-except: logged below, the alert already exists
        logger_file.warning(
            id="129", message=f"Notable {event_id} could not be updated: {e}"
        )
        return False

    code = getattr(response, "status", None)
    if code is not None and 200 <= int(code) < 300:
        logger_file.info(
            id="127", message=f"Notable {event_id} set to status {status}"
        )
        return True
    logger_file.warning(
        id="128",
        message=f"Notable {event_id} could not be updated (HTTP {code}): {content!r:.300}",
    )
    return False
