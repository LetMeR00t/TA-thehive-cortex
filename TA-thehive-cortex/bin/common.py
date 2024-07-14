# encoding = utf-8
import logging
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

class LoggerFile(object):

    def __init__(self, logger = None, command_id = ""):
        self._logger = logger
        self.command_id = str(command_id)

    @property
    def logger(self):
        return self._logger

    def _log(self, type = "info", id = "?", message = ""):
        if globals.log_context == "[]":
            log_context = ""
        else:
            log_context = globals.log_context
        if type == "debug" and self.logger.getEffectiveLevel() != logging.DEBUG:
            pass
        else:
            getattr(self.logger, type)(log_context+"["+globals.next_log_id()+"]["+self.command_id+"-"+str(id)+"] "+str(message))

    def info(self, id = "?", message = ""):
            self._log("info", id=id, message=message)

    def warn(self, id = "?", message = ""):
            self._log("warn", id=str(id)+"-WARNING", message=message)

    def error(self, id = "?", message = ""):
            self._log("error", id=str(id)+"-ERROR", message=message)

    def debug(self, id = "?", message = ""):
            self._log("debug", id=id, message=message)

class Settings(object):

    def __init__(self, client: client = None, settings=None, logger_file=None):
        # Initialize all settings to None
        self.logger_file = logger_file

        # Check the python version
        self.logger_file.debug(id="S1",message="Python version detected: " + str(sys.version_info))

        self.client = client
        self.namespace = "TA-thehive-cortex"
        # Prepare the query
        self.query = {"output_mode": "json"}

        # Get instances
        if settings is not None and "namespace" in settings:
            namespace = settings["namespace"]
            # Get logging
            logging_settings = self.readDefaultLocalConfiguration("ta_thehive_cortex_settings.conf")["logging"]
            self.logger_file.logger.setLevel(logging_settings["loglevel"])
            self.logger_file.debug(id="S2",message="Logging mode set to " + str(logging_settings["loglevel"]))

        # Retrieve password information in a dedicated list
        if client is not None:
            self._passwords = {}
            proxy_clear_password = None
            sp = self.client.storage_passwords
            for credential in sp:
                if credential.access["app"] == "TA-thehive-cortex":
                    username = credential['username'].split("``")[0]
                    # Process proxy credentials settings
                    if 'proxy' in username:
                        clear_credentials = credential['clear_password']
                        if 'proxy_password' in clear_credentials:
                            proxy_creds = json.loads(clear_credentials)
                            proxy_clear_password = str(proxy_creds['proxy_password'])
                            #TODO: Review this part as it's seems to not be used
                    # Otherwise, keep it as a standard user
                    else:
                        # Only keep the value if it's a clear dictionnary
                        if "password" in credential['clear_password']:
                            clear_password = json.loads(credential['clear_password'])
                            self._passwords[username] = clear_password["password"]

        self.__instances = {}
        instances_by_account_name = {}

        # Open and read the file with the instances information
        instances_file = os.path.join(os.environ['SPLUNK_HOME'], 'etc', 'apps', 'TA-thehive-cortex','lookups', 'thehive_cortex_instances.csv')
        
        with open(instances_file, 'r') as file:
            content = csv.reader(file)
            header = next(content)
            for line in content:
                # Build the row as a dict
                row = {}
                for i in range(0,len(line)):
                    row[header[i]] = line[i]
                self.logger_file.debug(id="S5",message="New instance detected, getting " + str(row))
                # Process the new instance
                row_id = row["id"]
                del row["id"]

                # Keep information for storage password
                if (row["account_name"] not in instances_by_account_name):
                    instances_by_account_name[row["account_name"]] = [row_id]
                else:
                    instances_by_account_name[row["account_name"]].append(row_id)
                
                # get self.client certificate if it's specified

                if row["client_cert"] != "-" and re.search(r"^[-A-Za-z0-9+/]+={0,3}$", row["client_cert"]):
                    self.logger_file.debug(id="S6",message="Base64 client certificate found")
                    try:
                        client_certificate_pem = base64.b64decode(row["client_cert"]).decode()

                        client_certificate_path = os.path.join(os.environ['SPLUNK_HOME'], 'etc', 'apps', 'TA-thehive-cortex', 'local')
                        self.logger_file.debug(id="S7",message=f"Client certificate path: {client_certificate_path}")

                        os.makedirs(client_certificate_path, exist_ok=True)
                        self.logger_file.debug(id="S8",message="Client certificate path checked")

                        client_certificate = os.path.join(client_certificate_path, "certificate-%s.pem" % datetime.date.today().year)
                        self.logger_file.debug(id="S9",message=f"Client certificate filename: {client_certificate}")

                        with open(client_certificate,"w") as fh:
                            fh.write(client_certificate_pem)
                        self.logger_file.debug(id="S10",message="Client certificate written")

                        row["client_cert"] = client_certificate
                    except ValueError:
                        self.logger_file.warn(id="S11",message="Client certificate base 64 decoding has failed")
                    except PermissionError as error:
                        self.logger_file.warn(id="S12",message=f"Client certificate permission error for: {error.filename}")

                elif row["client_cert"] != "-" and ".." not in row["client_cert"]:
                    client_certificate = os.path.join(os.environ['SPLUNK_HOME'], 'etc', 'apps', 'TA-thehive-cortex','local', row["client_cert"])
                    if os.path.exists(client_certificate):
                        row["client_cert"] = client_certificate
                    else:
                        self.logger_file.warn(id="S13",message="Be aware that a client certificate for instance \""+str(row_id)+"\" was provided but the file doesn't exist: "+client_certificate)

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

                # If nothing is defined for the URI, then use the root by default
                if "uri" not in row or row["uri"] is None or row["uri"] == "-":
                    row["uri"] = "/"

                self.logger_file.debug(id="S14",message="New instance parsed, adding key \"" + str(row_id) + "\" " + str(row))
                # Store the new instance
                row_dict = json.loads(json.dumps(row))
                self.__instances[row_id] = row_dict

        # Get additional parameters
        self.__additional_parameters = self.readDefaultLocalConfiguration("ta_thehive_cortex_settings.conf")["additional_parameters"]
        self.logger_file.debug(id="S15",message="Getting these additional parameters: " + str(self.__additional_parameters))

        # Get username of account name
        usernames_by_account = self.readConfFile("local","ta_thehive_cortex_account.conf")
        for account in instances_by_account_name.keys():
            instances_of_account_name = instances_by_account_name[account]
            username = usernames_by_account[account]["username"]
            for i in instances_of_account_name:
                    self.__instances[i]["username"] = username 
        self.logger_file.debug(id="S20",message="Getting these usernames from account: "+str(self.__instances))

        if client is not None:
            # Get storage passwords for account passwords
            for account in instances_by_account_name.keys():
                # Get account details by instance
                    instances_of_account_name = instances_by_account_name[account]
                    password = self.getAccountPassword(account)
                    for i in instances_of_account_name:
                        self.__instances[i]["password"] = password
            self.logger_file.debug(id="S25",message="Successfully recovering passwords from storage passwords")

    def readConfFile(self, folder, filename):
        """ This function is used to retrieve information from a .conf file stored in a specified folder in this application """
        conf = {}

        # Open and read the conf file
        conf_file = os.path.join(os.environ['SPLUNK_HOME'], 'etc', 'apps', 'TA-thehive-cortex',folder, filename)
        if os.path.isfile(conf_file):
            with open(conf_file, 'r') as file:
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
                                conf[stanza][skey] += [value.rstrip('\n')]
                            else:
                                conf[stanza][skey] = [value.rstrip('\n')] + [conf[skey]]
                        else:
                            conf[stanza][skey] = value.rstrip('\n')
            self.logger_file.debug(id="S26",message="Configuration "+folder+"/"+filename+" was read: "+str(conf))
        else:
            self.logger_file.debug(id="S27",message="Configuration "+folder+"/"+filename+" doesn't exist.")
        return conf

    def readDefaultLocalConfiguration(self, filename):
        """ This function is used to retrieve information from a default/local configuration merged dictionnary where local is prior to default settings """

        # Open and read the default file
        default = self.readConfFile('default', filename)
        # Do the same with the local file if it's existing and merge information
        local = self.readConfFile('local', filename)

        # Recovered configuration for the filename
        self.logger_file.debug(id="S28",message="Configuration retrieved for the filename '"+filename+"': "+str({**default, **local}))

        return {**default, **local}

    def sanitizeInstance(self, instance):
        result = instance
        result["password"] = "**********"
        return result

    def getAccountPassword(self, account):
        """ Get storage passwords for the account password """
        password = None
        if account in self._passwords:
            password = self._passwords[account]
        else:
            self.logger_file.debug(id="S29",message="This account ("+account+") doesn't exist in your configuration and it's password can't be retrieved")
        return password

    def getInstanceURL(self, instance_id):
        """ This function returns the URL of the given instance """
        try:
            instance = self.__instances[instance_id]
        except KeyError as e:
            self.logger_file.error(id="S30",message="This instance ID ("+instance_id+") doesn't exist in your configuration")
            sys.exit(30)

        # Empty the root URI as it will be filled by the API library directly
        uri = str(instance["uri"]) if str(instance["uri"])!="/" else ""
        
        self.logger_file.debug(id="S30",message="This instance ID ("+str(instance_id)+") returns: "+str(self.sanitizeInstance(instance)))
        return "https://"+instance["host"]+":"+str(instance["port"])+uri

    def getInstanceUsernameApiKey(self, instance_id):
        """ This function returns the Username/Secret (password or API key) of the given instance """
        try:
            instance = self.__instances[instance_id]
        except KeyError as e:
            self.logger_file.error(id="S31",message="This instance ID ("+instance_id+") doesn't exist in your configuration")
            sys.exit(31)

        if "username" not in instance:
            instance["username"] = "-"
            instance["password"] = "-"
        elif "password" not in instance:
            instance["password"] = None
        self.logger_file.debug(id="S35",message="This instance ID ("+str(instance_id)+") returns: "+str(instance["username"]))
        return (instance["username"], instance["password"])

    def getInstanceSetting(self, instance_id, setting):
        """ This function returns the setting for the given instance """
        instance = None
        if instance_id in self.__instances and setting in self.__instances[instance_id]:
            instance = self.__instances[instance_id][setting]
            self.logger_file.debug(id="S40",message="this instance id ("+str(instance_id)+") returns: "+str(setting)+"="+str(instance))
        else:
            self.logger_file.warn(id="S41",message="Can't recover the setting \""+str(setting)+"\" for the instance \""+str(instance_id)+"\"")
        return instance

    def getTheHiveDefaultInstance(self):
        """ This function returns the default instance ID of a TheHive instance if set"""
        param = self.__additional_parameters["thehive_default_instance"] if "thehive_default_instance" in self.__additional_parameters else None
        self.logger_file.debug(id="S45",message="Getting this parameter : thehive_default_instance="+str(param))
        return param

    def getTheHiveCasesMax(self):
        """ This function returns the maximum number of cases to return of a TheHive instance """
        param = self.__additional_parameters["thehive_max_cases"] if "thehive_max_cases" in self.__additional_parameters else 100
        self.logger_file.debug(id="S45",message="Getting this parameter : thehive_max_cases="+str(param))
        return param

    def getTheHiveCasesSort(self):
        """ This function returns the sort key to use for cases of a TheHive instance """
        param = self.__additional_parameters["thehive_sort_cases"] if "thehive_sort_cases" in self.__additional_parameters else "-startedAt"
        param = Desc(param[1:]) if param[0] == "-" else Asc(param)
        self.logger_file.debug(id="S50",message="Getting this parameter: thehive_sort_cases="+str(param))
        return param

    def getTheHiveAlertsMax(self):
        """ This function returns the maximum number of alerts to return of a TheHive instance """
        param = self.__additional_parameters["thehive_max_alerts"] if "thehive_max_alerts" in self.__additional_parameters else 100
        self.logger_file.debug(id="S51",message="Getting this parameter: thehive_max_alerts="+str(param))
        return param

    def getTheHiveAlertsSort(self):
        """ This function returns the sort key to use for alerts of a TheHive instance """
        param = self.__additional_parameters["thehive_sort_alerts"] if "thehive_sort_alerts" in self.__additional_parameters else "-date"
        param = Desc(param[1:]) if param[0] == "-" else Asc(param)
        self.logger_file.debug(id="S52",message="Getting this parameter: thehive_sort_alerts="+str(param))
        return param

    def getTheHiveTTPCatalogName(self):
        """ This function returns the TTP Catalog name of a TheHive instance """
        param = self.__additional_parameters["thehive_ttp_catalog_name"] if "thehive_ttp_catalog_name" in self.__additional_parameters else "Enterprise Attack"
        self.logger_file.debug(id="S53",message="Getting this parameter: thehive_ttp_catalog_name="+str(param))
        return param

    def getCortexJobsMax(self):
        """ This function returns the maximum number of jobs to return of a Cortex instance """
        param = self.__additional_parameters["cortex_max_jobs"] if "cortex_max_jobs" in self.__additional_parameters else 100
        self.logger_file.debug(id="S54",message="Getting this parameter: "+str(param))
        return param

    def getCortexJobsSort(self):
        """ This function returns the sort key to use for jobs of a Cortex instance """
        param = self.__additional_parameters["cortex_sort_jobs"] if "cortex_sort_jobs" in self.__additional_parameters else "-createdAt"
        self.logger_file.debug(id="S55",message="Getting this parameter: "+str(param))
        return param

    def checkAndValidate(self, d, name, default="", is_mandatory=False):
        """ This function is use to check and validate an expected value format """
        if name in d:
            self.logger_file.debug(id="S60",message="Found parameter \""+str(name)+"\"="+str(d[name]))
            return d[name]
        else:
            if is_mandatory:
                self.logger_file.debug(id="S66",message="Missing parameter (no \""+str(name)+"\" field found)")
                sys.exit(66)
            else:
                self.logger_file.debug(id="S67",message="Parameter \""+str(name)+"\" not found, using default value=\""+str(default)+"\"")
                return default 


