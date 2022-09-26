# encoding = utf-8
import sys
import ta_thehive_cortex_declare
from thehive4py.api import TheHiveApi
from thehive4py.models import Version
import thehive4py.exceptions
from common import Settings
import splunklib.client as client
from ta_logging import setup_logging
import certifi

def initialize_thehive_instance(keywords, settings, logger_name="script"):
    """ This function is used to initialize a TheHive instance """
    logger = setup_logging(logger_name)

    # Check the existence of the instance_id
    if len(keywords) == 1:
        instance_id = keywords[0]
    else:
        logger.error("[TH1-ERROR] MISSING_INSTANCE_ID - No instance ID was given to the script")
        exit(1)

    return create_thehive_instance(instance_id, settings, logger)

def create_thehive_instance(instance_id, settings, logger):
    """ This function is used to create an instance of TheHive """
    # Initialize settings
    token = settings["sessionKey"] if "sessionKey" in settings else settings["session_key"]
    spl = client.connect(app="TA-thehive-cortex",owner="nobody",token=token)
    logger.debug("[TH5] Connection to Splunk done")
    configuration = Settings(spl, settings, logger)
    logger.debug("[TH6] Settings recovered")

    defaults = {
        "MAX_CASES_DEFAULT": configuration.getTheHiveCasesMax(),
        "SORT_CASES_DEFAULT": configuration.getTheHiveCasesSort(),
        "MAX_ALERTS_DEFAULT": configuration.getTheHiveAlertsMax(),
        "SORT_ALERTS_DEFAULT": configuration.getTheHiveAlertsSort()
    }

    # Create the TheHive instance
    (thehive_username, thehive_secret) = configuration.getInstanceUsernameApiKey(instance_id)
    thehive_url = configuration.getInstanceURL(instance_id)
    thehive_authentication_type = configuration.getInstanceSetting(instance_id,"authentication_type")
    thehive_proxies = configuration.getInstanceSetting(instance_id,"proxies")
    thehive_cert = configuration.getInstanceSetting(instance_id,"client_cert")
    thehive_cert = None if thehive_cert == "-" else thehive_cert
    thehive_verify = configuration.getInstanceSetting(instance_id,"verify")
    thehive_organisation = configuration.getInstanceSetting(instance_id,"organisation")
    thehive_version = configuration.getInstanceSetting(instance_id,"type") 
    thehive = None

    if (thehive_authentication_type == "password"):
        logger.debug("[TH15] TheHive instance will be initialized with a password (not an API key)")
        thehive = TheHive(url=thehive_url, username=thehive_username, password=thehive_secret, proxies=thehive_proxies, verify=thehive_verify, cert=thehive_cert, organisation=thehive_organisation, version=thehive_version, sid=settings["sid"], logger=logger)
    elif (thehive_authentication_type == "api_key"):
        logger.debug("[TH16] TheHive instance will be initialized with an API Key (not a password)")
        thehive = TheHive(url=thehive_url, apiKey=thehive_secret, proxies=thehive_proxies, verify=thehive_verify, cert=thehive_cert, organisation=thehive_organisation, version=thehive_version, sid=settings["sid"], logger=logger)
    else:
        logger.error("[TH20-ERROR] WRONG_AUTHENTICATION_TYPE - Authentication type is not one of the expected values (password or api_key), given value: "+thehive_authentication_type)
        exit(20)

    return (thehive, configuration, defaults, logger) 



