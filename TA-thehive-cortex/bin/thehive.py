# encoding = utf-8
import sys
import ta_thehive_cortex_declare
from thehive4py.client import TheHiveApi
from thehive4py.errors import TheHiveError
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
    spl = client.connect(token=token)
    logger.debug("[TH5] Connection to Splunk done")
    configuration = Settings(spl, settings, logger)
    logger.debug("[TH6] Settings recovered")

    defaults = {
        "MAX_CASES_DEFAULT": configuration.getTheHiveCasesMax(),
        "SORT_CASES_DEFAULT": configuration.getTheHiveCasesSort(),
        "MAX_ALERTS_DEFAULT": configuration.getTheHiveAlertsMax(),
        "SORT_ALERTS_DEFAULT": configuration.getTheHiveAlertsSort(),
        "TTP_CATALOG_NAME": configuration.getTheHiveTTPCatalogName()
    }

    # Get default instance if any is set
    thehive_default_instance = configuration.getTheHiveDefaultInstance()
    instance_id_final = thehive_default_instance if instance_id == "<default>" else instance_id

    if instance_id_final == "" and instance_id == "<default>":
        logger.error("[TH10-ERROR] Your alert is using the <default> instance ID setting which is empty in your configuration page. Please update the parameter accordingly")
        sys.exit(10)

    # Create the TheHive instance
    (thehive_username, thehive_secret) = configuration.getInstanceUsernameApiKey(instance_id_final)
    thehive_url = configuration.getInstanceURL(instance_id_final)
    thehive_authentication_type = configuration.getInstanceSetting(instance_id_final,"authentication_type")
    thehive_proxies = configuration.getInstanceSetting(instance_id_final,"proxies")
    thehive_cert = configuration.getInstanceSetting(instance_id_final,"client_cert")
    thehive_cert = None if thehive_cert == "-" else thehive_cert
    thehive_verify = configuration.getInstanceSetting(instance_id_final,"verify")
    thehive_organisation = configuration.getInstanceSetting(instance_id_final,"organisation")
    thehive_version = configuration.getInstanceSetting(instance_id_final,"type") 
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

def create_thehive_instance_modular_input(instance_id, helper):
    """ This function is used to create an instance of TheHive specifically for modular inputs that don't provide settings information """
    logger = helper.logger
    
    # Initialize settings
    configuration = Settings(client=None, settings=None, logger=logger)
    logger.debug("[TH25] Settings recovered")

    # Get default instance if any is set
    thehive_default_instance = configuration.getTheHiveDefaultInstance()
    instance_id_final = thehive_default_instance if instance_id == "<default>" else instance_id

    if instance_id_final == "" and instance_id == "<default>":
        logger.error("[TH26-ERROR] Your alert is using the <default> instance ID setting which is empty in your configuration page. Please update the parameter accordingly")
        sys.exit(10)

    # Create the TheHive instance
    (thehive_username, thehive_secret) = configuration.getInstanceUsernameApiKey(instance_id_final)
    # As we are in a modular input, we can't retrieve the thehive_secret information, we will use the helper instead
    thehive_secret = helper.get_user_credential_by_username(thehive_username)["password"]
    thehive_url = configuration.getInstanceURL(instance_id_final)
    thehive_authentication_type = configuration.getInstanceSetting(instance_id_final,"authentication_type")
    thehive_proxies = configuration.getInstanceSetting(instance_id_final,"proxies")
    thehive_cert = configuration.getInstanceSetting(instance_id_final,"client_cert")
    thehive_cert = None if thehive_cert == "-" else thehive_cert
    thehive_verify = configuration.getInstanceSetting(instance_id_final,"verify")
    thehive_organisation = configuration.getInstanceSetting(instance_id_final,"organisation")
    thehive_version = configuration.getInstanceSetting(instance_id_final,"type") 
    thehive = None

    if (thehive_authentication_type == "password"):
        logger.debug("[TH30] TheHive instance will be initialized with a password (not an API key)")
        thehive = TheHive(url=thehive_url, username=thehive_username, password=thehive_secret, proxies=thehive_proxies, verify=thehive_verify, cert=thehive_cert, organisation=thehive_organisation, version=thehive_version, sid=None, logger=logger)
    elif (thehive_authentication_type == "api_key"):
        logger.debug("[TH40] TheHive instance will be initialized with an API Key (not a password)")
        thehive = TheHive(url=thehive_url, apiKey=thehive_secret, proxies=thehive_proxies, verify=thehive_verify, cert=thehive_cert, organisation=thehive_organisation, version=thehive_version, sid=None, logger=logger)
    else:
        logger.error("[TH50-ERROR] WRONG_AUTHENTICATION_TYPE - Authentication type is not one of the expected values (password or api_key), given value: "+thehive_authentication_type)
        exit(20)

    return (thehive, configuration, logger) 

