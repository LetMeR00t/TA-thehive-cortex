# encoding = utf-8
import ta_thehive_cortex_declare
import splunk.Intersplunk
from cortex import initialize_cortex_instance
from copy import deepcopy

TLP_DEFAULT = 2 # AMBER
PAP_DEFAULT = 2 # AMBER

if __name__ == '__main__':
    
    # First, parse the arguments
    # get the keywords and options passed to this command
    keywords, options = splunk.Intersplunk.getKeywordsAndOptions()

    # get the previous search results
    results,dummyresults,settings = splunk.Intersplunk.getOrganizedResults()

    # Initialize this script and return a cortex instance object, a configuration object and defaults values
    (cortex, configuration, defaults, logger) = initialize_cortex_instance(keywords, settings ,logger_name="cortex_run_jobs")

    logger.debug("[CRJ-1] Input keywords: "+str(keywords))
    logger.debug("[CRJ-2] Input results: "+str(results))

    outputResults = []
    # Prepare and run all jobs
    for result in results:
        # Check the results to extract interesting fields
        data = configuration.checkAndValidate(result, "data", is_mandatory=True).split(";")
        dataType = configuration.checkAndValidate(result, "dataType", is_mandatory=True)
        analyzers = configuration.checkAndValidate(result, "analyzers", is_mandatory=True)
        tlp = int(configuration.checkAndValidate(result, "tlp", default=TLP_DEFAULT, is_mandatory=False))
        pap = int(configuration.checkAndValidate(result, "pap", default=PAP_DEFAULT, is_mandatory=False))

        for d in data:
            cortex.addJob(d,dataType,tlp,pap,analyzers)
            logger.debug("[CRJ-5] Adding a new job (no details)")
        jobs = cortex.runJobs()
        logger.debug("[CRJ-6] Job(s) are running")

        # Append job id to the result
        for job in jobs:
            result_copy = deepcopy(result)
            logger.debug("[CRJ-10] Job details: "+str(job))

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

            logger.debug("[CRJ-15] Event details: "+str(job))

            result_copy.update(event)
            outputResults.append(deepcopy(result_copy))

    splunk.Intersplunk.outputResults(outputResults)