class TheHive(TheHiveApi):
    """ This class is used to represent a TheHive instance
        Most of parameters are reused from the python library of TheHive
    """

    def __init__(self, url = None, username = None, password = None, apiKey = None, proxies={}, cert = None , verify = True, organisation = None, version = None, sid = "", logger = None):

        self.logger = logger
        if version=="TheHive5":
            self.logger.debug("[TH24] TheHive version is 5.x")
            if sys.version_info[0] < 3:
                version = Version.THEHIVE_5
            else:
                version = Version.THEHIVE_5.value
        elif version=="TheHive4":
            self.logger.debug("[TH25] TheHive version is 4.x")
            if sys.version_info[0] < 3:
                version = Version.THEHIVE_4
            else:
                version = Version.THEHIVE_4.value
        elif version=="TheHive3":
            self.logger.debug("[TH26] TheHive version is 3.x")
            if sys.version_info[0] < 3:
                version = Version.THEHIVE_3
            else:
                version = Version.THEHIVE_3.value
        else:
            self.logger.warning("[TH27] No valid version of TheHive was found for the given type: \""+str(version)+"\". Default will be used (TheHive 3)")
            if sys.version_info[0] < 3:
                version = Version.THEHIVE_3
            else:
                version = Version.THEHIVE_3.value

        try :
            if sys.version_info[0] < 3:
                if apiKey is not None:
                    TheHiveApi.__init__(self,url=str(url),principal=str(apiKey),password=None,proxies=proxies,verify=verify,cert=cert,organisation=organisation,version=version)
                elif password is not None:
                    TheHiveApi.__init__(self,url=str(url),principal=username,password=password,proxies=proxies,verify=verify,cert=cert,organisation=organisation,version=version)
                else:
                    self.logger.error("[TH30-ERROR] THE_HIVE_AUTHENTICATION - Password AND API Key are null values")
                    exit(30)
            else:
                if apiKey is not None:
                    super().__init__(url=str(url),principal=str(apiKey),password=None,proxies=proxies,verify=verify,cert=cert,organisation=organisation,version=version)
                elif password is not None:
                    super().__init__(url=str(url),principal=username,password=password,proxies=proxies,verify=verify,cert=cert,organisation=organisation,version=version)
                else:
                    self.logger.error("[TH31-ERROR] THE_HIVE_AUTHENTICATION - Password AND API Key are null values")
                    exit(31)

            self.logger.debug("[TH35] TheHive instance is initialized")

            # Try to connect to the API by recovering some cases
            test = self.find_cases(query={}, range='all')
            if  test.status_code >= 300:
                self.logger.error("[TH36-ERROR] THE_HIVE_AUTHENTICATION_RESPONSE - Server didn't send a 2xx response. Got: "+str(test.status_code))
                self.logger.debug("[TH37] Payload content - Headers: "+str(test.request.headers))
                self.logger.debug("[TH37] Payload content - URL: "+str(test.request.url))

            if apiKey is not None:
                self.logger.debug("[TH40] TheHive API connection to (URL=\""+url+"\" is successful")
            elif password is not None:
                self.logger.debug("[TH41] TheHive API connection to (URL=\""+url+"\",Username=\""+username+"\") is successful")
        except thehive4py.exceptions.TheHiveException as e:
            if "CERTIFICATE_VERIFY_FAILED" in str(e):
                self.logger.warning("[TH45] THE_HIVE_CERTIFICATE_FAILED - It seems that the certificate verification failed. Please check that the certificate authority is added to \""+str(certifi.where())+"\". Complete error: "+str(e))
                sys.exit(45)
            elif "HANDSHAKE_FAILURE" in str(e):
                self.logger.warning("[TH46] THE_HIVE_HANDHSHAKE_FAILURE - It seems that the SSL handshake failed. A possible solution is to check if the remote server/proxy is not expecting a client certificate. Complete error: "+str(e))
                sys.exit(46)
            elif "Proxy Authentication Required" in str(e):
                self.logger.warning("[TH47] THE_HIVE_PROXY_AUTHENTICATION_ERROR - It seems that the connection to the proxy has failed as it's required an authentication (none was provided or the username/password is not working). Proxy information are: "+str(proxies)+". Complete error: "+str(e))
                sys.exit(47)
            elif "ProxyError" in str(e):
                self.logger.warning("[TH48] THE_HIVE_PROXY_ERROR - It seems that the connection to the proxy has failed. Proxy information are: "+str(proxies)+". Complete error: "+str(e))
                sys.exit(48)
            else:
                self.logger.error("[TH60-GENERIC-ERROR] THE_HIVE_CONNECTION_ERROR - Error: "+str(e))
                sys.exit(60)

        self.__sid = sid
