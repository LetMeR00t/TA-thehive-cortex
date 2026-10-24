# encoding = utf-8
# Author: Alexandre Demeyer <letmer00t@gmail.com>
#
# Copyright: LGPLv3 (https://www.gnu.org/licenses/lgpl-3.0.txt)
# Feel free to use the code, but please share the changes you've made

__author__ = "Alexandre Demeyer"
__license__ = "LGPLv3"
__version__ = "4.0.0"
__maintainer__ = "Alexandre Demeyer"
__email__ = "letmer00t@gmail.com"

import ta_thehive_cortex_declare

# Standard library imports
import json
import logging
import os
import re
import sys

# Third-party imports
import splunklib.client as client
from solnlib import conf_manager, log

# Local application/library specific imports
# LoggerFile, Utils and the two errors moved out in #24; importing them here
# keeps `from common import ...` working for every caller, the generated
# alert_actions_base.py included.
from dict_utils import Utils
from logger_file import LoggerFile
from settings_accessors import (
    InstanceResolutionError,
    MissingParameterError,
    SettingsAccessors,
)


# --- UCC credential arbitration ---------------------------------------------
#
# ⚠️ This rule decides WHICH password the add-on ends up using when Splunk's
# storage/passwords holds several entries for the same account -- and it used
# to live in two places, inline in Instances.__init__ and copied verbatim into
# a manual diagnostic script. Neither copy was covered by a single assertion.
# A rule duplicated is a rule that drifts, and this one arbitrates secrets.
#
# It is a pure function on purpose: no Splunk, no I/O, no logging. That is what
# makes the arbitration -- which is genuinely subtle -- testable at all.

CRED_SEP = "``splunk_cred_sep``"

# Splunk returns these instead of the value when the caller may not read it.
MASQUES = ("******", "********")


def account_from_ucc_username(username):
    """`<account>``splunk_cred_sep``<field>` -> `<account>`."""
    if CRED_SEP in username:
        return username.split(CRED_SEP)[0]
    return username


def pick_password(entries, app_name="TA-thehive-cortex"):
    """Decide, per account, which stored value is the real password.

    `entries` is any iterable of objects carrying `realm`, `username` and
    `clear_password` -- `client.storage_passwords` satisfies it as is.

    Returns `(passwords, discarded)`:
      * `passwords`  {account: value}
      * `discarded`   accounts whose entry was discarded as garbage, for the
                     caller to log. The function itself never logs: a value
                     that must not reach a log file must not be handed to a
                     logger in the first place.

    The arbitration, in order:
      1. only realms naming this app are considered;
      2. a JSON object is unwrapped to its `password` member -- but only when
         that member DIFFERS from the raw text, which is what marks the entry
         as genuinely JSON-encoded;
      3. masked values are ignored, they carry no secret;
      4. a value containing the UCC separator is Splunk internal garbage;
      5. between two candidates, a JSON-sourced value beats a raw one, and at
         equal provenance the LONGEST wins -- a truncated entry never
         supersedes a whole one.
    """
    passwords = {}
    from_json_by_account = {}
    discarded = []

    for entree in entries:
        realm = entree.realm
        account = account_from_ucc_username(entree.username)
        if not realm or app_name not in realm:
            continue

        raw = entree.clear_password
        from_json = False
        try:
            decoded = json.loads(raw)
            if isinstance(decoded, dict):
                value = decoded.get("password", raw)
                if value != raw:
                    from_json = True
            else:
                value = raw
        except Exception:
            # A stored password is very often not JSON at all. Not an error.
            value = raw

        if value in MASQUES:
            continue

        # ⚠️ A JSON payload can carry a non-string `password` (a number, a
        # nested object). Before this guard the next line raised TypeError
        # INSIDE the caller's blanket try/except, which abandoned every
        # remaining credential: one malformed entry silently cost the
        # passwords of all the other accounts. It is now discarded like any
        # other garbage, and named.
        if not isinstance(value, str):
            discarded.append(account)
            continue

        if CRED_SEP in value:
            discarded.append(account)
            continue

        current_from_json = from_json_by_account.get(account, False)
        current_value = passwords.get(account, "")

        if (
            account not in passwords
            or (from_json and not current_from_json)
            or (from_json == current_from_json and len(value) > len(current_value))
        ):
            passwords[account] = value
            from_json_by_account[account] = from_json

    return passwords, discarded


