# encoding = utf-8
import os
import sys
import ta_thehive_cortex_declare
import json
from splunk.clilib import cli_common as cli
import re

class Settings(object):

    def __init__(self, client, search_settings=None, logger=None):
        # Initialize all settings to None
        self.logger = logger

        # Check the python version
        self.logger.debug("[S1] Python version detected: " + str(sys.version_info))

        self.client = client
        self.namespace = "TA-thehive-cortex"
        # Prepare the query
        self.query = {"output_mode": "json"}

        # Get instances
        if search_settings is not None and "namespace" in search_settings:
            namespace = search_settings["namespace"]
            # Get logging
            logging_settings = json.loads(
                self.client.get("TA_thehive_cortex_settings/logging", owner="nobody", app=self.namespace, **self.query).body.read())["entry"][0]["content"]
            if "loglevel" in logging_settings:
                logger.setLevel(logging_settings["loglevel"])
            self.logger.debug("[S2] Logging mode set to " + str(logging_settings["loglevel"]))

        proxy_clear_password = None
        for credential in self.client.storage_passwords:
            username = credential.content.get('username')
            if 'proxy' in username:
                clear_credentials = credential.content.get('clear_password')
                if 'proxy_password' in clear_credentials:
                    proxy_creds = json.loads(clear_credentials)
                    proxy_clear_password = str(proxy_creds['proxy_password'])

        self.__instances = {}
        instances_by_account_name = {}
        try:
            content = self.client.kvstore["kv_thehive_cortex_instances"].data.query()
            for row in content:
                self.logger.debug("[S5] KVStore, getting " + str(row))
                # Process the new instance
                row_id = row["id"]
                del row["id"]

                # Keep information for storage password
                if (row["account_name"] not in instances_by_account_name):
                    instances_by_account_name[row["account_name"]] = [row_id]
                else:
                    instances_by_account_name[row["account_name"]].append(row_id)
                
                # get self.client certificate if it's specified
                if row["client_cert"] != "-" and ".." not in row["client_cert"]:
                    client_certificate = os.path.join(os.environ['SPLUNK_HOME'], 'etc', 'apps', 'TA-thehive-cortex','local', row["client_cert"])
                    if os.path.exists(client_certificate):
                        row["client_cert"] = client_certificate
                    else:
                        self.logger.warning("[S8] Be aware that a client certificate for instance \""+str(row_id)+"\" was provided but the file doesn't exist: "+client_certificate)

                # get proxy parameters if any
                if row["proxy_url"] != "-":
                    pattern = r"^(?P<proxy_protocol>https?:\/\/)?(?P<proxy_url>.*)$"
                    match = re.search(pattern, row["proxy_url"])
                    if match:
                       if match.group("proxy_protocol") is not None:
                           proxy_protocol = match.group("proxy_protocol")
                       else:
                           # Default to HTTP proxy
                           proxy_protocol = "http://"
                       row["proxy_url"] = match.group("proxy_url")
                    if row["proxy_url"][-1] != "/":
                        row["proxy_url"] += "/"

                    if row["proxy_account"] != "-":
                        proxy_url = proxy_protocol
                        proxy_username = self.getAccountUsername(row["proxy_account"])
                        proxy_password = self.getAccountPassword(row["proxy_account"])
                        proxy_url += proxy_username+":"+proxy_password+"@"+row["proxy_url"]
                    else:
                        proxy_url = proxy_protocol+row["proxy_url"]

                    row["proxies"] = {
                        "http": proxy_url,
                        "https": proxy_url
                    }
                else:
                    row["proxies"] = None

                row["organisation"] = row["organisation"] if row["organisation"] != "-" else None

                self.logger.debug("[S10] KVStore, adding key \"" + str(row_id) + "\" " + str(row))
                # Store the new instance
                row_dict = json.loads(json.dumps(row))
                self.__instances[row_id] = row_dict
        except IOError as e:
            self.logger.error("[S11-ERROR] Could not open/access/process KVStore: ")
            sys.exit(11)

        # Get additional parameters
        self.__additional_parameters = json.loads(self.client.get("TA_thehive_cortex_settings/additional_parameters", owner="nobody", app=self.namespace, **self.query).body.read())["entry"][0]["content"]
        self.logger.debug("[S15] Getting these additional parameters: " + str(self.__additional_parameters))

        # Get username of account name
        for account in instances_by_account_name.keys():
            instances_of_account_name = instances_by_account_name[account]
            username = self.getAccountUsername(account)
            for i in instances_of_account_name:
                    self.__instances[i]["username"] = username 
        self.logger.debug("[S20] Getting these usernames from account: "+str(self.__instances))

        # Get storage passwords for account passwords
        for account in instances_by_account_name.keys():
            # Get account details by instance
                instances_of_account_name = instances_by_account_name[account]
                password = self.getAccountPassword(account)
                for i in instances_of_account_name:
                    self.__instances[i]["password"] = password
        self.logger.debug("[S25] Getting these passwords from storage passwords: " + str(self.__instances))


    def getAccountUsername(self, account):
        """ Get the username of an account """
        username = None
        for account_details in json.loads(self.client.get("TA_thehive_cortex_account", owner="nobody", app=self.namespace,**self.query).body.read())["entry"]:
            account_details_name = account_details["name"]
            if account_details_name == account:
                if "username" in account_details["content"]:
                    username = account_details["content"]["username"] 
        return username

    def getAccountPassword(self, account):
        """ Get storage passwords for the account password """
        password = None
        for s in self.client.storage_passwords:
            if account in s['username'] and "password" in s['clear_password']:
                password = str(json.loads(s["clear_password"])["password"])
        return password


    def getInstanceURL(self, instance_id):
        """ This function returns the URL of the given instance """
        try:
            instance = self.__instances[instance_id]
        except KeyError as e:
            self.logger.debug("[S26-ERROR] This instance ID ("+instance_id+") doesn't exist in your configuration")
            sys.exit(26)

        self.logger.debug("[S30] This instance ID ("+str(instance_id)+") returns: "+str(instance))
        return instance["protocol"]+"://"+instance["host"]+":"+str(instance["port"])

    def getInstanceUsernameApiKey(self, instance_id):
        """ This function returns the Username/Secret (password or API key) of the given instance """
        try:
            instance = self.__instances[instance_id]
        except KeyError as e:
            self.logger.debug("[S31-ERROR] This instance ID ("+instance_id+") doesn't exist in your configuration")
            sys.exit(31)

        if "username" not in instance:
            instance["username"] = "-"
            instance["password"] = "-"
        self.logger.debug("[S35] This instance ID ("+str(instance_id)+") returns: "+str(instance))
        return (instance["username"], instance["password"])

    def getInstanceSetting(self, instance_id, setting):
        """ This function returns the setting for the given instance """
        instance = None
        if instance_id in self.__instances and setting in self.__instances[instance_id]:
            instance = self.__instances[instance_id][setting]
            self.logger.debug("[S40] this instance id ("+str(instance_id)+") returns: "+str(setting)+"="+str(instance))
        else:
            self.logger.warning("[S41] Can't recover the setting \""+str(setting)+"\" for the instance \""+str(instance_id)+"\"")
        return instance

    def getTheHiveCasesMax(self):
        """ This function returns the maximum number of cases to return of a TheHive instance """
        param = self.__additional_parameters["thehive_max_cases"] if "thehive_max_cases" in self.__additional_parameters else 100
        self.logger.debug("[S45] Getting this parameter : thehive_max_cases="+str(param))
        return param

    def getTheHiveCasesSort(self):
        """ This function returns the sort key to use for cases of a TheHive instance """
        param = self.__additional_parameters["thehive_sort_cases"] if "thehive_sort_cases" in self.__additional_parameters else "-startedAt"
        self.logger.debug("[S50] Getting this parameter: thehive_sort_cases="+str(param))
        return param

    def getTheHiveAlertsMax(self):
        """ This function returns the maximum number of alerts to return of a TheHive instance """
        param = self.__additional_parameters["thehive_max_alerts"] if "thehive_max_alerts" in self.__additional_parameters else 100
        self.logger.debug("[S51] Getting this parameter: thehive_max_alerts="+str(param))
        return param

    def getTheHiveAlertsSort(self):
        """ This function returns the sort key to use for alerts of a TheHive instance """
        param = self.__additional_parameters["thehive_sort_alerts"] if "thehive_sort_alerts" in self.__additional_parameters else "-date"
        self.logger.debug("[S52] Getting this parameter: thehive_sort_alerts="+str(param))
        return param

    def getCortexJobsMax(self):
        """ This function returns the maximum number of jobs to return of a Cortex instance """
        param = self.__additional_parameters["cortex_max_jobs"] if "cortex_max_jobs" in self.__additional_parameters else 100
        self.logger.debug("[S55] Getting this parameter: "+str(param))
        return param

    def getCortexJobsSort(self):
        """ This function returns the sort key to use for jobs of a Cortex instance """
        param = self.__additional_parameters["cortex_sort_jobs"] if "cortex_sort_jobs" in self.__additional_parameters else "-createdAt"
        self.logger.debug("[S60] Getting this parameter: "+str(param))
        return param

    def checkAndValidate(self, d, name, default="", is_mandatory=False):
        """ This function is use to check and validate an expected value format """
        if name in d:
            self.logger.info("[S65] Found parameter \""+str(name)+"\"="+str(d[name]))
            return d[name]
        else:
            if is_mandatory:
                self.logger.error("[S66-ERROR] Missing parameter (no \""+str(name)+"\" field found)")
                sys.exit(66)
            else:
                self.logger.info("[S67] Parameter \""+str(name)+"\" not found, using default value=\""+str(default)+"\"")
                return default 


