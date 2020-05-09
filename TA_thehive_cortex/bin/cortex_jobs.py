# encoding = utf-8
import sys, os
import ta_thehive_cortex_declare_lib
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

    # Initialiaze settings
    spl = client.connect(app="TA_thehive_cortex",owner="nobody",token=settings["sessionKey"])
    logger = setup_logging("cortex_jobs")
    configuration = Settings(spl, logger)

    MAX_JOBS_DEFAULT = configuration.getCortexJobsMax()
    SORT_JOBS_DEFAULT = configuration.getCortexJobsSort()

    logger.debug("Fields found = "+str(keywords)) 

    # MANDATORY FIELDS : None
    # OPTIONAL FIELDS
    hasFilterData = True if "data" in keywords else False
    hasFilterDatatypes = True if "datatypes" in keywords else False
    hasFilterAnalyzers = True if "analyzers" in keywords else False
    hasMaxJobs = True if "max_jobs" in keywords else False
    hasSortJobs = True if "sort_jobs" in keywords else False

    logger.debug("Data filtering? = "+str(hasFilterData)+", Datatypes filtering? = "+str(hasFilterDatatypes)+", Analyzers filtering? = "+str(hasFilterAnalyzers)+", Max jobs filtering? = "+str(hasMaxJobs)+", Sort jobs filtering? = "+str(hasSortJobs)) 

    # Create the Cortex instance
    cortex = Cortex(configuration.getCortexURL(), configuration.getCortexApiKey(), settings["sid"], logger)

    outputResults = []
    # Prepare and get all jobs queries 
    for result in results:
        ## FILTERS ##
        # Check the results to extract interesting fields
        filterData = result["data"] if hasFilterData else FILTER_DATA_DEFAULT
        filterDatatypes = result["datatypes"] if hasFilterDatatypes else FILTER_DATATYPES_DEFAULT
        filterAnalyzers = result["analyzers"] if hasFilterAnalyzers else FILTER_ANALYZERS_DEFAULT
        maxJobs = result["max_jobs"] if hasMaxJobs else MAX_JOBS_DEFAULT
        sortJobs = result["sort_jobs"] if hasSortJobs else SORT_JOBS_DEFAULT

        logger.debug("filterData: "+filterData+", filterDatatypes: "+filterDatatypes+", filterAnalyzers: "+filterAnalyzers+", max_jobs: "+maxJobs+", sort_jobs: "+sortJobs)

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
