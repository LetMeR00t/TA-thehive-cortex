# encoding = utf-8
import ta_thehive_cortex_declare
from cortex import initialize_cortex_instance
from cortex4py.query import And, Eq, In
from copy import deepcopy
import splunk.Intersplunk
import globals

# Global parameters
FILTER_DATA_DEFAULT = ""
FILTER_DATATYPES_DEFAULT = "*"
FILTER_ANALYZERS_DEFAULT = "*"
MAX_JOBS = None
SORT_JOBS = None

if __name__ == '__main__':
    
    globals.initialize_globals()

    # First, parse the arguments
    # get the keywords and options passed to this command
    keywords, options = splunk.Intersplunk.getKeywordsAndOptions()

    # get the previous search results
    results,dummyresults,settings = splunk.Intersplunk.getOrganizedResults()

    # Initialize this script and return a cortex instance object, a configuration object and defaults values
    (cortex, configuration, defaults, logger_file) = initialize_cortex_instance(keywords, settings, acronym="CSJ", logger_name="cortex_search_jobs")

    logger_file.debug(id="1",message="Input keywords: "+str(keywords))
    logger_file.debug(id="2",message="Input results: "+str(results))

    outputResults = []
    # Prepare and get all jobs queries 
    for result in results:
        ## FILTERS ##
        # Check the results to extract interesting fields
        filterData = configuration.checkAndValidate(result, "data", default=FILTER_DATA_DEFAULT, is_mandatory=False)
        filterDatatypes = configuration.checkAndValidate(result, "datatypes", default=FILTER_DATATYPES_DEFAULT, is_mandatory=False)
        filterAnalyzers = configuration.checkAndValidate(result, "analyzers", default=FILTER_ANALYZERS_DEFAULT, is_mandatory=False)
        maxJobs = configuration.checkAndValidate(result, "max_jobs", default=defaults["MAX_JOBS_DEFAULT"], is_mandatory=False)
        sortJobs = configuration.checkAndValidate(result, "sort_jobs", default=defaults["SORT_JOBS_DEFAULT"], is_mandatory=False)

        # create the query from filters
        query = {}
        elements = []
        if filterData != FILTER_DATA_DEFAULT:
            element = Eq("data",filterData)
            elements.append(element)
        if filterDatatypes != FILTER_DATATYPES_DEFAULT:
            element = In("dataType",filterDatatypes.replace(" ","").split(";"))
            elements.append(element)
        if filterAnalyzers != FILTER_ANALYZERS_DEFAULT:
            element = In("workerDefinitionId",filterAnalyzers.replace(" ","").split(";"))
            elements.append(element)

        if len(elements)>1:
            query = And(*elements)
        elif len(elements)==1:
            query = elements[0]
        logger_file.info(id="10",message="Query is: "+str(query))
    
        ## JOBS ##
        jobs = cortex.jobs.find_all(query ,range='0-'+maxJobs, sort=sortJobs)

        for job in jobs:
             result_copy = deepcopy(result)
             logger_file.debug(id="15",message="Job details: "+str(job))

             report = cortex.jobs.get_report(job.id)

             logger_file.debug(id="16",message="Report details: \""+str(job.id)+"\": "+str(report))
    
             job_report = { "cortex_job_"+k:v for k,v in vars(report).items() if not k.startswith('_') }

             event = { "cortex_job_"+k:v for k,v in vars(job).items() if not k.startswith('_') }

             logger_file.debug(id="20",message="Event before post processing: "+str(event))
             
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

             logger_file.debug(id="25",message="Event after post processing: "+str(event))

             result_copy.update(event)
             outputResults.append(deepcopy(result_copy))

    splunk.Intersplunk.outputResults(outputResults)
