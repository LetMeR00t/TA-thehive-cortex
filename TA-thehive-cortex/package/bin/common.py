# encoding = utf-8
import logging
from typing import Union
import globals
import os
import base64
import datetime
import sys
import json
from thehive4py.query.sort import Asc, Desc
import re
import csv
import splunklib.client as client
from solnlib import conf_manager
from solnlib import log
from solnlib.utils import is_true


class LoggerFile(object):

    def __init__(self, logger=None, command_id=""):
        self._logger = logger
        self.command_id = str(command_id)

    @property
    def logger(self):
        return self._logger

    def _log(self, type="info", id="?", message=""):
        if globals.log_context == "[]":
            log_context = ""
        else:
            log_context = globals.log_context
        if type == "debug" and self.logger.getEffectiveLevel() != logging.DEBUG:
            pass
        else:
            getattr(self.logger, type)(
                log_context
                + "["
                + globals.next_log_id()
                + "]["
                + self.command_id
                + "-"
                + str(id)
                + "] "
                + str(message)
            )

    def info(self, id="?", message=""):
        self._log("info", id=id, message=message)

    def warn(self, id="?", message=""):
        self._log("warn", id=str(id) + "-WARNING", message=message)

    # Support potential issues
    def warning(self, id="?", message=""):
        self.warn(id=id, message=message)

    def error(self, id="?", message=""):
        self._log("error", id=str(id) + "-ERROR", message=message)

    def debug(self, id="?", message=""):
        self._log("debug", id=id, message=message)


