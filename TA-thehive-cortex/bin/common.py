import sys
import os
import csv
import ta_thehive_cortex_declare
import json
import splunklib.client as client
import logging


class Settings(object):

    def __init__(self, client, search_settings=None, logger=None):
        # Initialize all settings to None
        self.logger = logger

        namespace = "TA-thehive-cortex"
        # Prepare the query
        query = {"output_mode": "json"}

        # Get instances
        if search_settings is not None:
            namespace = search_settings["namespace"]
            # Get logging
            logging_settings = json.loads(client.get("TA_thehive_cortex_settings/logging", owner="nobody", app=namespace,**query).body.read())["entry"][0]["content"]
            if "loglevel" in logging_settings:
                logger.setLevel(logging_settings["loglevel"])

    config_args = dict()
    # get MISP instance to be used
    response = helper.service.get('misp42splunk_account')
    if response.status == 200:
        data_body = splunklib.data.load(response.body.read())
        helper.log_error("[MC1000] data body {}".format(data_body))
        misp_instances = data_body['feed']['entry']
    if len(misp_instances) > 0:
        foundStanza = False
        for instance in list(misp_instances):
            if misp_instance == str(instance['title']):
                app_config = instance['content']
                helper.log_error("[MC1000] app config {}".format(app_config))
                foundStanza = True
        if not foundStanza:
            raise Exception("no misp_instance with specified name found: %s ", str(misp_instance))
            return None
    else:
        raise Exception(
            "no misp instance configured. Please "
            "configure an entry for %s", misp_instance
        )
        return None












        instances_csv = os.environ["SPLUNK_HOME"] + "/etc/apps/" + namespace + "/lookups/thehive_cortex_instances.csv"
        self.__instances = {}
        instances_by_account_name = {}
        try:
            content = csv.DictReader(open(instances_csv,"r"))
            for row in content:
                # Process the new instance
                row_id = row["id"]
                del row["id"]

                # Keep information for storage password
                if (row["account_name"] not in instances_by_account_name):
                    instances_by_account_name[row["account_name"]] = [row_id]
                else:
                    instances_by_account_name[row["account_name"]].append(row_id)

                # Store the new instance
                row_dict = json.loads(json.dumps(row))
                self.__instances[row_id] = row_dict
        except IOError as e:
            self.logger.error("[5-FILE MISSING] Could not open/access/process the following file: "+instances_csv)
            sys.exit(5)

        # Get additional parameters
        self.__additional_parameters = json.loads(client.get("TA_thehive_cortex_settings/additional_parameters", owner="nobody", app=namespace,**query).body.read())["entry"][0]["content"]

        # Get username of account name
        for account_details in json.loads(client.get("TA_thehive_cortex_account", owner="nobody", app=namespace,**query).body.read())["entry"]:
            account_details_name = account_details["name"]
            if account_details_name in instances_by_account_name.keys():
                instances_of_account_name = instances_by_account_name[account_details_name]
                for i in instances_of_account_name:
                    self.__instances[i]["username"] = account_details["content"]["username"] 

        # Get storage passwords for account passwords
        for s in client.storage_passwords:
            for account in instances_by_account_name.keys():
                # Get account details by instance
                if account in s['username'] and "password" in s['clear_password']:
                    instances_of_account_name = instances_by_account_name[account]
                    for i in instances_of_account_name:
                        self.__instances[i]["password"] = str(json.loads(s["clear_password"])["password"])


    def getInstanceURL(self, instance_id):
        """ This function returns the URL of the given instance """
        instance = self.__instances[instance_id]
        return instance["protocol"]+"://"+instance["host"]+":"+instance["port"]

    def getInstanceUsernameApiKey(self, instance_id):
        """ This function returns the Username/API key of the given instance """
        instance = self.__instances[instance_id]
        if "username" not in instance:
            instance["username"] = "-"
            instance["password"] = "-"
        return (instance["username"], instance["password"])

    def getTheHiveCasesMax(self):
        """ This function returns the maximum number of jobs to return of the TheHive instance """
        return self.__additional_parameters["thehive_max_cases"] if "thehive_max_cases" in self.__additional_parameters else 100

    def getTheHiveCasesSort(self):
        """ This function returns the sort key to use for jobs of the TheHive instance """
        return self.__additional_parameters["thehive_sort_cases"] if "thehive_sort_cases" in self.__additional_parameters else "-startedAt"

    def getCortexJobsMax(self):
        """ This function returns the maximum number of jobs to return of the Cortex instance """
        return self.__additional_parameters["cortex_max_jobs"] if "cortex_max_jobs" in self.__additional_parameters else 100

    def getCortexJobsSort(self):
        """ This function returns the sort key to use for jobs of the Cortex instance """
        return self.__additional_parameters["cortex_sort_jobs"] if "cortex_sort_jobs" in self.__additional_parameters else "-createdAt"

    def checkAndValidate(self, d, name, default="", is_mandatory=False):
        """ This function is use to check and validate an expected value format """
        if name in d:
            self.logger.info("Found parameter \"" + name + "\"="+d[name])
            return d[name]
        else:
            if is_mandatory:
                self.logger.error("Missing parameter (no \"" + name + "\" field found)")
                sys.exit(1)
            else:
                self.logger.info("Parameter \"" + name + "\" not found, using default value=\"" + default + "\"")
                return default
