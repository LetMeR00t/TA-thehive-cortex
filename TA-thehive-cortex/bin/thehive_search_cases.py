# encoding = utf-8
import sys, os
import ta_thehive_cortex_declare
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
    logger = setup_logging("thehive_cases")
    configuration = Settings(spl, logger)

    MAX_CASES_DEFAULT = configuration.getTheHiveCasesMax()
    SORT_CASES_DEFAULT = configuration.getTheHiveCasesSort()

    # Create the TheHive instance
    thehive = TheHive(configuration.getTheHiveURL(), configuration.getTheHiveApiKey(), settings["sid"], logger)

    # Get cases
    outputResults = []
    # Prepare and get all cases queries 
    for result in results:
        ## FILTERS ##
        # Check the results to extract interesting fields
        filterKeyword = check_and_validate(result, "keyword", default=FILTER_KEYWORD_DEFAULT, is_mandatory=False)
        filterStatus = check_and_validate(result, "status", default=FILTER_STATUS_DEFAULT, is_mandatory=False)
        filterSeverity = check_and_validate(result, "severity", default=FILTER_SEVERITY_DEFAULT, is_mandatory=False)
        filterTags = check_and_validate(result, "tags", default=FILTER_TAGS_DEFAULT, is_mandatory=False)
        filterTitle = check_and_validate(result, "title", default=FILTER_TITLE_DEFAULT, is_mandatory=False)
        filterAssignee = check_and_validate(result, "assignee", default=FILTER_ASSIGNEE_DEFAULT, is_mandatory=False)
        filterDate = check_and_validate(result, "date", default=FILTER_DATE_DEFAULT, is_mandatory=False)
        maxCases = check_and_validate(result, "max_cases", default=MAX_CASES_DEFAULT, is_mandatory=False)
        sortCases = check_and_validate(result, "sort_cases", default=SORT_CASES_DEFAULT, is_mandatory=False)


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
        cases = thehive.find_cases(query=query,range='0-'+maxCases, sort=sortCases)
        if cases.status_code not in (200,201):
            logger.error(cases.content)
        for case in cases.json():
             result_copy = deepcopy(result)
             logger.debug("Get case ID \""+case["id"]+"\"")
             logger.debug("Case details: "+str(case))

             event = { "thehive_case_"+k:v for k,v in case.items() if not k.startswith('_') }
             
             # Post processing for Splunk
             ## CUSTOM FIELDS ##
             if "thehive_case_customFields" in event and event["thehive_case_customFields"] != {}:
                 customFields = []
                 for cf in event["thehive_case_customFields"]:
                     customFields.append(cf+"::"+event["thehive_case_customFields"][cf]["string"])
                 event["thehive_case_customFields"] = customFields

             ## METRICS ##
             if "thehive_case_metrics" in event and event["thehive_case_metrics"] != {}:
                 metrics = []
                 for m in event["thehive_case_metrics"]:
                     metrics.append(m+"::"+str(event["thehive_case_metrics"][m]))
                 event["thehive_case_metrics"] = metrics

             ## DATES ##
             event["thehive_case_startDate"] = event["thehive_case_startDate"]/1000
             if "thehive_case_endDate" in event and event["thehive_case_endDate"] is not None:
                 event["thehive_case_endDate"] = event["thehive_case_endDate"]/1000
             event["thehive_case_createdAt"] = event["thehive_case_createdAt"]/1000
             if "thehive_case_updatedAt" in event and event["thehive_case_updatedAt"] is not None: 
                 event["thehive_case_updatedAt"] = event["thehive_case_updatedAt"]/1000

             ## TASKS ##
             tasks = thehive.get_case_tasks(case["id"])
             tasks_statuses = {}
             for task in tasks.json():
                 if task["status"] in tasks_statuses:
                     tasks_statuses[task["status"]] += 1
                 else:
                     tasks_statuses[task["status"]] = 1
             event["thehive_case_tasks"] = [k+":"+str(v) for k,v in tasks_statuses.items()]

             ## OBSERVABLES ##
             observables = thehive.get_case_observables(case["id"])
             event["thehive_case_observables"] = len([o for o in observables.json() if "status" in o and o["status"] == "Ok"])

         
             result_copy.update(event)
             outputResults.append(deepcopy(result_copy))

    splunk.Intersplunk.outputResults(outputResults)