class Settings(object):

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
                "ta_thehive_cortex_settings.conf"
            )["logging"]
            self.logger_file.logger.setLevel(logging_settings["loglevel"])
            self.logger_file.debug(
                id="S2",
                message="Logging mode set to " + str(logging_settings["loglevel"]),
            )

        self.__instances = {}

        # Use solnlib to get configuration if client is available
        if client is not None:
            session_key = client.token
            
            # Get accounts for usernames
            account_cfm = conf_manager.get_conf_manager(
                session_key, "TA-thehive-cortex"
            ).get_conf("ta_thehive_cortex_account")
            accounts = account_cfm.get_all()
            self.logger_file.debug(id="S3", message=f"Accounts retrieved: {list(accounts.keys())}")

            # Get storage passwords
            self._passwords = {}
            sp = self.client.storage_passwords
            for credential in sp:
                if credential.access["app"] == "TA-thehive-cortex":
                    # UCC format for account is usually name
                    username_raw = credential["username"]
                    # If it's an UCC account, it might have a prefix or specific format
                    # But here we just need to match it with the account name
                    if "password" in credential["clear_password"]:
                        try:
                            clear_password_json = json.loads(credential["clear_password"])
                            self._passwords[username_raw] = clear_password_json["password"]
                        except Exception:
                            # Fallback if not JSON
                            self._passwords[username_raw] = credential["clear_password"]

            # Get instances from ta_thehive_cortex_instances.conf
            instance_cfm = conf_manager.get_conf_manager(
                session_key, "TA-thehive-cortex"
            ).get_conf("ta_thehive_cortex_instances")
            instances_conf = instance_cfm.get_all()
            
            for row_id, row in instances_conf.items():
                self.logger_file.debug(
                    id="S5", message="New instance detected, getting " + str(row)
                )
                
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
                self.__instances[row_id] = row

        # Get additional parameters
        self.__additional_parameters = self.readDefaultLocalConfiguration(
            "ta_thehive_cortex_settings.conf"
        ).get("additional_parameters", {})
        self.logger_file.debug(
            id="S15",
            message="Getting these additional parameters: "
            + str(self.__additional_parameters),
        )

    @property
    def utils(self):
        return self._utils

    def readConfFile(self, folder, filename):
        """This function is used to retrieve information from a .conf file stored in a specified folder in this application"""
        conf = {}

        # Open and read the conf file
        conf_file = os.path.join(
            os.environ["SPLUNK_HOME"],
            "etc",
            "apps",
            "TA-thehive-cortex",
            folder,
            filename,
        )
        if os.path.isfile(conf_file):
            with open(conf_file, "r") as file:
                stanza = None
                for line in file:
                    if line.startswith("["):
                        # We have a new stanza
                        stanza = line.strip()[1:][:-1]
                        conf[stanza] = {}
                    if " = " in line:
                        # Build a dictionnary with the information
                        key, value = line.partition(" = ")[::2]
                        # Check if the key exist. If so, then create a list of detected values accordingly
                        skey = key.strip()
                        if skey in conf:
                            if type(conf[skey]) is list:
                                conf[stanza][skey] += [value.rstrip("\n")]
                            else:
                                conf[stanza][skey] = [value.rstrip("\n")] + [conf[skey]]
                        else:
                            conf[stanza][skey] = value.rstrip("\n")
            self.logger_file.debug(
                id="S26",
                message="Configuration "
                + folder
                + "/"
                + filename
                + " was read: "
                + str(conf),
            )
        else:
            self.logger_file.debug(
                id="S27",
                message="Configuration " + folder + "/" + filename + " doesn't exist.",
            )
        return conf

    def readDefaultLocalConfiguration(self, filename):
        """This function is used to retrieve information from a default/local configuration merged dictionnary where local is prior to default settings"""

        # Open and read the default file
        default = self.readConfFile("default", filename)
        # Do the same with the local file if it's existing and merge information
        local = self.readConfFile("local", filename)

        # Recovered configuration for the filename
        self.logger_file.debug(
            id="S28",
            message="Configuration retrieved for the filename '"
            + filename
            + "': "
            + str({**default, **local}),
        )

        return {**default, **local}

    def sanitizeInstance(self, instance):
        result = instance
        result["password"] = "**********"
        return result

    def getAccountPassword(self, account):
        """Get storage passwords for the account password"""
        password = None
        if account in self._passwords:
            password = self._passwords[account]
        else:
            self.logger_file.debug(
                id="S29",
                message="This account ("
                + account
                + ") doesn't exist in your configuration and it's password can't be retrieved",
            )
        return password

    def getInstanceURL(self, instance_id):
        """This function returns the URL of the given instance"""
        try:
            instance = self.__instances[instance_id]
        except KeyError as e:
            self.logger_file.error(
                id="S30",
                message="This instance ID ("
                + instance_id
                + ") doesn't exist in your configuration",
            )
            sys.exit(30)

        # Empty the root URI as it will be filled by the API library directly
        uri = str(instance["uri"]) if str(instance["uri"]) != "/" else ""

        self.logger_file.debug(
            id="S30",
            message="This instance ID ("
            + str(instance_id)
            + ") returns: "
            + str(self.sanitizeInstance(instance)),
        )
        return "https://" + instance["host"] + ":" + str(instance["port"]) + uri

    def getInstanceUsernameApiKey(self, instance_id):
        """This function returns the Username/Secret (password or API key) of the given instance"""
        try:
            instance = self.__instances[instance_id]
        except KeyError as e:
            self.logger_file.error(
                id="S31",
                message="This instance ID ("
                + instance_id
                + ") doesn't exist in your configuration",
            )
            sys.exit(31)

        if "username" not in instance:
            instance["username"] = "-"
            instance["password"] = "-"
        elif "password" not in instance:
            instance["password"] = None
        self.logger_file.debug(
            id="S35",
            message="This instance ID ("
            + str(instance_id)
            + ") returns: "
            + str(instance["username"]),
        )
        return (instance["username"], instance["password"])

    def getInstanceSetting(self, instance_id, setting):
        """This function returns the setting for the given instance"""
        instance = None
        if instance_id in self.__instances and setting in self.__instances[instance_id]:
            instance = self.__instances[instance_id][setting]
            self.logger_file.debug(
                id="S40",
                message="this instance id ("
                + str(instance_id)
                + ") returns: "
                + str(setting)
                + "="
                + str(instance),
            )
        else:
            self.logger_file.warn(
                id="S41",
                message="Can't recover the setting \""
                + str(setting)
                + '" for the instance "'
                + str(instance_id)
                + '"',
            )
        return instance

    def getTheHiveDefaultInstance(self):
        """This function returns the default instance ID of a TheHive instance if set"""
        param = (
            self.__additional_parameters["thehive_default_instance"]
            if "thehive_default_instance" in self.__additional_parameters
            else None
        )
        self.logger_file.debug(
            id="S45",
            message="Getting this parameter : thehive_default_instance=" + str(param),
        )
        return param

    def getTheHiveCasesMax(self):
        """This function returns the maximum number of cases to return of a TheHive instance"""
        param = (
            self.__additional_parameters["thehive_max_cases"]
            if "thehive_max_cases" in self.__additional_parameters
            else 100
        )
        self.logger_file.debug(
            id="S45", message="Getting this parameter : thehive_max_cases=" + str(param)
        )
        return param

    def getTheHiveCasesSort(self):
        """This function returns the sort key to use for cases of a TheHive instance"""
        param = (
            self.__additional_parameters["thehive_sort_cases"]
            if "thehive_sort_cases" in self.__additional_parameters
            else "-startedAt"
        )
        param = Desc(param[1:]) if param[0] == "-" else Asc(param)
        self.logger_file.debug(
            id="S50", message="Getting this parameter: thehive_sort_cases=" + str(param)
        )
        return param

    def getTheHiveAlertsMax(self):
        """This function returns the maximum number of alerts to return of a TheHive instance"""
        param = (
            self.__additional_parameters["thehive_max_alerts"]
            if "thehive_max_alerts" in self.__additional_parameters
            else 100
        )
        self.logger_file.debug(
            id="S51", message="Getting this parameter: thehive_max_alerts=" + str(param)
        )
        return param

    def getTheHiveAlertsSort(self):
        """This function returns the sort key to use for alerts of a TheHive instance"""
        param = (
            self.__additional_parameters["thehive_sort_alerts"]
            if "thehive_sort_alerts" in self.__additional_parameters
            else "-date"
        )
        param = Desc(param[1:]) if param[0] == "-" else Asc(param)
        self.logger_file.debug(
            id="S52",
            message="Getting this parameter: thehive_sort_alerts=" + str(param),
        )
        return param

    def getTheHiveTTPCatalogName(self):
        """This function returns the TTP Catalog name of a TheHive instance"""
        param = (
            self.__additional_parameters["thehive_ttp_catalog_name"]
            if "thehive_ttp_catalog_name" in self.__additional_parameters
            else "Enterprise Attack"
        )
        self.logger_file.debug(
            id="S53",
            message="Getting this parameter: thehive_ttp_catalog_name=" + str(param),
        )
        return param

    def getTheHiveCreationAttachmentPrefix(self):
        """This function returns the maximum creation retry of a TheHive instance"""
        param = (
            self.__additional_parameters["thehive_creation_attachment_prefix"]
            if "thehive_creation_attachment_prefix" in self.__additional_parameters
            else "events_"
        )
        self.logger_file.debug(
            id="S54",
            message="Getting this parameter: thehive_creation_attachment_prefix="
            + str(param),
        )
        return param

    def getTheHiveCreationMaxRetry(self):
        """This function returns the maximum creation retry of a TheHive instance"""
        param = (
            self.__additional_parameters["thehive_creation_max_retry"]
            if "thehive_creation_max_retry" in self.__additional_parameters
            else "5"
        )
        self.logger_file.debug(
            id="S54",
            message="Getting this parameter: thehive_creation_max_retry=" + str(param),
        )
        return param

    def getCortexJobsMax(self):
        """This function returns the maximum number of jobs to return of a Cortex instance"""
        param = (
            self.__additional_parameters["cortex_max_jobs"]
            if "cortex_max_jobs" in self.__additional_parameters
            else 100
        )
        self.logger_file.debug(
            id="S55", message="Getting this parameter: " + str(param)
        )
        return param

    def getCortexJobsSort(self):
        """This function returns the sort key to use for jobs of a Cortex instance"""
        param = (
            self.__additional_parameters["cortex_sort_jobs"]
            if "cortex_sort_jobs" in self.__additional_parameters
            else "-createdAt"
        )
        self.logger_file.debug(
            id="S56", message="Getting this parameter: " + str(param)
        )
        return param

    def checkAndValidate(self, d, name, default="", is_mandatory=False):
        """This function is use to check and validate an expected value format"""
        if name in d:
            self.logger_file.debug(
                id="S60", message='Found parameter "' + str(name) + '"=' + str(d[name])
            )
            return d[name]
        else:
            if is_mandatory:
                self.logger_file.debug(
                    id="S66",
                    message='Missing parameter (no "' + str(name) + '" field found)',
                )
                sys.exit(66)
            else:
                self.logger_file.debug(
                    id="S67",
                    message='Parameter "'
                    + str(name)
                    + '" not found, using default value="'
                    + str(default)
                    + '"',
                )
                return default


