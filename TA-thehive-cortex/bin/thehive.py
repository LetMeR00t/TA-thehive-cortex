import sys
import ta_thehive_cortex_declare
from thehive4py.api import TheHiveApi
from thehive4py.models import Version
import thehive4py.exceptions
import json
import traceback
import splunklib.client as client
from common import Settings
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

class TheHive(TheHiveApi):

    """ This class is used to represent a TheHive instance
        Most of parameters are reused from the python library of TheHive
    """

    def __init__(self, url = None, apiKey = None, proxies={}, cert=True, organisation=None, version=Version.THEHIVE_3.value, sid = "", logger = None):
        self.logger = logger
        if version=="TheHive4":
            version = Version.THEHIVE_4.value
        elif version=="TheHive3":
            version = Version.THEHIVE_3.value
        else:
            self.logger.warning("No valid version of TheHive was found for the given type: \""+version+"\"")

        try :
            if sys.version_info[0] < 3:
                TheHiveApi.__init__(self,url=str(url),principal=str(apiKey),password=None,proxies=proxies,cert=cert,organisation=organisation,version=version)
            else:
                super().__init__(url=str(url),principal=str(apiKey),password=None,proxies=proxies,cert=cert,organisation=organisation,version=version)

            # Try to connect to the API by recovering all enabled analyzers
            self.find_cases(query={}, range='all')
            self.logger.debug("TheHive API connection to (URL=\""+url+"\",API key=\""+apiKey+"\") is successful")
        except thehive4py.exceptions.TheHiveException as e:
            if "CERTIFICATE_VERIFY_FAILED" in str(e):
                self.logger.info("[12a-THE_HIVE_CERTIFICATE_FAILED] It seems that the certificate verification failed. Please check that the certificate authority is added to \""+str(certifi.where())+"\". Complete error: "+str(e))
            else:
                self.logger.error("[12b-THE_HIVE_CONNECTION_ERROR] Error: "+str(e))
            sys.exit(12)

        self.__sid = sid
