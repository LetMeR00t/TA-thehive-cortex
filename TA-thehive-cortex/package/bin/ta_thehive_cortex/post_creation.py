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


def attach_procedures(endpoint, object_id, ttps, logger_file, url, contexte):
    """Create the MITRE procedures on a freshly created case or alert.

    `endpoint` is `thehive.case` or `thehive.alert`. Both declare
    `create_procedures(self, <case|alert>_id, procedures)` -- the first
    parameter carries a DIFFERENT name on each side, which is why it is passed
    positionally: naming it would reintroduce the very split this function
    exists to remove.
    """
    reponse = endpoint.create_procedures(object_id, procedures=ttps)[0]

    if "_id" in reponse:
        logger_file.info(
            id="138",
            message=f"Object {object_id} was successfully updated with the TTPs on url={url}",
        )
    else:
        logger_file.error(
            id="139",
            message=(
                f"TTPs update on recent creation has failed. url={url}, "
                f"{contexte()}, content={reponse}, ttp={ttps}"
            ),
        )
    return reponse


def upload_attachment(endpoint, object_id, chemin, logger_file, url, ids, contexte):
    """Upload the prepared file and report what actually happened.

    ⚠️ The two copies of this block ended on `str(response)` -- a variable
    bound EARLIER in the loop, and only when the object happened to carry TTPs
    or observables. On the failure path of an object without either, the line
    meant to explain the failure raised `NameError` instead. The message now
    names the attachment result, which is the thing being reported.

    Returns the result, or None when the upload failed.
    """
    resultat = None
    try:
        logger_file.info(
            id=ids["uploading"],
            message=f"Processing name for the attachment from the options, result is: {chemin}",
        )
        resultat = endpoint.add_attachment(object_id, [chemin])
    except Exception as e:
        logger_file.error(
            id=ids["failed"],
            message=(
                f"Attachment creation has failed. url={url}, {contexte()}, "
                f"error={e}"
            ),
        )

    if resultat is not None and "_id" in resultat[0]:
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
                f"{contexte()}, content={resultat}"
            ),
        )
    return resultat
