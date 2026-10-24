# encoding = utf-8
# Author: Alexandre Demeyer <letmer00t@gmail.com>
#
# Copyright: LGPLv3 (https://www.gnu.org/licenses/lgpl-3.0.txt)
# Feel free to use the code, but please share the changes you've made

"""What `Settings` answers once loaded: configuration files, instances,
accounts and the global settings, each through a plain method.

Split out of `common` (#24) as a mixin of `Settings`. ⚠️ The getters stay
written one by one on purpose: `tools/checks/settings_are_used.py` reads
the source to prove each setting is consumed, and generated accessors
would leave it blind -- green, and wrong.
"""

import ta_thehive_cortex_declare  # noqa: F401  puts the vendored libs on sys.path

# Standard library imports
import os

# Third-party imports
from thehive4py.query.sort import Asc, Desc


class InstanceResolutionError(Exception):
    """An instance id does not match anything in the configuration.

    Raised instead of sys.exit(). A search command already turns any exception
    into a readable SPL error (Intersplunk.generateErrorResults); ending the
    process instead gave the user a search that stopped without a word.
    """


class MissingParameterError(Exception):
    """A mandatory parameter is absent. Same reasoning as above."""


class SettingsAccessors(object):
    """Read side of `Settings`; expects the attributes its `__init__` sets."""

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
        # Resolve ID if it's a technical ID
        instance_id_resolved = self._id_to_name.get(instance_id, instance_id)
        
        try:
            instance = self._instances[instance_id_resolved]
        except KeyError:
            message = (
                "This instance ID ("
                + str(instance_id_resolved)
                + ") doesn't exist in your configuration"
            )
            self.logger_file.error(id="S30", message=message)
            raise InstanceResolutionError(message)

        # Empty the root URI as it will be filled by the API library directly
        uri = str(instance["uri"]) if str(instance["uri"]) != "/" else ""

        self.logger_file.debug(
            id="S32",
            message="This instance ID ("
            + str(instance_id_resolved)
            + ") returns: "
            + str(self.sanitizeInstance(instance)),
        )
        return "https://" + instance["host"] + ":" + str(instance["port"]) + uri

    def getInstanceUsernameApiKey(self, instance_id):
        """This function returns the Username/Secret (password or API key) of the given instance"""
        # Resolve ID if it's a technical ID
        instance_id_resolved = self._id_to_name.get(instance_id, instance_id)

        try:
            instance = self._instances[instance_id_resolved]
        except KeyError:
            message = (
                "This instance ID ("
                + str(instance_id_resolved)
                + ") doesn't exist in your configuration"
            )
            self.logger_file.error(id="S31", message=message)
            raise InstanceResolutionError(message)

        if "username" not in instance:
            instance["username"] = "-"
            instance["password"] = "-"
        elif "password" not in instance:
            instance["password"] = None
        self.logger_file.debug(
            id="S35",
            message="This instance ID ("
            + str(instance_id_resolved)
            + ") returns: "
            + str(instance["username"]),
        )
        return (instance["username"], instance["password"])

    def getInstanceSetting(self, instance_id, setting):
        """This function returns the setting for the given instance"""
        # Resolve ID if it's a technical ID
        instance_id_resolved = self._id_to_name.get(instance_id, instance_id)

        instance = None
        if instance_id_resolved in self._instances and setting in self._instances[instance_id_resolved]:
            instance = self._instances[instance_id_resolved][setting]
            self.logger_file.debug(
                id="S40",
                message="this instance id ("
                + str(instance_id_resolved)
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
                + str(instance_id_resolved)
                + '"',
            )
        return instance

    def getTheHiveDefaultInstance(self):
        """This function returns the default instance ID of a TheHive instance if set"""
        param = (
            self._additional_parameters["thehive_default_instance"]
            if "thehive_default_instance" in self._additional_parameters
            else None
        )
        
        # Resolve ID if it's a technical ID
        param_resolved = self._id_to_name.get(param, param)

        self.logger_file.debug(
            id="S45",
            message="Getting this parameter : thehive_default_instance=" + str(param_resolved),
        )
        return param_resolved

    def getTheHiveCasesMax(self):
        """This function returns the maximum number of cases to return of a TheHive instance"""
        param = (
            self._additional_parameters["thehive_max_cases"]
            if "thehive_max_cases" in self._additional_parameters
            else 100
        )
        self.logger_file.debug(
            id="S46", message="Getting this parameter : thehive_max_cases=" + str(param)
        )
        return param

    def getTheHiveCasesSort(self):
        """This function returns the sort key to use for cases of a TheHive instance"""
        param = (
            self._additional_parameters["thehive_sort_cases"]
            if "thehive_sort_cases" in self._additional_parameters
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
            self._additional_parameters["thehive_max_alerts"]
            if "thehive_max_alerts" in self._additional_parameters
            else 100
        )
        self.logger_file.debug(
            id="S51", message="Getting this parameter: thehive_max_alerts=" + str(param)
        )
        return param

    def getTheHiveAlertsSort(self):
        """This function returns the sort key to use for alerts of a TheHive instance"""
        param = (
            self._additional_parameters["thehive_sort_alerts"]
            if "thehive_sort_alerts" in self._additional_parameters
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
            self._additional_parameters["thehive_ttp_catalog_name"]
            if "thehive_ttp_catalog_name" in self._additional_parameters
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
            self._additional_parameters["thehive_creation_attachment_prefix"]
            if "thehive_creation_attachment_prefix" in self._additional_parameters
            else "events_"
        )
        self.logger_file.debug(
            id="S54",
            message="Getting this parameter: thehive_creation_attachment_prefix="
            + str(param),
        )
        return param

    def getHttpTimeout(self):
        """This function returns the HTTP timeout, in seconds, for TheHive and Cortex calls"""
        param = (
            self._additional_parameters["thehive_cortex_http_timeout"]
            if "thehive_cortex_http_timeout" in self._additional_parameters
            else "60"
        )
        self.logger_file.debug(
            id="S57",
            message="Getting this parameter: thehive_cortex_http_timeout=" + str(param),
        )
        return param

    def getTheHiveCreationMaxRetry(self):
        """This function returns the maximum creation retry of a TheHive instance"""
        param = (
            self._additional_parameters["thehive_creation_max_retry"]
            if "thehive_creation_max_retry" in self._additional_parameters
            else "5"
        )
        self.logger_file.debug(
            id="S58",
            message="Getting this parameter: thehive_creation_max_retry=" + str(param),
        )
        return param

    def getCortexJobsMax(self):
        """This function returns the maximum number of jobs to return of a Cortex instance"""
        param = (
            self._additional_parameters["cortex_max_jobs"]
            if "cortex_max_jobs" in self._additional_parameters
            else 100
        )
        self.logger_file.debug(
            id="S55", message="Getting this parameter: " + str(param)
        )
        return param

    def getCortexJobMaxWait(self):
        """This function returns how long Cortex may hold a job report before answering

        ⚠️ Zero means "answer now", which is what this add-on has always done:
        a report asked for while the analyzer is still running comes back
        empty, and an empty report reads exactly like an analyzer that found
        nothing. A non-zero value is passed to Cortex as `waitreport?atMost=`,
        so the waiting happens server-side -- one call, not a polling loop."""
        param = (
            self._additional_parameters["cortex_job_max_wait"]
            if "cortex_job_max_wait" in self._additional_parameters
            else "0"
        )
        self.logger_file.debug(
            id="S68",
            message="Getting this parameter: cortex_job_max_wait=" + str(param),
        )
        return param

    def getCortexJobsSort(self):
        """This function returns the sort key to use for jobs of a Cortex instance"""
        param = (
            self._additional_parameters["cortex_sort_jobs"]
            if "cortex_sort_jobs" in self._additional_parameters
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
                message = 'Missing parameter (no "' + str(name) + '" field found)'
                self.logger_file.error(id="S66", message=message)
                raise MissingParameterError(message)
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
