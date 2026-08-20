# encoding = utf-8
#
# Copyright: LGPLv3 (https://www.gnu.org/licenses/lgpl-3.0.txt)
#
"""Create an object in TheHive, retrying, and say the truth about the outcome.

⚠️ This loop existed twice -- case helper and alert helper -- and both copies
carried the same two defects:

1. `if retry_count == max_retry:` after the loop. That condition tests **how
   many attempts were made**, not whether the creation succeeded. With the
   default `max_retry = 2`, an object created on the SECOND attempt lands on
   `retry_count == 2` and is reported as *"creation has failed, after retries"*
   -- while the object exists in TheHive.
2. The same line then formats `str(e)`. In Python 3 the name bound by
   `except ... as e` is **deleted when the except block ends**, so that line
   raises `NameError` -- after a successful creation. The alert action died
   having done its job.

The condition is now `if not created`, which is the question actually being
asked, and nothing outside an except block reaches the exception.
"""

from service_errors import is_duplicate, status_code as _status_code


def create_with_retry(create, max_retry, logger_file, ids, context):
    """Call `create()` until it returns, at most `max_retry + 1` times.

    `ids` names the log identifier of each outcome:
      * `duplicate`  the server says the object already exists (optional)
      * `retry`      an attempt failed and another will follow
      * `exhausted`  every attempt failed

    `context` is a callable returning the message suffix, evaluated only when
    something is actually logged -- serialising a payload nobody will read is
    the kind of cost that only shows up under load.

    Returns the created object, or None when every attempt failed.
    """
    created = None
    attempt = 0
    last_error = None

    while attempt <= max_retry and created is None:
        try:
            created = create()
        except Exception as e:
            # ⚠️ Bound OUTSIDE the except block on purpose: Python 3 unbinds
            # the `as e` name as soon as the block ends, and both copies of
            # this loop used it afterwards.
            last_error = e
            code = _status_code(e)
            duplicate = is_duplicate(e)
            if duplicate and ids.get("duplicate"):
                logger_file.warning(
                    id=ids["duplicate"],
                    message=(
                        f"Creation has failed (Duplicate found, Status={code}). "
                        f"Will retry... {context()}, error={e}"
                    ),
                )
            else:
                logger_file.warning(
                    id=ids["retry"],
                    message=f"Creation has failed. Will retry... {context()}, error={e}",
                )
        attempt += 1

    if created is None:
        logger_file.error(
            id=ids["exhausted"],
            message=(
                f"Creation has failed, after {max_retry} retries. "
                f"{context()}, error={last_error}"
            ),
        )
    return created
