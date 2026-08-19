# encoding = utf-8
#
# Copyright: LGPLv3 (https://www.gnu.org/licenses/lgpl-3.0.txt)
#
"""Build the file that carries the Splunk search results to TheHive.

⚠️ This code existed **twice**, ~190 lines each, in
`modalert_thehive_create_a_new_case_helper.py` and
`modalert_thehive_create_a_new_alert_helper.py`, differing in 13 lines out of
195 -- and using the **same log identifiers** on both sides. A `[MA-THCA-141]`
in production therefore designated two different places at once, which is a
diagnosis that cannot be made.

Duplication of that size is invisible in a diff review: nobody reads two files
side by side. It only shows up in a measurement.

What stays in the callers is what genuinely differs: the endpoint
(`thehive.case` vs `thehive.alert`) and the messages that name the object.
"""

import csv
import gzip
import hashlib
import json
import os
import shutil
import tempfile


class AttachmentError(Exception):
    """A requested attachment cannot be produced.

    ⚠️ Raised where the previous code fell off the end of an if/elif chain and
    then crashed on the next line -- `os.rename(None, ...)` for an unsupported
    format, `open(None, "rb")` for an unsupported mode. The error was logged
    first, so the log said one thing and the traceback another. Naming the
    failure means the caller can report it instead of dying on a TypeError
    that points at the wrong line.
    """


#: attach_results: 0 none, 1 gzip as-is, 2 uncompressed CSV, 3 JSON
MODES = {1: ".csv.gz", 2: ".csv", 3: ".json"}

#: attach_format: how the final file is named
FORMATS = {0: "prefix+id", 1: "id", 2: "prefix+sha256", 3: "sha256"}


def build_attachment(
    results_file,
    attach_results,
    attach_format,
    attachment_prefix,
    object_id,
    logger_file,
):
    """Produce the file to attach, in a temporary directory of its own.

    Returns `(tmp_directory, chemin_final)`. The caller uploads the file and is
    responsible for `shutil.rmtree(tmp_directory, ignore_errors=True)` -- the
    directory must outlive this call, since the upload reads from it.

    ⚠️ The temporary directory is created by `mkdtemp` per invocation, and that
    is not cosmetic: the system temp dir is shared by every alert action worker
    (on Windows it resolves to C:\\WINDOWS\\TEMP for the splunkd SYSTEM
    service), so a fixed name such as `results.json` collided between
    overlapping runs -- Errno 13, then Errno 2.
    """
    if attach_results not in MODES:
        raise AttachmentError(
            f"attach_results={attach_results} is not a supported mode "
            f"(expected one of {sorted(MODES)})"
        )

    logger_file.debug(id="141", message=f"Processing results file: {results_file}")

    results_file_name = os.path.basename(results_file).split(".")[0]
    tmp_directory = tempfile.mkdtemp(prefix="thc_attach_")
    file_ext = MODES[attach_results]
    avant_renommage = os.path.join(tmp_directory, results_file_name + file_ext)

    if attach_results == 1:
        # Copy the gzip Splunk produced, without touching it.
        shutil.copyfile(results_file, avant_renommage)
    else:
        logger_file.warn(
            id="145",
            message=f"Uncompressing Splunk search results file located at {results_file}...",
        )
        entetes, lignes = _lire_les_resultats(results_file, logger_file)
        if attach_results == 2:
            _ecrire_csv(avant_renommage, entetes, lignes)
        else:
            _ecrire_json(results_file, entetes, avant_renommage)

    with open(avant_renommage, "rb") as f:
        sha256 = hashlib.sha256(f.read())

    apres_renommage = os.path.join(
        tmp_directory,
        _nom_final(attach_format, attachment_prefix, object_id, sha256, file_ext,
                   logger_file),
    )
    os.rename(avant_renommage, apres_renommage)
    return tmp_directory, apres_renommage


def _lire_les_resultats(results_file, logger_file):
    """Read the gzip CSV Splunk wrote. Returns (headers, rows)."""
    try:
        with gzip.open(results_file, "rt") as f:
            csvreader = csv.reader(f)
            entetes = next(csvreader)
            return entetes, [row for row in csvreader]
    except Exception as e:
        logger_file.error(id="148", message=f"Error during uncompressing process: {e}")
        # ⚠️ The previous code carried on with headers=None and rows=None, and
        # died a few lines later inside csv.writerow -- a TypeError blaming the
        # writer for a read that had already failed and been logged.
        raise AttachmentError(f"could not read the Splunk results file: {e}")


def _ecrire_csv(chemin, entetes, lignes):
    with open(chemin, "wt", newline="") as f:
        csvwriter = csv.writer(f)
        csvwriter.writerow(entetes)
        csvwriter.writerows(lignes)


def _ecrire_json(results_file, entetes, chemin):
    """Re-read as dicts, because a CSV row is positional and JSON is not."""
    with gzip.open(results_file, "rt") as f:
        reader = csv.DictReader(f, entetes)
        next(reader)  # the header line, which DictReader would hand back as data
        lignes = [row for row in reader]

    # ⚠️ Preserved as-is: a single row is written as an OBJECT, several as an
    # ARRAY. Inconsistent, and changing it would silently break every
    # downstream consumer written against the current shape.
    charge = json.dumps(lignes, indent=2) if len(lignes) > 1 else json.dumps(lignes[0], indent=2)
    with open(chemin, "w") as f:
        f.write(charge)


def _nom_final(attach_format, attachment_prefix, object_id, sha256, file_ext,
               logger_file):
    identifiant = str(object_id).replace("~", "")
    if attach_format == 0:
        return attachment_prefix + identifiant + file_ext
    if attach_format == 1:
        return identifiant + file_ext
    if attach_format == 2:
        return attachment_prefix + sha256.hexdigest() + file_ext
    if attach_format == 3:
        return sha256.hexdigest() + file_ext

    # ⚠️ Own identifier. This branch used to reuse id="141", already taken by
    # the results-file trace a hundred lines above, in BOTH helpers.
    logger_file.error(
        id="146",
        message=f"Attachment format isn't supported, given: {attach_format}",
    )
    raise AttachmentError(
        f"attach_format={attach_format} is not supported "
        f"(expected one of {sorted(FORMATS)})"
    )
