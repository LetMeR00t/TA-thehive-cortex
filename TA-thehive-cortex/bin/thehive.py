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

# class TheHiveCase(object):
# 
#     def __init__(self, title, severity=2, tags=[], pap=2, date="", tlp=2, description="", tasks=[], logger = None):
#         self.logger = logger
#         ## Init and check data information
#         self.title = title
# 
#         if (severity.upper() in severityCode):
#             self.severity = severityCode[dataType.upper()]
#         elif type(severity)==int:
#             self.severity = severity
#         else:
#             self.logger.error("[21-WRONG SEVERITY] This severity ("+severity+") is not allowed")
#             sys.exit(21)
# 
#         self.tags = tags
#         self.pap = pap
#         self.date = date
#         self.tlp = tlp
#         self.description = description
#         self.tasks = tasks
# 
#         self.logger.debug('['+self.title+'] Severity: "'+self.severity+'"')
#         self.logger.debug('['+self.title+'] Tags: "'+str(self.tags)+'"')
#         self.logger.debug('['+self.title+'] PAP: "'+str(self.pap)+'"')
#         self.logger.debug('['+self.title+'] Date: "'+str(self.date)+'"')
#         self.logger.debug('['+self.title+'] TLP: "'+str(self.tlp)+'"')
#         self.logger.debug('['+self.title+'] Description: "'+self.description+'"')
#         self.logger.debug('['+self.title+'] Tasks: "'+str(self.tasks)+'"')
#         self.logger.debug("["+self.title+"] Analyzers "+str([a.name for a in self.analyzers]))
# 
#     @classmethod
#     def convert(cls, value, default):
#         """ This function is used to convert any "WHITE/GREEN/AMBER/RED" value in an integer """
#     
#         if (isinstance(value, int)):
#             if value in range(0,4):
#                 return value
#             else:
#                 self.logger.debug("Integer value "+str(value)+" is out of range (0-3), "+str(default)+" default value will be used")
#                 return default
#         elif (isinstance(value, str)):
#             value = value.upper()
#             if value in colorCode:
#                 return colorCode[value]
#             else:
#                 self.logger.debug("String value "+str(value)+" is not in ['WHITE','GREEN','AMBER','RED'], "+str(default)+" default value will be used")
#                 return default
#         else:
#                 self.logger.debug("Value "+str(value)+" is not an integer or a string, "+str(default)+" default value will be used")
#                 return default
# 
#     def jsonify(self):
#         """ This function returns a JSONified version of the object (used by the Cortex API) """
# 
#         json = {}
# 
#         json["title"] = self.title
#         json["severity"] = self.severity
#         json["tags"] = self.tags
#         json["pap"] = self.pap
#         json["date"] = self.date
#         json["tlp"] = self.tlp
#         json["description"] = self.description
#         json["tasks"] = self.tasks
# 
# 
#         return json