class TheHive(TheHiveApi):
    """ This class is used to represent a TheHive instance
        Most of parameters are reused from the python library of TheHive
    """

    def __init__(self, url = None, username = None, password = None, apiKey = None, proxies={}, cert = None , verify = True, organisation = None, version = None, sid = None, logger = None):

        self.logger = logger

        self.logger.debug("[TH60] Version is: "+version)

        try :
            if apiKey is not None:
                super().__init__(url=str(url),username=username,apikey=str(apiKey),proxies=proxies,verify=verify,cert=cert,organisation=organisation)
            elif password is not None:
                super().__init__(url=str(url),username=username,password=password,proxies=proxies,verify=verify,cert=cert,organisation=organisation)
            else:
                self.logger.error("[TH65-ERROR] THE_HIVE_AUTHENTICATION - Password AND API Key are null values")
                exit(31)

            self.logger.debug("[TH70] TheHive instance is initialized, try a request to {}".format(url))

            # Try to connect to the API by getting information about the user used
            test = self.user.get_current()

            if  "_id" not in test:
                self.logger.error("[TH75-ERROR] THE_HIVE_AUTHENTICATION_RESPONSE - Server didn't respond with a valid response.")
                self.logger.debug("[TH75] Payload content - Headers: "+str(self.session.headers))
                self.logger.debug("[TH75] Payload content - URL: "+str(self.session.hive_url))
            elif apiKey is not None:
                self.logger.debug("[TH80] TheHive API connection to (URL=\""+url+"\" is successful")
            elif password is not None:
                self.logger.debug("[TH80] TheHive API connection to (URL=\""+url+"\",Username=\""+username+"\") is successful")

        except TheHiveError as e:
            if "CERTIFICATE_VERIFY_FAILED" in str(e):
                self.logger.warning("[TH85] THE_HIVE_CERTIFICATE_FAILED - It seems that the certificate verification failed. Please check that the certificate authority is added to \""+str(certifi.where())+"\". Complete error: "+str(e))
                sys.exit(45)
            elif "HANDSHAKE_FAILURE" in str(e):
                self.logger.warning("[TH90] THE_HIVE_HANDHSHAKE_FAILURE - It seems that the SSL handshake failed. A possible solution is to check if the remote server/proxy is not expecting a client certificate. Complete error: "+str(e))
                sys.exit(46)
            elif "Proxy Authentication Required" in str(e):
                self.logger.warning("[TH95] THE_HIVE_PROXY_AUTHENTICATION_ERROR - It seems that the connection to the proxy has failed as it's required an authentication (none was provided or the username/password is not working). Proxy information are: "+str(proxies)+". Complete error: "+str(e))
                sys.exit(47)
            elif "ProxyError" in str(e):
                self.logger.warning("[TH100] THE_HIVE_PROXY_ERROR - It seems that the connection to the proxy has failed. Proxy information are: "+str(proxies)+". Complete error: "+str(e))
                sys.exit(48)
            else:
                self.logger.error("[TH110-GENERIC-ERROR] THE_HIVE_CONNECTION_ERROR - Error: "+str(e))
                sys.exit(60)

        self.__sid = sid
