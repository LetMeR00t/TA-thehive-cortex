# encoding = utf-8
import sys, os
import ta_thehive_cortex_declare_lib
import splunk.Intersplunk
from common import Settings
from thehive import TheHive
import splunklib.client as client
from ta_logging import setup_logging
from copy import deepcopy

FILTER_KEYWORD_DEFAULT = "*"
FILTER_STATUS_DEFAULT = "*"
FILTER_SEVERITY_DEFAULT = "*"
FILTER_TAGS_DEFAULT = "*"
FILTER_TITLE_DEFAULT = "*"
FILTER_ASSIGNEE_DEFAULT = "*"
FILTER_DATE_DEFAULT = "* TO *"
MAX_CASES = None
SORT_CASES = None

if __name__ == '__main__':
    
    # First, parse the arguments
    # get the keywords and options passed to this command
    keywords, options = splunk.Intersplunk.getKeywordsAndOptions()

    # get the previous search results
    results,dummyresults,settings = splunk.Intersplunk.getOrganizedResults()

    # Initialiaze settings
    spl = client.connect(app="TA_thehive_cortex",owner="nobody",token=settings["sessionKey"])
    logger = setup_logging("thehive_cases")
    configuration = Settings(spl, logger)
    logger.debug("Fields found = "+str(keywords)) 

    MAX_CASES_DEFAULT = configuration.getTheHiveCasesMax()
    SORT_CASES_DEFAULT = configuration.getTheHiveCasesSort()

    # Create the TheHive instance
    thehive = TheHive(configuration.getTheHiveURL(), configuration.getTheHiveApiKey(), settings["sid"], logger)

    # MANDATORY FIELDS : None
    # OPTIONAL FIELDS
    hasFilterKeyword = True if "keyword" in keywords else False
    hasFilterStatus = True if "status" in keywords else False
    hasFilterSeverity = True if "severity" in keywords else False
    hasFilterTags = True if "tags" in keywords else False
    hasFilterTitle = True if "title" in keywords else False
    hasFilterAssignee = True if "assignee" in keywords else False
    hasFilterDate = True if "date" in keywords else False
    hasMaxCases = True if "max_cases" in keywords else False
    hasSortCases = True if "sort_cases" in keywords else False

    # Get cases
    outputResults = []
    # Prepare and get all cases queries 
    for result in results:
        ## FILTERS ##
        # Check the results to extract interesting fields
        filterKeyword = result["keyword"] if hasFilterKeyword else FILTER_KEYWORD_DEFAULT
        filterStatus = result["status"] if hasFilterStatus else FILTER_STATUS_DEFAULT
        filterSeverity = result["severity"] if hasFilterSeverity else FILTER_SEVERITY_DEFAULT
        filterTags = result["tags"] if hasFilterTags else FILTER_TAGS_DEFAULT
        filterTitle = result["title"] if hasFilterTitle else FILTER_TITLE_DEFAULT
        filterAssignee = result["assignee"] if hasFilterAssignee else FILTER_ASSIGNEE_DEFAULT
        filterDate = result["date"] if hasFilterDate else FILTER_DATE_DEFAULT
        maxCases = result["max_cases"] if hasMaxCases else MAX_CASES_DEFAULT
        sortCases = result["sort_cases"] if hasSortCases else SORT_CASES_DEFAULT


        logger.debug("filterKeyword: "+filterKeyword+", filterStatus: "+filterStatus+", filterSeverity: "+filterSeverity+", filterTags: "+filterTags+", filterTitle: "+filterTitle+", filterAssignee: "+filterAssignee+", filterDate: "+filterDate+", max_cases: "+maxCases+", sort_cases: "+sortCases)

        # create the query from filters
        query = {}
        if filterKeyword != "*":
            new_query = {"_string": filterKeyword}
            query = {"_and": [new_query]}
        if filterStatus != "*":
            new_query = {"_string": "("+" OR ".join(["status:\""+s+"\"" for s in filterStatus.replace(" ","").split(";") if s != "*"])+")"}
            if query == {}:
                query = {"_and": [new_query]}
            else:
                query["_and"][0]["_string"] = query["_and"][0]["_string"]+" AND "+new_query["_string"]
        if filterSeverity != "*":
            new_query = {"_string": "("+" OR ".join(["severity:\""+s+"\"" for s in filterSeverity.replace(" ","").split(";") if s != "*"])+")"}
            if query == {}:
                query = {"_and": [new_query]}
            else:
                query["_and"][0]["_string"] = query["_and"][0]["_string"]+" AND "+new_query["_string"]
        if filterTags != "*":
            new_query = {"_string": "("+" OR ".join(["tags:\""+s+"\"" for s in filterTags.replace(" ","").split(";") if s != "*"])+")"}
            if query == {}:
                query = {"_and": [new_query]}
            else:
                query["_and"][0]["_string"] = query["_and"][0]["_string"]+" AND "+new_query["_string"]
        if filterTitle != "*":
            new_query = {"_string": "title:"+filterTitle}
            if query == {}:
                query = {"_and": [new_query]}
            else:
                query["_and"][0]["_string"] = query["_and"][0]["_string"]+" AND "+new_query["_string"]
        if filterAssignee != "*":
            new_query = {"_string": "("+" OR ".join(["owner:\""+s+"\"" for s in filterAssignee.replace(" ","").split(";") if s != "*"])+")"}
            if query == {}:
                query = {"_and": [new_query]}
            else:
                query["_and"][0]["_string"] = query["_and"][0]["_string"]+" AND "+new_query["_string"]
        if filterDate != "* TO *":
            filterDate = filterDate.split(" TO ")
            d1 = filterDate[0] if filterDate[0] != "*" else "*"
            d2 = filterDate[1] if filterDate[1] != "*" else "*"
            new_query = {"_string": "(startDate:[ "+d1+" TO "+d2+" ])"}
            if query == {}:
                query = {"_and": [new_query]}
            else:
                query["_and"][0]["_string"] = query["_and"][0]["_string"]+" AND "+new_query["_string"]


        logger.info("Query is: "+str(query))
    
        ## CASES ##
        cases = thehive.cases.find_all(query ,range='0-'+maxCases, sort=sortCases)
        for case in cases:
             result_copy = deepcopy(result)
             logger.debug("Get case ID \""+case.id+"\"")
             logger.debug("Case details: "+str(case))

             event = { "thehive_case_"+k:v for k,v in vars(case).items() if not k.startswith('_') }
             
             # Post processing for Splunk
             ## CUSTOM FIELDS ##
             if event["thehive_case_customFields"] != {}:
                 customFields = []
                 for cf in event["thehive_case_customFields"]:
                     customFields.append(cf+"::"+event["thehive_case_customFields"][cf]["string"])
                 event["thehive_case_customFields"] = customFields

             ## METRICS ##
             if event["thehive_case_metrics"] != {}:
                 metrics = []
                 for m in event["thehive_case_metrics"]:
                     metrics.append(m+"::"+str(event["thehive_case_metrics"][m]))
                 event["thehive_case_metrics"] = metrics

             ## DATES ##
             event["thehive_case_startDate"] = event["thehive_case_startDate"]/1000
             if "thehive_case_endDate" in event:
                 event["thehive_case_endDate"] = event["thehive_case_endDate"]/1000
             event["thehive_case_createdAt"] = event["thehive_case_createdAt"]/1000
             if "thehive_case_updatedAt" in event: 
                 event["thehive_case_updatedAt"] = event["thehive_case_updatedAt"]/1000

             ## TASKS ##
             tasks = thehive.cases.get_tasks(case.id,{})
             tasks_statuses = {}
             for task in tasks:
                 if task.status in tasks_statuses:
                     tasks_statuses[task.status] += 1
                 else:
                     tasks_statuses[task.status] = 1
             event["thehive_case_tasks"] = [k+":"+str(v) for k,v in tasks_statuses.items()]

             ## OBSERVABLES ##
             observables = thehive.cases.get_observables(case.id,{})
             event["thehive_case_observables"] = len([o for o in observables if o.status == "Ok"])

         
             result_copy.update(event)
             outputResults.append(deepcopy(result_copy))

    splunk.Intersplunk.outputResults(outputResults)
