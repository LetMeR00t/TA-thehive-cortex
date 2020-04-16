# encoding = utf-8
import ta_cortex_declare
import traceback
import json
from cortex4py.api import Api
import cortex4py.exceptions
import splunk.Intersplunk, splunk.entity

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

colorCode = {
        "WHITE": 0,
        "GREEN": 1,
        "AMBER": 2,
        "RED": 3}
        

# This function is used to write any error in the search.log
def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

class Cortex(object):

    # Cortex Information
    # API object
    api = None

    """This is the main class for communicating with the Cortex API."""
    def __init__(self, data, dataType, tlp=2, pap=2, analyzers="all"):

        ## Init and check data information
        self.data = data
        if (dataType.lower() in dataTypeList):
            self.dataType = dataType.lower()
        else:
            splunkOutput("ERROR", "[WRONG DATA TYPE] This data type ("+dataType+") is not allowed", 21)
        self.tlp = tlp
        self.pap = pap
        # If all analyzers are chosen, we recover them usin the datatype
        if analyzers == "all":
            self.analyzers = Cortex.api.analyzers.get_by_type(dataType)
        else:
            self.analyzers = []
            for analyzer in analyzers.split(";"):
                a = Cortex.api.analyzers.get_by_name(analyzer)
                if a is not None:
                    self.analyzers.append(a)
                else:
                    splunkOutput("ERROR", "[ANALYZER NOT FOUND] This analyzer ("+analyzer+") doesn't exist", 22)

        self.__jobs = []

        if DEBUG:
            splunkOutput("DEBUG",'['+self.data+'] DataType: "'+self.dataType+'"')
            splunkOutput("DEBUG",'['+self.data+'] TLP: "'+str(self.tlp)+'"')
            splunkOutput("DEBUG",'['+self.data+'] PAP: "'+str(self.pap)+'"')
            splunkOutput("DEBUG","["+self.data+"] Analyzers "+str([a.name for a in self.analyzers]))

    # This function returns all jobs
    def getJobs(self):
        return self.__jobs

    # This function returns a JSONified version of the object (used by the Cortex API)
    def jsonify(self):
        json = {}

        json["data"] = self.data
        json["dataType"] = self.dataType
        json["tlp"] = "tlp"
        json["pap"] = "pap"

        return json

    # This function is running all the jobs for the current Cortex object
    def run_jobs(self):
      try:

          args = self.jsonify()
          args["message"] = "sid:"+settings["sid"]
          for a in self.analyzers:
              self.__jobs.append(Cortex.api.analyzers.run_by_id(a.id, args, force=1))
    
      except Exception as e:
          tb = traceback.format_exc()
          splunkOutput("ERROR",str(e)+" - "+str(tb),127)


# This function is used to output results into Splunk
def cortexResult(exitcode, cortex_status, cortex_message, result):
    
    result["cortex_status"] = cortex_status
    result["cortex_message"] = cortex_message

# This function is used to convert any "WHITE/GREEN/AMBER/RED" value in an integer
def convert(value, default):

    if (isinstance(value, int)):
        if value in range(0,4):
            return value
        else:
            splunkOutput("DEBUG", "Integer value "+str(value)+" is out of range (0-3), "+str(default)+" default value will be used")
            return default
    elif (isinstance(value, str)):
        value = value.upper()
        if value in colorCode:
            return colorCode[value]
        else:
            splunkOutput("DEBUG", "String value "+str(value)+" is not in ['WHITE','GREEN','AMBER','RED'], "+str(default)+" default value will be used")
            return default
    else:
            splunkOutput("DEBUG", "Value "+str(value)+" is not an integer or a string, "+str(default)+" default value will be used")
            return default

# This function is used to output errors/debug from the script
def splunkOutput(tag, message, exitcode=None):

    if (tag != "DEBUG" or (tag == "DEBUG" and DEBUG is True)):
        eprint("["+tag+"]: "+message) 
        if exitcode is not None:
            splunk.Intersplunk.outputResults([{"["+tag+"]": message}])
            sys.exit(exitcode)