class Settings(SettingsAccessors):

    def __init__(self, client: client = None, settings=None, logger_file=None):
        # Initialize all settings to None
        self.logger_file = logger_file

        # Check the python version
        self.logger_file.debug(
            id="S1", message="Python version detected: " + str(sys.version_info)
        )

        self._utils = Utils(logger_file=logger_file)

        self.client = client
        self.namespace = "TA-thehive-cortex"
        # Prepare the query
        self.query = {"output_mode": "json"}

        # Get instances
        if settings is not None and "namespace" in settings:
            namespace = settings["namespace"]
            # Get logging
            logging_settings = self.readDefaultLocalConfiguration(
                "thehive_cortex_settings.conf"
            )["logging"]
            self.logger_file.logger.setLevel(logging_settings["loglevel"])
            self.logger_file.debug(
                id="S2",
                message="Logging mode set to " + str(logging_settings["loglevel"]),
            )

        self._instances = {}

        # Use solnlib to get configuration if client is available
        if client is not None:
            session_key = client.token
            
            # Get accounts for usernames
            account_cfm = conf_manager.ConfManager(
                session_key, 
                "TA-thehive-cortex",
                realm="__REST_CREDENTIAL__#TA-thehive-cortex#configs/conf-thehive_cortex_accounts"
            ).get_conf("thehive_cortex_accounts")
            accounts = account_cfm.get_all()
            self.logger_file.debug(id="S3", message=f"Accounts retrieved: {list(accounts.keys())}")

            # Get storage passwords -- the arbitration itself lives in
            # pick_password(), a pure function, so it can be tested without a
            # Splunk instance. See its docstring for the rule.
            self._passwords = {}
            try:
                self._passwords, discarded = pick_password(self.client.storage_passwords)
                for account in discarded:
                    self.logger_file.debug(
                        id="S3_SKIP",
                        message=f"Skipping unusable stored value for account {account}",
                    )
            except Exception as e:
                self.logger_file.error(
                    id="S3_ERROR", message=f"Failed to access storage_passwords: {e}"
                )
            self.logger_file.debug(
                id="S4",
                # credential-free: the KEYS of this mapping are account names,
                # never values. Naming which accounts carry a stored password is
                # what makes "TH31: both password and API key are empty"
                # diagnosable at all.
                message=f"Passwords retrieved for accounts: {list(self._passwords.keys())}",
            )

            # Get instances from thehive_cortex_instances.conf
            instance_cfm = conf_manager.ConfManager(
                session_key, "TA-thehive-cortex"
            ).get_conf("thehive_cortex_instances")
            instances_conf = instance_cfm.get_all()
            
            self._id_to_name = {}
            for row_id, row in instances_conf.items():
                self.logger_file.debug(
                    id="S5", message="New instance detected, getting " + str(row)
                )
                
                # Build ID mapping (UCC/REST ID to name)
                # UCC ID is usually /servicesNS/nobody/TA-thehive-cortex/thehive_cortex_instances/<name>
                technical_id = f"/servicesNS/nobody/TA-thehive-cortex/thehive_cortex_instances/{row_id}"
                self._id_to_name[technical_id] = row_id
                self._id_to_name[technical_id.replace(" ", "%20")] = row_id

                # Get username and password from associated account
                account_name = row.get("account_name")
                if account_name and account_name in accounts:
                    row["username"] = accounts[account_name].get("username", "-")
                    row["password"] = self._passwords.get(account_name, "-")
                else:
                    row["username"] = "-"
                    row["password"] = "-"

                # Handle client certificate
                if row.get("client_cert") and row["client_cert"] != "-" and not row["client_cert"].startswith("/"):
                    # Check if it's a relative path in local/
                    client_certificate = os.path.join(
                        os.environ["SPLUNK_HOME"],
                        "etc",
                        "apps",
                        "TA-thehive-cortex",
                        "local",
                        row["client_cert"],
                    )
                    if os.path.exists(client_certificate):
                        row["client_cert"] = client_certificate
                    else:
                        self.logger_file.warn(
                            id="S13",
                            message='Be aware that a client certificate for instance "'
                            + str(row_id)
                            + "\" was provided but the file doesn't exist: "
                            + client_certificate,
                        )

                # Handle CA certificate
                if row.get("ca_cert_path") and row["ca_cert_path"] != "-" and not row["ca_cert_path"].startswith("/"):
                    # Check if it's a relative path in local/
                    ca_certificate = os.path.join(
                        os.environ["SPLUNK_HOME"],
                        "etc",
                        "apps",
                        "TA-thehive-cortex",
                        "local",
                        row["ca_cert_path"],
                    )
                    if os.path.exists(ca_certificate):
                        row["ca_cert_path"] = ca_certificate
                    else:
                        self.logger_file.warn(
                        id="S13b",
                        message='Be aware that a CA certificate for instance "'
                        + str(row_id)
                        + "\" was provided but the file doesn't exist: "
                        + ca_certificate,
                        )
                
                # Set verify parameter securely (Issue #116)
                # If ca_cert_path is provided, use it for verification. Otherwise use True.
                row["verify"] = True if row.get("ca_cert_path", "-") == "-" else row["ca_cert_path"]

                # get proxy parameters if any
                proxy_url_val = row.get("proxy_url", "-")
                if proxy_url_val != "-":
                    pattern = r"^(?P<proxy_protocol>https?:\/\/)?(?P<proxy_url>.*)$"
                    match = re.search(pattern, proxy_url_val)
                    if match:
                        proxy_protocol = match.group("proxy_protocol") or "http://"
                        row["proxy_url"] = match.group("proxy_url")
                    
                    if row["proxy_url"] and row["proxy_url"][-1] != "/":
                        row["proxy_url"] += "/"

                    proxy_account = row.get("proxy_account", "-")
                    if proxy_account != "-":
                        proxy_username = accounts.get(proxy_account, {}).get("username", "-")
                        proxy_password = self._passwords.get(proxy_account, "-")
                        full_proxy_url = (
                            proxy_protocol
                            + proxy_username
                            + ":"
                            + proxy_password
                            + "@"
                            + row["proxy_url"]
                        )
                    else:
                        full_proxy_url = proxy_protocol + row["proxy_url"]

                    row["proxies"] = {"http": full_proxy_url, "https": full_proxy_url}
                else:
                    row["proxies"] = None

                row["organisation"] = (
                    row.get("organisation") if row.get("organisation") != "-" else None
                )

                # If nothing is defined for the URI, then use the root by default
                if "uri" not in row or row["uri"] is None or row["uri"] == "-":
                    row["uri"] = "/"

                self.logger_file.debug(
                    id="S14",
                    message='New instance parsed, adding key "'
                    + str(row_id)
                    + '" '
                    + str(row),
                )
                # Store the new instance
                self._instances[row_id] = row

        # Get additional parameters
        conf = self.readDefaultLocalConfiguration("thehive_cortex_settings.conf")
        self._additional_parameters = {
            **conf.get("additional_parameters", {}),
            **conf.get("settings", {}),
        }
        self.logger_file.debug(
            id="S15",
            message="Getting these additional parameters: "
            + str(self._additional_parameters),
        )

    @property
    def utils(self):
        return self._utils
