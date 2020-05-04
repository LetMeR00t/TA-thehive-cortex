# encoding = utf-8
import sys, os
import ta_thehive_cortex_declare_lib
import splunk.Intersplunk
import logging, logging.handlers
from cortex import Cortex, CortexJob, Settings
import splunklib.client as client


def setup_logging():
    logger = logging.getLogger('command_cortex_jobs.log')    
    SPLUNK_HOME = os.environ['SPLUNK_HOME']
    
    LOGGING_DEFAULT_CONFIG_FILE = os.path.join(SPLUNK_HOME, 'etc', 'log.cfg')
    LOGGING_LOCAL_CONFIG_FILE = os.path.join(SPLUNK_HOME, 'etc', 'log-local.cfg')
    LOGGING_STANZA_NAME = 'python'
    LOGGING_FILE_NAME = "command_cortex_jobs.log"
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

    # get parameters if any
    filter_data = sys.argv[1] if len(sys.argv)>1 else ""
    filter_datatypes = sys.argv[2] if len(sys.argv)>2 else "*"
    filter_analyzers = sys.argv[3] if len(sys.argv)>3 else "*"

    logger.debug("filter_data: "+filter_data+", filter_datatypes: "+filter_datatypes+", filter_analyzers: "+filter_analyzers)

    # create the query from filters
    query = {}
    if filter_data != "":
        new_query = {"_field":"data","_value":filter_data}
        query = new_query
    if filter_datatypes != "*":
        new_query = {"_in":{"_field":"dataType","_values":filter_datatypes.replace(" ","").split(";")}}
        if query == {}:
            query = new_query
        else:
            query = {"_and":[query,new_query]}
    if filter_analyzers != "*":
        new_query = {"_in":{"_field":"workerDefinitionId","_values":filter_analyzers.replace(" ","").split(";")}}
        if query == {}:
            query = new_query
        elif "_and" in query:
            query["_and"].append(new_query)
        else:
            query = {"_and":[query,new_query]}

    logger.info("Query is: "+str(query))

    # Create the Cortex instance
    cortex = Cortex(configuration.getURL(), configuration.getApiKey(), settings["sid"], logger)

    # Get jobs 
    jobs = cortex.api.jobs.find_all(query ,range='0-'+configuration.getJobsMax(), sort=configuration.getJobsSort())
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
         event = {"id": job.id,"data": "["+job.dataType.upper()+"] "+job.data ,"analyzer": job.analyzerName ,"createdAt": job.createdAt/1000 ,"createdBy": job.organization+"/"+job.createdBy ,"tlp": job.tlp ,"status": job.status ,"summary": summaries}
         if "startDate" in dir(job):
             event["startDate"] = job.startDate/1000
         if "endDate" in dir(job): 
             event["endDate"] = job.endDate/1000 
         results.append(event)


    splunk.Intersplunk.outputResults(results)
