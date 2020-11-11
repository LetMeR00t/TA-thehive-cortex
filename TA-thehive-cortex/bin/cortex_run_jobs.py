# encoding = utf-8
import ta_thehive_cortex_declare
import sys, os
import splunk.Intersplunk
from common import Settings
from cortex import Cortex, CortexJob
import splunklib.client as client
from ta_logging import setup_logging
from copy import deepcopy

TLP_DEFAULT = 2 # AMBER
PAP_DEFAULT = 2 # AMBER

def check_and_validate(d, name, default="", is_mandatory=False):
    if name in d:
        logger.info("Found parameter \""+name+"\"="+d[name])
        return d[name]
    else:
        if is_mandatory:
            logger.error("Missing parameter (no \""+name+"\" field found)")
            sys.exit(1)
        else:
            logger.info("Parameter \""+name+"\" not found, using default value=\""+default+"\"")
            return default 

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

    # Create the Cortex instance
    cortex = Cortex(configuration.getCortexURL(), configuration.getCortexApiKey(), settings["sid"], logger)

    outputResults = []
    # Prepare and run all jobs
    for result in results:
        # Check the results to extract interesting fields
        data = check_and_validate(result, "data", is_mandatory=True)
        dataType = check_and_validate(result, "dataType", is_mandatory=True)
        analyzers = check_and_validate(result, "analyzers", is_mandatory=True)
        tlp = int(check_and_validate(result, "tlp", default=TLP_DEFAULT, is_mandatory=False))
        pap = int(check_and_validate(result, "pap", default=PAP_DEFAULT, is_mandatory=False))

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