if __name__ == '__main__':
    
    # First, parse the arguments
    # get the keywords and options passed to this command
    keywords, options = splunk.Intersplunk.getKeywordsAndOptions()

    # get the previous search results
    results,dummyresults,settings = splunk.Intersplunk.getOrganizedResults()

    # get cortex settings
    cortex_settings = splunk.entity.getEntity('TA_cortex_settings','cortex', namespace='TA_cortex', sessionKey=settings['sessionKey'], owner='nobody')
    logging_settings = splunk.entity.getEntity('TA_cortex_settings','logging', namespace='TA_cortex', sessionKey=settings['sessionKey'], owner='nobody')
    cortex_storage_passwords = splunk.entity.getEntity('storage','passwords', namespace='TA_cortex', sessionKey=settings['sessionKey'], owner='nobody')

    # Get the API key
    if "cortex_api_key" in cortex_storage_passwords['clear_password']:
        credential_json = json.loads(cortex_storage_passwords.get('clear_password'))
        cortex_settings['cortex_api_key'] = str(credential_json["cortex_api_key"])

    # Initialize GLOBAL variables
    DEBUG = True if "debug" in logging_settings and int(logging_settings["debug"]) == 1 else False
    TLP_DEFAULT = 2 # AMBER
    PAP_DEFAULT = 2 # AMBER
    splunkOutput("DEBUG", "Fields found = "+str(keywords)) 

    # Checks before configure
    cortex_information_required = ["cortex_protocol","cortex_host","cortex_port","cortex_api_key"]
    for i in cortex_information_required:
        if not i in cortex_settings:
            splunkOutput("ERROR","[FIELD MISSING] No \""+i+"\" setting set in \"Configuration\", please configure your Cortex instance under \"Configuration\"",10)

    # Initiliaze class variables for Cortex
    url = cortex_settings["cortex_protocol"]+"://"+cortex_settings["cortex_host"]+":"+cortex_settings["cortex_port"]
    apiKey = cortex_settings["cortex_api_key"]

    try :
        Cortex.api = Api(url, apiKey)
        # Try to connect to the API by recovering all enabled analyzers
        Cortex.api.analyzers.find_all({}, range='all')
    except cortex4py.exceptions.ServiceUnavailableError as e:
        splunkOutput("ERROR","[SERVICE UNAVAILABLE] Cortex service is unavailable, is configuration correct ?",11)
    except cortex4py.exceptions.AuthenticationError as e:
        splunkOutput("ERROR","[AUTHENTICATION ERROR] Credentials are invalid",12)

    # MANDATORY FIELDS
    for key in ["data", "dataType"]:
        if (key not in keywords): 
            splunkOutput("ERROR","[FIELD MISSING] No \""+key+"\" field given in arguments, it\'s mandatory\r\nExpecting: | cortexrun data dataType (tlp, pap, analyzers)",15)
    # OPTIONAL FIELDS
    hasTLPField = True if "tlp" in keywords else False
    hasPAPField = True if "pap" in keywords else False
    hasAnalyzersField = True if "analyzers" in keywords else False

    splunkOutput("DEBUG", "TLP field? = "+str(hasTLPField)+", PAP field? = "+str(hasPAPField)+", Analyzers field? = "+str(hasAnalyzersField)) 

    # Prepare and run all jobs
    for result in results:
        # Check the results to extract interesting fields
        data = result["data"]
        dataType = result["dataType"]
        tlp = convert(result["tlp"], TLP_DEFAULT) if hasTLPField else TLP_DEFAULT
        pap = convert(result["pap"], PAP_DEFAULT) if hasPAPField else PAP_DEFAULT
        analyzers = result["analyzers"] if (hasAnalyzersField is True and "analyzers" in result and result["analyzers"] != "") else "all" # Any analyzer by default
    
        cortex = Cortex(data,dataType,tlp,pap,analyzers)
        cortex.run_jobs()

        # Append job id to the result
        cortexResults = []
        for job in cortex.getJobs():
            cortexResults.append("id="+job.id+"::analyzer="+job.analyzerName+"::status="+job.status)
        result["cortex"] = cortexResults
    

    splunk.Intersplunk.outputResults(results)