class Utils:

    def __init__(self, logger_file=None):
        # Initialize all settings to None
        self.logger_file = logger_file

        # Check the python version
        self.logger_file.debug(id="U1", message="Utils class initiated")

    def remove_unwanted_keys_from_dict(self, d: dict, l: list) -> dict:
        """This method is used to remove unwanted keys provided through a list 'l' from a dictionnary 'd'.
        Processing is taking into account the path within the dictionnary so it could be nested dictionnaries.
        Examples:
        - key1.key2.*.key3
        - key4.key5
        - key6

        Note: Wildcard is used for list of items

        Args:
            d (dict): input dictionnary
            l (list): list containing the keys to remove

        Returns:
            dict: the processed dictionnary 'd' with the list 'l'
        """
        self.logger_file.debug(
            id="U5",
            message=f"Event before processing (remove_unwanted_keys_from_dict): {d}",
        )
        new_d = d.copy()
        for path in l:
            new_d = self._remove_key_from_dict(d=new_d, path=path.split("."))
        self.logger_file.debug(
            id="U10",
            message=f"Event after processing (remove_unwanted_keys_from_dict): {new_d}",
        )
        return new_d

    def _remove_key_from_dict(
        self, d: Union[dict, list], path: list
    ) -> Union[dict, list]:
        """This method is used to remove one key from a dictionnary by giving the path to it

        Args:
            d (dict): input dictionnary
            path (list): path to the key in the dictionnary

        Returns:
            dict: dictionnary without the key if it exists.
        """
        new_d = d.copy()
        new_path = path.copy()
        key = new_path.pop(0)

        # Check if d is a dict or a list
        if isinstance(d, dict):
            # If the path is a final node
            if len(path) == 1:
                key = path[0]
                if key in d.keys():
                    del new_d[key]
                return new_d
            else:
                # It's a string or a list
                if key in new_d.keys():
                    child_d = self._remove_key_from_dict(new_d[key], path=new_path)
                    new_d[key] = child_d
                # Anyway return the new dict, modified or not
                return new_d
        elif isinstance(d, list) and key == "*":
            # Process each item
            # Check if it's a list of dict
            if len(d) > 0 and isinstance(d[0], dict):
                # Process each subdict
                items = []
                for item in d:
                    items.append(self._remove_key_from_dict(d=item, path=new_path))
                return items
            else:
                # As it's not dictionnaries, keep it as it
                return d
        else:
            # Unknown type
            return new_d

    def check_and_reduce_values_size(self, d: any, max_size: int) -> any:
        """Parse a dictionnary 'd' and truncate any value which is exceeding the 'max_size' length

        Args:
            d (any): input dictionnary or any substructure of the dictionnary
            max_size (int): maximum size for a given value. Exceeding this limit will truncate the value to max_size (and convert it as a string)

        Returns:
            dict: dictionnary processed and with values not exceeding 'max_size'
        """
        new_d = None
        if isinstance(d, dict):
            new_d = d.copy()
            # Process the all dictionnary
            for key in d.keys():
                new_d[key] = self.check_and_reduce_values_size(
                    d=d[key], max_size=max_size
                )
            return new_d
        elif isinstance(d, list):
            # Process each item of the list
            items = []
            for item in d:
                items.append(
                    self.check_and_reduce_values_size(d=item, max_size=max_size)
                )
            return items
        else:
            # It's not a dict or a list, consider it as final node and check
            if len(str(d)) > max_size:
                new_d = str(d)[0:max_size] + "[trunc]"
            else:
                new_d = d

            return new_d
