# encoding = utf-8
import sys
import ta_thehive_cortex_declare
from cortex4py.api import Api
import cortex4py.exceptions
from ta_logging import setup_logging
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
        "user-agent"
]

# Mapping for TLP/PAP codes
colorCode = {
        "WHITE": 0,
        "GREEN": 1,
        "AMBER": 2,
        "RED": 3
}

def initialize_cortex_instance(keywords, settings, logger_name="script"):
    """ This function is used to initialize a Cortex instance """

    logger = setup_logging(logger_name)

    # Check the existence of the instance_id
    if len(keywords) == 1:
        instance_id = keywords[0]
    else:
        logger.error("[C1-ERROR] No instance ID was given to the script")
        exit(4)

    # Initialiaze settings
    spl = client.connect(app="TA-thehive-cortex",owner="nobody",token=settings["sessionKey"])
    logger.debug("[C5] Connection to Splunk done")
    configuration = Settings(spl, settings, logger)
    logger.debug("[C6] Settings recovered")

    defaults = {
        "MAX_JOBS_DEFAULT": configuration.getCortexJobsMax(),
        "SORT_JOBS_DEFAULT": configuration.getCortexJobsSort()
    }

    # Create the Cortex instance
    (cortex_username, cortex_api_key) = configuration.getInstanceUsernameApiKey(instance_id)
    cortex_url = configuration.getInstanceURL(instance_id)
    cortex = Cortex(url=cortex_url, apiKey=cortex_api_key, sid=settings["sid"], logger=logger)
    logger.debug("[C10] Cortex instance created")

    return (cortex, configuration, defaults, logger) 


class Cortex(Api):
    """ This class is used to represent a Cortex instance"""

    def __init__(self, url = None, apiKey = None, sid = "", logger = None):
        self.logger = logger
        try :
            if apiKey is None:
                self.logger.error("[C15-ERROR] API Key is null, this is the only way to connect to a Cortex instance")
                exit(15)

            if sys.version_info[0] < 3:
                super(Cortex,self).__init__(str(url),str(apiKey))
            else:
                super().__init__(str(url),str(apiKey))
            logger.debug("[C20] Cortex object instanciated")

            # Try to connect to the API by recovering all enabled analyzers
            self.analyzers.find_all({}, range='all')

            self.logger.debug("[C21] Cortex API connection to (URL=\""+url+"\",API key=\""+apiKey+"\") is successful")
        except cortex4py.exceptions.NotFoundError as e:
            self.logger.error("[C25-ERROR] RESOURCE NOT FOUND - Cortex service is unavailable, is configuration correct ?")
            sys.exit(25)
        except cortex4py.exceptions.ServiceUnavailableError as e:
            self.logger.error("[C26-ERROR] SERVICE UNAVAILABLE - Cortex service is unavailable, is configuration correct ?")
            sys.exit(26)
        except cortex4py.exceptions.AuthenticationError as e:
            self.logger.error("[C27-ERROR] AUTHENTICATION ERROR - Credentials are invalid")
            sys.exit(27)

        self.__sid = sid
        self.__jobs = []

    def getJobs(self):
        """ This function returns all jobs to perform """
        self.logger.debug("[C30] Getting jobs: "+str(self.__jobs))
        return self.__jobs
    
    def addJob(self, data, dataType, tlp=2, pap=2, analyzers="all"):
        """ This function add a new job to do """
        job = None
        ## Init and check data information
        if (dataType.lower() in dataTypeList):
            dataType = dataType.lower()
        else:
            self.logger.error("[C35-ERROR] WRONG DATA TYPE - This data type ("+dataType+") is not allowed")
            sys.exit(35)

        analyzersObj = []
        # If all analyzers are chosen, we recover them usin the datatype
        if analyzers == "all":
            analyzersObj = self.analyzers.get_by_type(dataType)
        else:
            for analyzer in analyzers.replace(" ","").split(";"):
                a = self.analyzers.get_by_name(analyzer)
                if a is not None:
                    analyzersObj.append(a)
                else:
                    self.logger.error("[C40-ERROR] ANALYZER NOT FOUND - This analyzer ("+analyzer+") doesn't exist")
                    sys.exit(40)
        self.logger.debug("[C41] Analyzers recovered: "+str(analyzersObj))

        job = CortexJob(data, dataType, tlp, pap, analyzersObj, self.logger)
        self.logger.debug("[C42] Job instance created")

        self.__jobs.append(job)

    def runJobs(self):
        """ Execute all jobs and return the result """
        results = []
        for job in self.__jobs:
            try:
                job_json = job.jsonify()
                job_json["message"] = "sid:"+self.__sid
                for a in job.analyzers:
                    self.logger.debug("[C45] JOB sent: "+str(job_json))
                    results.append(self.analyzers.run_by_id(a.id, job_json, force=1))
            except Exception as e:
                tb = traceback.format_exc()
                self.logger.error("[C46-GENERIC-ERROR] "+str(e)+" - "+str(tb))
                sys.exit(46)

        self.__jobs = []
        return results

class CortexJob(object):

    def __init__(self, data, dataType, tlp=2, pap=2, analyzers="all", logger = None):
        self.logger = logger
        ## Init and check data information
        self.data = data
        if (dataType.lower() in dataTypeList):
            self.dataType = dataType.lower()
        else:
            self.logger.error("[CJ-1] WRONG DATA TYPE - This data type ("+dataType+") is not allowed")
            sys.exit(1)

        self.tlp = tlp
        self.pap = pap

        self.analyzers = analyzers

        self.logger.debug('[CJ-5] ['+self.data+'] DataType: "'+self.dataType+'"')
        self.logger.debug('[CJ-6] ['+self.data+'] TLP: "'+str(self.tlp)+'"')
        self.logger.debug('[CJ-7] ['+self.data+'] PAP: "'+str(self.pap)+'"')
        self.logger.debug("[CJ-8] ["+self.data+"] Analyzers "+str([a.name for a in self.analyzers]))

    def jsonify(self):
        """ This function returns a JSONified version of the object (used by the Cortex API) """

        json = {}

        json["data"] = self.data
        json["dataType"] = self.dataType
        json["tlp"] = self.tlp
        json["pap"] = self.pap

        return json
