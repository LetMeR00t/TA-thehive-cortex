# encoding = utf-8
import sys
import ta_thehive_cortex_declare
from thehive4py.client import TheHiveApi
from common import LoggerFile, Settings
import splunklib.client as client
from ta_logging import setup_logging
import certifi

def initialize_thehive_instances(keywords, settings, acronym, logger_name="script"):
    """ This function is used to initialize a TheHive instance """
    logger = setup_logging(logger_name)
    logger_file = LoggerFile(logger, acronym)
    
    # Check the existence of the instance_id
    if len(keywords) == 1:
        instances_id = keywords[0].split(",")
    else:
        logger_file.error(id="TH1",message="MISSING_INSTANCE_ID - No instance ID was given to the script")
        exit(1)

    instances = []
    for instance_id in instances_id:
        instances.append(create_thehive_instance(instance_id, settings, logger, acronym=acronym))

    return instances 

def create_thehive_instance(instance_id, settings, logger, acronym):
    """ This function is used to create an instance of TheHive """
    logger_file = LoggerFile(logger, acronym)
    # Initialize settings
    token = settings["sessionKey"] if "sessionKey" in settings else settings["session_key"]
    spl = client.connect(app="TA-thehive-cortex",owner="nobody",token=token)
    logger_file.debug(id="TH5",message="Connection to Splunk done")
    configuration = Settings(spl, settings, logger_file)
    logger_file.debug(id="TH6",message="Settings recovered")

    defaults = {
        "MAX_CASES_DEFAULT": configuration.getTheHiveCasesMax(),
        "SORT_CASES_DEFAULT": configuration.getTheHiveCasesSort(),
        "MAX_ALERTS_DEFAULT": configuration.getTheHiveAlertsMax(),
        "SORT_ALERTS_DEFAULT": configuration.getTheHiveAlertsSort(),
        "TTP_CATALOG_NAME": configuration.getTheHiveTTPCatalogName(),
        "MAX_CREATION_RETRY": configuration.getTheHiveCreationMaxRetry()
    }

    # Get default instance if any is set
    thehive_default_instance = configuration.getTheHiveDefaultInstance()
    instance_id_final = thehive_default_instance if instance_id == "<default>" else instance_id

    if instance_id_final == "" and instance_id == "<default>":
        logger_file.error(id="TH10",message="Your alert is using the <default> instance ID setting which is empty in your configuration page. Please update the parameter accordingly")
        sys.exit(10)

    # Create the TheHive instance
    (thehive_username, thehive_secret) = configuration.getInstanceUsernameApiKey(instance_id_final)
    thehive_url = configuration.getInstanceURL(instance_id_final)
    thehive_authentication_type = configuration.getInstanceSetting(instance_id_final,"authentication_type")
    thehive_proxies = configuration.getInstanceSetting(instance_id_final,"proxies")
    thehive_cert = configuration.getInstanceSetting(instance_id_final,"client_cert")
    thehive_cert = None if thehive_cert == "-" else thehive_cert
    thehive_organisation = configuration.getInstanceSetting(instance_id_final,"organisation")
    thehive_version = configuration.getInstanceSetting(instance_id_final,"type") 
    thehive = None

    if (thehive_authentication_type == "password"):
        logger_file.debug(id="TH15",message="TheHive instance will be initialized with a password (not an API key)")
        thehive = TheHive(url=thehive_url, username=thehive_username, password=thehive_secret, proxies=thehive_proxies, verify=True, cert=thehive_cert, organisation=thehive_organisation, version=thehive_version, sid=settings["sid"], logger_file=logger_file)
    elif (thehive_authentication_type == "api_key"):
        logger_file.debug(id="TH16",message="TheHive instance will be initialized with an API Key (not a password)")
        thehive = TheHive(url=thehive_url, apiKey=thehive_secret, proxies=thehive_proxies, verify=True, cert=thehive_cert, organisation=thehive_organisation, version=thehive_version, sid=settings["sid"], logger_file=logger_file)
    else:
        logger_file.error(id="TH20",message="WRONG_AUTHENTICATION_TYPE - Authentication type is not one of the expected values (password or api_key), given value: "+thehive_authentication_type)
        exit(20)

    return (thehive, configuration, defaults, logger_file, instance_id) 

