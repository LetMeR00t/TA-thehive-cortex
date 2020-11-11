import sys
import ta_thehive_cortex_declare
from thehive4py.api import TheHiveApi
import thehive4py.exceptions
import json
import traceback
import splunklib.client as client
from common import Settings


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

    """ This class is used to represent a TheHive instance"""

    def __init__(self, url = None, apiKey = None, sid = "", logger = None):
        self.logger = logger
        try :
            if sys.version_info[0] < 3:
                TheHiveApi.__init__(self,str(url),str(apiKey))
            else:
                super().__init__(str(url), str(apiKey))

            # Try to connect to the API by recovering all enabled analyzers
            self.find_cases(query={}, range='all')
        except thehive4py.exceptions.TheHiveException as e:
            self.logger.error("[The Hive] Error: "+e.msg)
            sys.exit(12)

        self.__sid = sid
