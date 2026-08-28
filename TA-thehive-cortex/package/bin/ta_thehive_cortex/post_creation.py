# encoding = utf-8
#
# Copyright: LGPLv3 (https://www.gnu.org/licenses/lgpl-3.0.txt)
#
"""What is attached to an object right after TheHive has created it.

⚠️ The TTPs block existed twice, ~35 lines each, differing only in the endpoint
name -- and it carried two AMBIGUOUS log identifiers:

* `135` labelled the TTPs success **and** an observable failure, in the same
  file. One identifier, two events, one of them an error.
* `140` labelled the TTPs failure **and** the start of the attachment
  processing, again in the same file.

An identifier that designates two places designates none, and it is exactly
what someone reaches for when an incident has to be traced back to a line. The
single implementation below uses `138` and `139`, free on both sides.
"""


def attach_procedures(endpoint, object_id, ttps, logger_file, url, context):
    """Create the MITRE procedures on a freshly created case or alert.

    `endpoint` is `thehive.case` or `thehive.alert`. Both declare
    `create_procedures(self, <case|alert>_id, procedures)` -- the first
    parameter carries a DIFFERENT name on each side, which is why it is passed
    positionally: naming it would reintroduce the very split this function
    exists to remove.

    ⚠️ **The object already exists when this runs.** Letting an exception out of
    here made the whole alert action die: the alert was created, the action
    exited 5, `splunkd.log` reddened on every single run, and nothing said that
    only the TTPs were missing. Measured on TheHive 5.7.5 against an account
    without `manageProcedure`, which is a server-side permission -- nothing the
    add-on can fix, and no reason to report the creation as failed.

    Returns the response, or None when the TTPs could not be attached.
    """
    try:
        response = endpoint.create_procedures(object_id, procedures=ttps)[0]
    except Exception as e:
        details = str(e)
        # The two cases deserve different messages: one is a permission to
        # grant, the other is anybody's guess and needs the raw error.
        if "manageProcedure" in details or "not authorized" in details.lower():
            logger_file.error(
                id="133",
                message=(
                    f"TTPS_REFUSED - object {object_id} was created, but its "
                    f"TTPs were REFUSED: the account is missing the "
                    f"`manageProcedure` permission on this organisation. Grant "
                    f"it in the TheHive profile; nothing else about this "
                    f"creation failed. url={url}, {context()}, ttp={ttps}"
                ),
            )
        else:
            logger_file.error(
                id="134",
                message=(
                    f"TTPS_FAILED - object {object_id} was created, but its "
                    f"TTPs could not be attached: {details}. url={url}, "
                    f"{context()}, ttp={ttps}"
                ),
            )
        return None

    if "_id" in response:
        logger_file.info(
            id="138",
            message=f"Object {object_id} was successfully updated with the TTPs on url={url}",
        )
    else:
        logger_file.error(
            id="139",
            message=(
                f"TTPs update on recent creation has failed. url={url}, "
                f"{context()}, content={response}, ttp={ttps}"
            ),
        )
    return response


def upload_attachment(endpoint, object_id, path, logger_file, url, ids, context):
    """Upload the prepared file and report what actually happened.

    ⚠️ The two copies of this block ended on `str(response)` -- a variable
    bound EARLIER in the loop, and only when the object happened to carry TTPs
    or observables. On the failure path of an object without either, the line
    meant to explain the failure raised `NameError` instead. The message now
    names the attachment result, which is the thing being reported.

    Returns the result, or None when the upload failed.
    """
    result = None
    try:
        logger_file.info(
            id=ids["uploading"],
            message=f"Processing name for the attachment from the options, result is: {path}",
        )
        result = endpoint.add_attachment(object_id, [path])
    except Exception as e:
        logger_file.error(
            id=ids["failed"],
            message=(
                f"Attachment creation has failed. url={url}, {context()}, "
                f"error={e}"
            ),
        )

    if result is not None and "_id" in result[0]:
        logger_file.info(
            id=ids["attached"],
            message=(
                f"Object {object_id} search results were successfully attached "
                f"on url={url}"
            ),
        )
    else:
        logger_file.error(
            id=ids["not_attached"],
            message=(
                f"Attachment creation on recent creation has failed. url={url}, "
                f"{context()}, content={result}"
            ),
        )
    return result