def create_thehive_instance_modular_input(instance_id, helper, acronym):
    """ This function is used to create an instance of TheHive specifically for modular inputs that don't provide settings information """
    logger_file = LoggerFile(helper.logger, acronym)
    
    # Initialize settings
    configuration = Settings(client=None, settings=None, logger_file=logger_file)
    logger_file.debug(id="TH25",message="Settings recovered")

    # Get default instance if any is set
    thehive_default_instance = configuration.getTheHiveDefaultInstance()
    instance_id_final = thehive_default_instance if instance_id == "<default>" else instance_id

    if instance_id_final == "" and instance_id == "<default>":
        logger_file.error(id="TH30",message="Your alert is using the <default> instance ID setting which is empty in your configuration page. Please update the parameter accordingly")
        sys.exit(30)

    # Create the TheHive instance
    (thehive_username, thehive_secret) = configuration.getInstanceUsernameApiKey(instance_id_final)
    # As we are in a modular input, we can't retrieve the thehive_secret information, we will use the helper instead
    thehive_secret = helper.get_user_credential_by_username(thehive_username)["password"]
    thehive_url = configuration.getInstanceURL(instance_id_final)
    thehive_authentication_type = configuration.getInstanceSetting(instance_id_final,"authentication_type")
    thehive_proxies = configuration.getInstanceSetting(instance_id_final,"proxies")
    thehive_cert = configuration.getInstanceSetting(instance_id_final,"client_cert")
    thehive_cert = None if thehive_cert == "-" else thehive_cert
    thehive_organisation = configuration.getInstanceSetting(instance_id_final,"organisation")
    thehive_version = configuration.getInstanceSetting(instance_id_final,"type") 
    thehive = None

    if (thehive_authentication_type == "password"):
        logger_file.debug(id="TH35",message="TheHive instance will be initialized with a password (not an API key)")
        thehive = TheHive(url=thehive_url, username=thehive_username, password=thehive_secret, proxies=thehive_proxies, verify=True, cert=thehive_cert, organisation=thehive_organisation, version=thehive_version, sid=None, logger_file=logger_file)
    elif (thehive_authentication_type == "api_key"):
        logger_file.debug(id="TH40",message="TheHive instance will be initialized with an API Key (not a password)")
        thehive = TheHive(url=thehive_url, apiKey=thehive_secret, proxies=thehive_proxies, verify=True, cert=thehive_cert, organisation=thehive_organisation, version=thehive_version, sid=None, logger_file=logger_file)
    else:
        logger_file.error(id="TH50",message="WRONG_AUTHENTICATION_TYPE - Authentication type is not one of the expected values (password or api_key), given value: "+thehive_authentication_type)
        exit(20)

    return (thehive, configuration, logger_file) 

class TheHive(TheHiveApi):
    """ This class is used to represent a TheHive instance
        Most of parameters are reused from the python library of TheHive
    """

    def __init__(self, url = None, username = None, password = None, apiKey = None, proxies={}, cert = None , verify = True, organisation = None, version = None, sid = None, logger_file = None):

        self._logger_file = logger_file

        self.logger_file.debug(id="TH1",message="Version is: "+version)

        try :
            if apiKey is not None:
                super().__init__(url=str(url),username=username,apikey=str(apiKey),proxies=proxies,verify=verify,cert=cert,organisation=organisation)
            elif password is not None:
                super().__init__(url=str(url),username=username,password=password,proxies=proxies,verify=verify,cert=cert,organisation=organisation)
            else:
                self.logger_file.error(id="TH30",message="THE_HIVE_AUTHENTICATION - Password AND API Key are null values")
                exit(30)

            self.logger_file.debug(id="TH40",message="TheHive instance is initialized, try a request to {}".format(url))

            # Try to connect to the API by getting information about the user used
            test = self.user.get_current()

            if  "_id" not in test:
                self.logger_file.error(id="TH45",message="THE_HIVE_AUTHENTICATION_RESPONSE - Server didn't respond with a valid response.")
                self.logger_file.debug(id="TH46",message="Payload content - Headers: "+str(self.session.headers))
                self.logger_file.debug(id="TH47",message="Payload content - URL: "+str(self.session.hive_url))
            elif apiKey is not None:
                self.logger_file.debug(id="TH50",message="TheHive API connection to (URL=\""+url+"\" is successful")
            elif password is not None:
                self.logger_file.debug(id="TH60",message="TheHive API connection to (URL=\""+url+"\",Username=\""+username+"\") is successful")

        except Exception as e:
            if "CERTIFICATE_VERIFY_FAILED" in str(e):
                self.logger_file.warn(id="TH85",message="THE_HIVE_CERTIFICATE_FAILED - It seems that the certificate verification failed. Please check that the certificate authority is added to \""+str(certifi.where())+"\". Complete error: "+str(e))
                sys.exit(85)
            elif "HANDSHAKE_FAILURE" in str(e):
                self.logger_file.warn(id="TH90",message="THE_HIVE_HANDHSHAKE_FAILURE - It seems that the SSL handshake failed. A possible solution is to check if the remote server/proxy is not expecting a client certificate. Complete error: "+str(e))
                sys.exit(90)
            elif "Proxy Authentication Required" in str(e):
                self.logger_file.warn(id="TH95",message="THE_HIVE_PROXY_AUTHENTICATION_ERROR - It seems that the connection to the proxy has failed as it's required an authentication (none was provided or the username/password is not working). Proxy information are: "+str(proxies)+". Complete error: "+str(e))
                sys.exit(95)
            elif "ProxyError" in str(e):
                self.logger_file.warn(id="TH100",message="THE_HIVE_PROXY_ERROR - It seems that the connection to the proxy has failed. Proxy information are: "+str(proxies)+". Complete error: "+str(e))
                sys.exit(100)
            else:
                self.logger_file.error(id="TH110",message="THEHIVE_CONNECTION_ERROR - Error: "+str(e)+". Check any error in the TheHive instance logs following this API REST call. If the error is persisting after several tries, please raise an issue to the application maintainer.")
                sys.exit(110)

        self.__sid = sid

    @property
    def logger_file(self):
        return self._logger_file
