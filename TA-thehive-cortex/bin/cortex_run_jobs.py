# encoding = utf-8
import ta_thehive_cortex_declare
import splunk.Intersplunk
from cortex import initialize_cortex_instance
from copy import deepcopy
import globals

TLP_DEFAULT = 2 # AMBER
PAP_DEFAULT = 2 # AMBER

if __name__ == '__main__':
    
    globals.initialize_globals()

    # First, parse the arguments
    # get the keywords and options passed to this command
    keywords, options = splunk.Intersplunk.getKeywordsAndOptions()

    # get the previous search results
    results,dummyresults,settings = splunk.Intersplunk.getOrganizedResults()

    # Initialize this script and return a cortex instance object, a configuration object and defaults values
    (cortex, configuration, defaults, logger_file) = initialize_cortex_instance(keywords, settings, acronym="CRJ", logger_name="cortex_run_jobs")

    logger_file.debug(id="1",message="Input keywords: "+str(keywords))
    logger_file.debug(id="2",message="Input results: "+str(results))

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
            logger_file.debug(id="5",message="Adding a new job (no details)")
        jobs = cortex.runJobs()
        logger_file.debug(id="6",message="Job(s) are running")

        # Append job id to the result
        for job in jobs:
            result_copy = deepcopy(result)
            logger_file.debug(id="10",message="Job details: "+str(job))

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

            logger_file.debug(id="15",message="Event details: "+str(job))

            result_copy.update(event)
            outputResults.append(deepcopy(result_copy))

    splunk.Intersplunk.outputResults(outputResults)
