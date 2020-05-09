import sys
import ta_thehive_cortex_declare_lib
from thehive4py.api import Api
import thehive4py.exceptions
import json
import traceback
import splunklib.client as client
from common import Settings

# All available data types
dataTypeList = [
        "domain",
        "file",
        "filename",
        "fqdn",
        "hash",
        "ip",
        "mail",
        "mail_subject",
        "other",
        "regexp",
        "registry",
        "uri_path",
        "url",
        "user-agent"]

# Mapping for TLP/PAP codes
colorCode = {
        "WHITE": 0,
        "GREEN": 1,
        "AMBER": 2,
        "RED": 3}

class TheHive(Api):

    """ This class is used to represent a TheHive instance"""

    def __init__(self, url = None, apiKey = None, sid = "", logger = None):
        self.logger = logger
        try :
            super().__init__(str(url), str(apiKey))
            # Try to connect to the API by recovering all enabled analyzers
            self.cases.find_all({}, range='all')
        except thehive4py.exceptions.NotFoundError as e:
            self.logger.error("[10-RESOURCE NOT FOUND] TheHive service is unavailable, is configuration correct ?")
            sys.exit(10)
        except thehive4py.exceptions.ServiceUnavailableError as e:
            self.logger.error("[11-SERVICE UNAVAILABLE] TheHive service is unavailable, is configuration correct ?")
            sys.exit(11)
        except thehive4py.exceptions.AuthenticationError as e:
            self.logger.error("[12-AUTHENTICATION ERROR] Credentials are invalid")
            sys.exit(12)

        self.__sid = sid
