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
    logger.debug("Results found = "+str(results)) 
    logger.debug(splunk.Intersplunk.getKeywordsAndOptions())


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
    
       # Get jobs 
        jobs = cortex.api.jobs.find_all(query ,range='0-'+maxJobs, sort=sortJobs)
        for job in jobs:
             logger.debug("Get job ID \""+job.id+"\"")
             logger.debug("Job details: "+str(job))
             report = cortex.api.jobs.get_report(job.id).report
             summaries = []
             if job.status == "Success":
                 for t in report.get("summary", {}).get("taxonomies", {}):
                     summaries.append("("+t.get("namespace", {})+") "+t.get("predicate", {})+": "+str(t.get("value", {})))
             elif job.status == "Failure":
                 summaries.append(report.get("errorMessage", ""))
    
             logger.debug("Report for \""+job.id+"\": "+str(report))
             data = ""
             if (job.dataType == "file"):
                 data = job.attachment["name"]
             else:
                 data = job.data
             event = {"cortex_job_id": job.id,"cortex_job_data": "["+job.dataType.upper()+"] "+job.data ,"cortex_job_analyzer": job.analyzerName ,"cortex_job_createdAt": job.createdAt/1000 ,"cortex_job_createdBy": job.createdBy+"/"+job.organization,"cortex_job_tlp": job.tlp ,"cortex_job_status": job.status ,"cortex_job_summary": summaries}
         
             if "startDate" in dir(job):
                 event["cortex_job_startDate"] = job.startDate/1000
             if "endDate" in dir(job): 
                 event["cortex_job_endDate"] = job.endDate/1000 

             result.update(event)
             outputResults.append(deepcopy(result))

    splunk.Intersplunk.outputResults(outputResults)
