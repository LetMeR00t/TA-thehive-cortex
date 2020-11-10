# encoding = utf-8
import ta_thehive_cortex_declare
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
    spl = client.connect(app="TA-thehive-cortex",owner="nobody",token=settings["sessionKey"])
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
        for job in jobs:
            result_copy = deepcopy(result)
            logger.debug("Job details: "+str(job))

            event = { "cortex_job_"+k:v for k,v in vars(job).items() if not k.startswith('_') }
            
            # Post processing for Splunk
            ## DATES ##
            if "cortex_job_startDate" in event:
                event["cortex_job_startDate"] = event["cortex_job_startDate"]/1000
            if "cortex_job_endDate" in event:
                event["cortex_job_endDate"] = event["cortex_job_endDate"]/1000
            event["cortex_job_createdAt"] = event["cortex_job_createdAt"]/1000
            if "cortex_job_updatedAt" in event:
                event["cortex_job_updatedAt"] = event["cortex_job_updatedAt"]/1000


            result_copy.update(event)
            outputResults.append(deepcopy(result_copy))

    splunk.Intersplunk.outputResults(outputResults)
