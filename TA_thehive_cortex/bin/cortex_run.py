# encoding = utf-8
import ta_thehive_cortex_declare_lib
import os
import splunk.Intersplunk
import logging, logging.handlers
from cortex import Cortex, CortexJob, Settings
import splunklib.client as client


def setup_logging():
    logger = logging.getLogger('command_cortex_run.log')    
    SPLUNK_HOME = os.environ['SPLUNK_HOME']
    
    LOGGING_DEFAULT_CONFIG_FILE = os.path.join(SPLUNK_HOME, 'etc', 'log.cfg')
    LOGGING_LOCAL_CONFIG_FILE = os.path.join(SPLUNK_HOME, 'etc', 'log-local.cfg')
    LOGGING_STANZA_NAME = 'python'
    LOGGING_FILE_NAME = "command_cortex_run.log"
    BASE_LOG_PATH = os.path.join('var', 'log', 'splunk')
    LOGGING_FORMAT = "%(asctime)s %(levelname)-s\t%(module)s:%(lineno)d - %(message)s"
    splunk_log_handler = logging.handlers.RotatingFileHandler(os.path.join(SPLUNK_HOME, BASE_LOG_PATH, LOGGING_FILE_NAME), mode='a') 
    splunk_log_handler.setFormatter(logging.Formatter(LOGGING_FORMAT))
    logger.addHandler(splunk_log_handler)
    splunk.setupSplunkLogger(logger, LOGGING_DEFAULT_CONFIG_FILE, LOGGING_LOCAL_CONFIG_FILE, LOGGING_STANZA_NAME)
    return logger
logger = setup_logging()
# Default logging
logger.setLevel(logging.INFO)


TLP_DEFAULT = 2 # AMBER
PAP_DEFAULT = 2 # AMBER

if __name__ == '__main__':
    
    # First, parse the arguments
    # get the keywords and options passed to this command
    keywords, options = splunk.Intersplunk.getKeywordsAndOptions()

    # get the previous search results
    results,dummyresults,settings = splunk.Intersplunk.getOrganizedResults()

    # Initialiaze settings
    spl = client.connect(app="TA_thehive_cortex",owner="nobody",token=settings["sessionKey"])
    configuration = Settings(spl, logger)
    if int(configuration.getSetting("logging","debug")) == 1:
        logger.setLevel(logging.DEBUG)
        logger.debug("LEVEL changed to DEBUG according to the configuration")
    logger.debug("Fields found = "+str(keywords)) 

    # Create the Cortex instance
    cortex = Cortex(configuration.getURL(), configuration.getApiKey(), settings["sid"], logger)

    # MANDATORY FIELDS
    for key in ["data", "dataType"]:
        if (key not in keywords): 
            splunkOutput("ERROR","[FIELD MISSING] No \""+key+"\" field given in arguments, it\'s mandatory\r\nExpecting: | cortexrun data dataType (tlp, pap, analyzers)",15)
    # OPTIONAL FIELDS
    hasTLPField = True if "tlp" in keywords else False
    hasPAPField = True if "pap" in keywords else False
    hasAnalyzersField = True if "analyzers" in keywords else False

    logger.debug("TLP field? = "+str(hasTLPField)+", PAP field? = "+str(hasPAPField)+", Analyzers field? = "+str(hasAnalyzersField)) 

    # Prepare and run all jobs
    for result in results:
        # Check the results to extract interesting fields
        data = result["data"]
        dataType = result["dataType"]
        tlp = CortexJob.convert(result["tlp"], TLP_DEFAULT) if hasTLPField else TLP_DEFAULT
        pap = CortexJob.convert(result["pap"], PAP_DEFAULT) if hasPAPField else PAP_DEFAULT
        analyzers = result["analyzers"] if (hasAnalyzersField is True and "analyzers" in result and result["analyzers"] != "") else "all" # Any analyzer by default
    
        cortex.addJob(data,dataType,tlp,pap,analyzers)
        jobs = cortex.runJobs()

        # Append job id to the result
        cortexResults = []
        for job in jobs:
            cortexResults.append("id="+job.id+"::analyzer="+job.analyzerName+"::status="+job.status)
        result["cortex"] = cortexResults
    

    splunk.Intersplunk.outputResults(results)
