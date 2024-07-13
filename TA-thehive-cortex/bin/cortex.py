# encoding = utf-8
import sys
import ta_thehive_cortex_declare
from cortex4py.api import Api
import cortex4py.exceptions
from ta_logging import setup_logging
import traceback
import splunklib.client as client
from common import LoggerFile, Settings

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

def initialize_cortex_instance(keywords, settings, acronym, logger_name="script"):
    """ This function is used to initialize a Cortex instance """
    logger_file = LoggerFile(setup_logging(logger_name), acronym)

    # Check the existence of the instance_id
    if len(keywords) == 1:
        instance_id = keywords[0]
    else:
        logger_file.error("[C1-ERROR] No instance ID was given to the script")
        exit(4)

    return create_cortex_instance(instance_id, settings, logger_file)

def create_cortex_instance(instance_id, settings, logger, acronym):
    logger_file = LoggerFile(logger, acronym)
    """ This function is used to create an instance of TheHive """
    # Initialize settings
    token = settings["sessionKey"] if "sessionKey" in settings else settings["session_key"]
    spl = client.connect(app="TA-thehive-cortex",owner="nobody",token=token)
    logger_file.debug(id="C5",message="Connection to Splunk done")
    configuration = Settings(spl, settings, logger_file=logger_file)
    logger_file.debug(id="C6",message="Settings recovered")

    defaults = {
        "MAX_JOBS_DEFAULT": configuration.getCortexJobsMax(),
        "SORT_JOBS_DEFAULT": configuration.getCortexJobsSort()
    }

    # Create the Cortex instance
    (cortex_username, cortex_secret) = configuration.getInstanceUsernameApiKey(instance_id)
    cortex_url = configuration.getInstanceURL(instance_id)
    cortex_authentication_type = configuration.getInstanceSetting(instance_id,"authentication_type")
    cortex_proxies = configuration.getInstanceSetting(instance_id,"proxies")
    cortex_cert = configuration.getInstanceSetting(instance_id,"client_cert")
    cortex_cert = None if cortex_cert == "-" else cortex_cert
    cortex_organisation = configuration.getInstanceSetting(instance_id,"organisation")
    cortex_version = configuration.getInstanceSetting(instance_id,"type") 
    cortex = None

    if (cortex_authentication_type == "password"):
        logger_file.error(id="C7",message="Cortex instance will be initialized with a password (not an API key) - This is not supported for Cortex")
        sys.exit(7)
    elif (cortex_authentication_type == "api_key"):
        logger_file.debug(id="C8",message="Cortex instance will be initialized with an API Key (not a password)")
        cortex = Cortex(url=cortex_url, apiKey=cortex_secret, sid=settings["sid"], proxies=cortex_proxies, verify=True, cert=cortex_cert, logger=logger_file)
    else:
        logger_file.error(id="C9",message="WRONG_AUTHENTICATION_TYPE - Authentication type is not one of the expected values (password or api_key), given value: "+cortex_authentication_type)
        sys.exit(20)

    return (cortex, configuration, defaults, logger_file) 


class Cortex(Api):
    """ This class is used to represent a Cortex instance"""

    def __init__(self, url = None, apiKey = None, sid = "", proxies = {}, cert = None , verify = True, logger_file = None):
        self.logger_file = logger_file
        try :
            if apiKey is None:
                self.logger_file.error(id="C15",message="API Key is null, this is the only way to connect to a Cortex instance")
                sys.exit(15)

            self.logger_file.debug(id="C19",message=f"Cortex object will be instanciated with url '{url}'")
            super().__init__(str(url),str(apiKey),proxies=proxies,verify_cert=verify,cert=cert)
            self.logger_file.debug(id="C20",message="Cortex object instanciated")

            # Try to connect to the API by recovering all enabled analyzers
            self.analyzers.find_all({}, range='all')

            self.logger_file.debug(id="C21",message="Cortex API connection to (URL=\""+url+"\") is successful")
        except cortex4py.exceptions.NotFoundError as e:
            self.logger_file.error(id="C25",message="RESOURCE NOT FOUND - Cortex service is unavailable, is the configuration correct ?")
            sys.exit(25)
        except cortex4py.exceptions.ServiceUnavailableError as e:
            self.logger_file.error(id="C26",message="SERVICE UNAVAILABLE - Cortex service is unavailable, is the configuration correct ?")
            sys.exit(26)
        except cortex4py.exceptions.AuthenticationError as e:
            self.logger_file.error(id="C27",message="AUTHENTICATION ERROR - Credentials are invalid")
            sys.exit(27)

        self.__sid = sid
        self.__jobs = []

    def getJobs(self):
        """ This function returns all jobs to perform """
        self.logger_file.debug(id="C30",message="Getting jobs: "+str(self.__jobs))
        return self.__jobs
    
    def addJob(self, data, dataType, tlp=2, pap=2, analyzers="all"):
        """ This function add a new job to do """
        job = None
        ## Init and check data information
        if (dataType.lower() in dataTypeList):
            dataType = dataType.lower()
        else:
            self.logger_file.error(id="C35",message="WRONG DATA TYPE - This data type ("+dataType+") is not allowed")
            sys.exit(35)

        analyzersObj = []
        # If all analyzers are chosen, we recover them using the datatype
        if analyzers == "all":
            analyzersObj = self.analyzers.get_by_type(dataType)
        else:
            for analyzer in analyzers.replace(" ","").split(";"):
                a = self.analyzers.get_by_name(analyzer)
                if a is not None:
                    analyzersObj.append(a)
                else:
                    self.logger_file.error(id="C40",message="ANALYZER NOT FOUND - This analyzer ("+analyzer+") doesn't exist")
                    sys.exit(40)
        self.logger_file.debug(id="C41",message="Analyzers recovered: "+str(analyzersObj))

        job = CortexJob(data, dataType, tlp, pap, analyzersObj, self.logger)
        self.logger_file.debug(id="C42",message="Job instance created")

        self.__jobs.append(job)

    def runJobs(self):
        """ Execute all jobs and return the result """
        results = []
        for job in self.__jobs:
            try:
                job_json = job.jsonify()
                job_json["message"] = "sid:"+self.__sid
                for a in job.analyzers:
                    self.logger_file.debug(id="C45",message="JOB sent: "+str(job_json))
                    results.append(self.analyzers.run_by_id(a.id, job_json, force=1))
            except Exception as e:
                tb = traceback.format_exc()
                self.logger_file.error(id="C46",message=str(e)+" - "+str(tb))
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
            self.logger_file.error(id="CJ1",message="WRONG DATA TYPE - This data type ("+dataType+") is not allowed")
            sys.exit(1)

        self.tlp = tlp
        self.pap = pap

        self.analyzers = analyzers

        self.logger_file.debug(id="CJ5",message='['+self.data+'] DataType: '+self.dataType+'"')
        self.logger_file.debug(id="CJ6",message='['+self.data+'] TLP: '+str(self.tlp)+'"')
        self.logger_file.debug(id="CJ7",message='['+self.data+'] PAP: '+str(self.pap)+'"')
        self.logger_file.debug(id="CJ8",message='['+self.data+'] Analyzers '+str([a.name for a in self.analyzers]))

    def jsonify(self):
        """ This function returns a JSONified version of the object (used by the Cortex API) """

        json = {}

        json["data"] = self.data
        json["dataType"] = self.dataType
        json["tlp"] = self.tlp
        json["pap"] = self.pap

        return json
