# encoding = utf-8
import sys, os
import ta_thehive_cortex_declare
from common import Settings
from cortex import Cortex, CortexJob
import splunklib.client as client
from ta_logging import setup_logging
from copy import deepcopy
import splunk.Intersplunk

FILTER_DATA_DEFAULT = ""
FILTER_DATATYPES_DEFAULT = "*"
FILTER_ANALYZERS_DEFAULT = "*"
MAX_JOBS = None
SORT_JOBS = None

if __name__ == '__main__':
    
    # First, parse the arguments
    # get the keywords and options passed to this command
    keywords, options = splunk.Intersplunk.getKeywordsAndOptions()

    # get the previous search results
    results,dummyresults,settings = splunk.Intersplunk.getOrganizedResults()

    # Check the existence of the instance_id
    if len(keywords) == 1:
        instance_id = keywords[0]
    else:
        logger.error("[4-MISSING_INSTANCE_ID] No instance ID was given to the script")
        exit(4)

    # Initialiaze settings
    spl = client.connect(app="TA-thehive-cortex",owner="nobody",token=settings["sessionKey"])
    logger = setup_logging("cortex_jobs")
    configuration = Settings(spl, settings, logger)

    MAX_JOBS_DEFAULT = configuration.getCortexJobsMax()
    SORT_JOBS_DEFAULT = configuration.getCortexJobsSort()

    # Create the Cortex instance
    (cortex_username, cortex_api_key) = configuration.getInstanceUsernameApiKey(instance_id)
    cortex = Cortex(configuration.getInstanceURL(instance_id), cortex_api_key, settings["sid"], logger)


    outputResults = []
    # Prepare and get all jobs queries 
    for result in results:
        ## FILTERS ##
        # Check the results to extract interesting fields
        filterData = configuration.check_and_validate(result, "data", default=FILTER_DATA_DEFAULT, is_mandatory=False)
        filterDatatypes = configuration.check_and_validate(result, "datatypes", default=FILTER_DATATYPES_DEFAULT, is_mandatory=False)
        filterAnalyzers = configuration.check_and_validate(result, "analyzers", default=FILTER_ANALYZERS_DEFAULT, is_mandatory=False)
        maxJobs = configuration.check_and_validate(result, "max_jobs", default=MAX_JOBS_DEFAULT, is_mandatory=False)
        sortJobs = configuration.check_and_validate(result, "sort_jobs", default=SORT_JOBS_DEFAULT, is_mandatory=False)

        # create the query from filters
        query = {}
        if filterData != "":
            new_query = {"_field":"data","_value":filterData}
            query = new_query
        if filterDatatypes != "*":
            new_query = {"_in":{"_field":"dataType","_values":filterDatatypes.replace(" ","").split(";")}}
            if query == {}:
                query = new_query
            else:
                query = {"_and":[query,new_query]}
        if filterAnalyzers != "*":
            new_query = {"_in":{"_field":"workerDefinitionId","_values":filterAnalyzers.replace(" ","").split(";")}}
            if query == {}:
                query = new_query
            elif "_and" in query:
                query["_and"].append(new_query)
            else:
                query = {"_and":[query,new_query]}
    
        logger.info("Query is: "+str(query))
    
        ## JOBS ##
        jobs = cortex.jobs.find_all(query ,range='0-'+maxJobs, sort=sortJobs)
        for job in jobs:
             result_copy = deepcopy(result)
             logger.debug("Job details: "+str(job))

             report = cortex.jobs.get_report(job.id)

             logger.debug("Report details: \""+job.id+"\": "+str(report))
    
             job_report = { "cortex_job_"+k:v for k,v in vars(report).items() if not k.startswith('_') }

             event = { "cortex_job_"+k:v for k,v in vars(job).items() if not k.startswith('_') }
             
             # Post processing for Splunk
             ## REPORT ##
             keys = []
             for k in job_report["cortex_job_report"]:
                 keys.append(k+"::"+str(job_report["cortex_job_report"][k]))
             event["cortex_job_report"] = keys
             
             ## DATES ##
             if "cortex_job_startDate" in event:
                 event["cortex_job_startDate"] = event["cortex_job_startDate"]/1000
             if "cortex_job_endDate" in event:
                 event["cortex_job_endDate"] = event["cortex_job_endDate"]/1000
             event["cortex_job_createdAt"] = event["cortex_job_createdAt"]/1000
             event["cortex_job_updatedAt"] = event["cortex_job_updatedAt"]/1000


             result_copy.update(event)
             outputResults.append(deepcopy(result_copy))

    splunk.Intersplunk.outputResults(outputResults)
