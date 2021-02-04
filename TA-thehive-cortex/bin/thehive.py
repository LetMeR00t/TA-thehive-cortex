import sys
import ta_thehive_cortex_declare
from thehive4py.api import TheHiveApi
from thehive4py.models import Version
import thehive4py.exceptions
from common import Settings
import json
import traceback
import splunklib.client as client
from ta_logging import setup_logging
import certifi


# Mapping for Severity codes
severityCode = {
        "LOW": 1,
        "MEDIUM": 2,
        "HIGH": 3,
        "CRITICAL": 4}


# Mapping for TLP/PAP codes
colorCode = {
        "WHITE": 0,
        "GREEN": 1,
        "AMBER": 2,
        "RED": 3}

def initialize_thehive_instance(keywords, settings, logger_name="script"):
    """ This function is used to initialize a TheHive instance """
    logger = setup_logging(logger_name)

    # Check the existence of the instance_id
    if len(keywords) == 1:
        instance_id = keywords[0]
    else:
        logger.error("[4-MISSING_INSTANCE_ID] No instance ID was given to the script")
        exit(4)

    return create_thehive_instance(instance_id, settings, logger)

def create_thehive_instance(instance_id, settings, logger):
    """ This function is used to create an instance of TheHive """
    # Initialize settings
    token = settings["sessionKey"] if "sessionKey" in settings else settings["session_key"]
    spl = client.connect(app="TA-thehive-cortex",owner="nobody",token=token)
    configuration = Settings(spl, settings, logger)

    defaults = {
        "MAX_CASES_DEFAULT": configuration.getTheHiveCasesMax(),
        "SORT_CASES_DEFAULT": configuration.getTheHiveCasesSort()
    }

    # Create the TheHive instance
    (thehive_username, thehive_secret) = configuration.getInstanceUsernameApiKey(instance_id)
    thehive_url = configuration.getInstanceURL(instance_id)
    thehive_authentication_type = configuration.getInstanceSetting(instance_id,"authentication_type")
    thehive_proxies = configuration.getInstanceSetting(instance_id,"proxies")
    thehive_cert = configuration.getInstanceSetting(instance_id,"cert")
    thehive_organisation = configuration.getInstanceSetting(instance_id,"organisation")
    thehive_version = configuration.getInstanceSetting(instance_id,"type") 
    thehive = None

    if (thehive_authentication_type == "password"):
        thehive = TheHive(url=thehive_url, username=thehive_username, password=thehive_secret, proxies=thehive_proxies, cert=thehive_cert, organisation=thehive_organisation, version=thehive_version, sid=settings["sid"], logger=logger)
    elif (thehive_authentication_type == "api_key"):
        thehive = TheHive(url=thehive_url, apiKey=thehive_secret, proxies=thehive_proxies, cert=thehive_cert, organisation=thehive_organisation, version=thehive_version, sid=settings["sid"], logger=logger)
    else:
        logger.error("[7-WRONG_AUTHENTICATION_TYPE] Authentication type is not one of the expected values (password or api_key), given value: "+thehive_authentication_type)
        exit(7)

    return (thehive, configuration, defaults, logger) 



class TheHive(TheHiveApi):

    """ This class is used to represent a TheHive instance
        Most of parameters are reused from the python library of TheHive
    """

    def __init__(self, url = None, username = None, password = None, apiKey = None, proxies={}, cert=True, organisation=None, version=None, sid = "", logger = None):

        self.logger = logger
        if version=="TheHive4":
            if sys.version_info[0] < 3:
                version = Version.THEHIVE_4
            else:
                version = Version.THEHIVE_4.value
        elif version=="TheHive3":
            if sys.version_info[0] < 3:
                version = Version.THEHIVE_3
            else:
                version = Version.THEHIVE_3.value
        else:
            self.logger.warning("No valid version of TheHive was found for the given type: \""+str(version)+"\". Default will be used (TheHive 3)")
            if sys.version_info[0] < 3:
                version = Version.THEHIVE_3
            else:
                version = Version.THEHIVE_3.value

        try :
            if sys.version_info[0] < 3:
                if apiKey is not None:
                    TheHiveApi.__init__(self,url=str(url),principal=str(apiKey),password=None,proxies=proxies,cert=cert,organisation=organisation,version=version)
                elif password is not None:
                    TheHiveApi.__init__(self,url=str(url),principal=username,password=password,proxies=proxies,cert=cert,organisation=organisation,version=version)
                else:
                    self.logger.error("[11-THE_HIVE_AUTHENTICATION] Password AND API Key are null values")
                    exit(11)
            else:
                if apiKey is not None:
                    super().__init__(url=str(url),principal=str(apiKey),password=None,proxies=proxies,cert=cert,organisation=organisation,version=version)
                elif password is not None:
                    super().__init__(url=str(url),principal=username,password=password,proxies=proxies,cert=cert,organisation=organisation,version=version)
                else:
                    self.logger.error("[11-THE_HIVE_AUTHENTICATION] Password AND API Key are null values")
                    exit(11)

            # Try to connect to the API by recovering some cases
            self.find_cases(query={}, range='all')

            if apiKey is not None:
                self.logger.debug("TheHive API connection to (URL=\""+url+"\",API key=\""+apiKey+"\") is successful")
            elif password is not None:
                self.logger.debug("TheHive API connection to (URL=\""+url+"\",Username=\""+username+"\",Password=\""+password+"\") is successful")
        except thehive4py.exceptions.TheHiveException as e:
            if "CERTIFICATE_VERIFY_FAILED" in str(e):
                self.logger.info("[12a-THE_HIVE_CERTIFICATE_FAILED] It seems that the certificate verification failed. Please check that the certificate authority is added to \""+str(certifi.where())+"\". Complete error: "+str(e))
            else:
                self.logger.error("[12b-THE_HIVE_CONNECTION_ERROR] Error: "+str(e))
            sys.exit(12)

        self.__sid = sid
