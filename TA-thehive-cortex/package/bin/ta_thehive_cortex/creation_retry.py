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


def create_with_retry(create, max_retry, logger_file, ids, contexte):
    """Call `create()` until it returns, at most `max_retry + 1` times.

    `ids` names the log identifier of each outcome:
      * `duplicate`  the server says the object already exists (optional)
      * `retry`      an attempt failed and another will follow
      * `exhausted`  every attempt failed

    `contexte` is a callable returning the message suffix, evaluated only when
    something is actually logged -- serialising a payload nobody will read is
    the kind of cost that only shows up under load.

    Returns the created object, or None when every attempt failed.
    """
    cree = None
    tentative = 0
    derniere_erreur = None

    while tentative <= max_retry and cree is None:
        try:
            cree = create()
        except Exception as e:
            # ⚠️ Bound OUTSIDE the except block on purpose: Python 3 unbinds
            # the `as e` name as soon as the block ends, and both copies of
            # this loop used it afterwards.
            derniere_erreur = e
            code = _code_de_statut(e)
            texte = str(e).lower()
            doublon = (
                "already exists" in texte
                or "duplicate" in texte
                or code in (400, 409)
            )
            if doublon and ids.get("duplicate"):
                logger_file.warning(
                    id=ids["duplicate"],
                    message=(
                        f"Creation has failed (Duplicate found, Status={code}). "
                        f"Will retry... {contexte()}, error={e}"
                    ),
                )
            else:
                logger_file.warning(
                    id=ids["retry"],
                    message=f"Creation has failed. Will retry... {contexte()}, error={e}",
                )
        tentative += 1

    if cree is None:
        logger_file.error(
            id=ids["exhausted"],
            message=(
                f"Creation has failed, after {max_retry} retries. "
                f"{contexte()}, error={derniere_erreur}"
            ),
        )
    return cree


def _code_de_statut(e):
    """TheHiveError carries its status either directly or on a response."""
    code = getattr(e, "status_code", None)
    if code is None:
        reponse = getattr(e, "response", None)
        code = getattr(reponse, "status_code", None)
    return code
