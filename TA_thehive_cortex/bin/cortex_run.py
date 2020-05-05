# encoding = utf-8
import ta_thehive_cortex_declare_lib
import os
import splunk.Intersplunk
from common import Settings
from cortex import Cortex, CortexJob
import splunklib.client as client
from ta_logging import setup_logging
from copy import deepcopy

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
    logger = setup_logging("cortex_run")
    configuration = Settings(spl, logger)
    logger.debug("Fields found = "+str(keywords)) 

    # Create the Cortex instance
    cortex = Cortex(configuration.getCortexURL(), configuration.getCortexApiKey(), settings["sid"], logger)

    # MANDATORY FIELDS
    for key in ["data", "dataType"]:
        if (key not in keywords): 
            splunkOutput("ERROR","[FIELD MISSING] No \""+key+"\" field given in arguments, it\'s mandatory\r\nExpecting: | cortexrun data dataType (tlp, pap, analyzers)",15)
    # OPTIONAL FIELDS
    hasTLPField = True if "tlp" in keywords else False
    hasPAPField = True if "pap" in keywords else False
    hasAnalyzersField = True if "analyzers" in keywords else False

    logger.debug("TLP field? = "+str(hasTLPField)+", PAP field? = "+str(hasPAPField)+", Analyzers field? = "+str(hasAnalyzersField)) 

    outputResults = []
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
            event = {}
            event["cortex_job_id"] = job.id
            event["cortex_job_analyzer"] = job.analyzerName
            event["cortex_job_status"] = job.status
            result.update(event)
            outputResults.append(deepcopy(result))
    

    splunk.Intersplunk.outputResults(outputResults)
