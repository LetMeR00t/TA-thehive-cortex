# encoding = utf-8
#
# Copyright: LGPLv3 (https://www.gnu.org/licenses/lgpl-3.0.txt)
#
"""Reading what TheHive actually said when a call failed.

⚠️ This classification was re-implemented **three times** -- in the case
creation retry, in the observables loop of the case helper, and in the
"Add observables" alert action -- each time as the same six lines pasted
verbatim, comment included. A subtle rule copied three times is a rule that
will disagree with itself: the day TheHive adds a status code, two of the three
get updated.
"""


def status_code(e):
    """TheHive carries its status either on the error or on its response."""
    code = getattr(e, "status_code", None)
    if code is None:
        response = getattr(e, "response", None)
        code = getattr(response, "status_code", None)
    return code


def is_duplicate(e):
    """The object already exists -- a warning, not an error.

    ⚠️ 400 is treated as a duplicate here, which is broad: a malformed payload
    also answers 400. Preserved deliberately -- narrowing it is a behaviour
    change that belongs to its own ticket, with a way to tell the two apart.
    """
    text = str(e).lower()
    code = status_code(e)
    return "already exists" in text or "duplicate" in text or code in (400, 409)


def response_detail(e):
    """The response body, when there is one, as a message suffix.

    Best effort on purpose: this only ever ENRICHES a message that is being
    logged anyway, so failing to read the body must not replace the real error.
    """
    response = getattr(e, "response", None)
    if response is None:
        return ""
    try:
        return f" | Response: {response.text}"
    except Exception:  # silent-except: the real error is logged by the caller
        return ""
