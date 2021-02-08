# encoding = utf-8
import ta_thehive_cortex_declare
import splunk.Intersplunk
from thehive import initialize_thehive_instance
from thehive4py.query import And, Eq, Or, String
from copy import deepcopy
import json

# Global variables
FILTER_KEYWORD_DEFAULT = "*"
FILTER_STATUS_DEFAULT = "*"
FILTER_SEVERITY_DEFAULT = "*"
FILTER_TAGS_DEFAULT = "*"
FILTER_TITLE_DEFAULT = "*"
FILTER_ASSIGNEE_DEFAULT = "*"
FILTER_DATE_DEFAULT = "* TO *"

if __name__ == '__main__':
    
    # First, parse the arguments
    # get the keywords and options passed to this command
    keywords, options = splunk.Intersplunk.getKeywordsAndOptions()

    # get the previous search results
    results,dummyresults,settings = splunk.Intersplunk.getOrganizedResults()

    # Initialize this script and return a thehive instance object, a configuration object and defaults values
    (thehive, configuration, defaults, logger) = initialize_thehive_instance(keywords, settings ,logger_name="thehive_search_cases")

    logger.debug("[THSC-1] Input keywords: "+str(keywords))
    logger.debug("[THSC-2] Input results: "+str(results))

    outputResults = []
    # Prepare and get all cases queries 
    for result in results:
        ## FILTERS ##
        # Check the results to extract interesting fields
        filterKeyword = configuration.checkAndValidate(result, "keyword", default=FILTER_KEYWORD_DEFAULT, is_mandatory=False)
        filterStatus = configuration.checkAndValidate(result, "status", default=FILTER_STATUS_DEFAULT, is_mandatory=False)
        filterSeverity = configuration.checkAndValidate(result, "severity", default=FILTER_SEVERITY_DEFAULT, is_mandatory=False)
        filterTags = configuration.checkAndValidate(result, "tags", default=FILTER_TAGS_DEFAULT, is_mandatory=False)
        filterTitle = configuration.checkAndValidate(result, "title", default=FILTER_TITLE_DEFAULT, is_mandatory=False)
        filterAssignee = configuration.checkAndValidate(result, "assignee", default=FILTER_ASSIGNEE_DEFAULT, is_mandatory=False)
        filterDate = configuration.checkAndValidate(result, "date", default=FILTER_DATE_DEFAULT, is_mandatory=False)
        maxCases = configuration.checkAndValidate(result, "max_cases", default=defaults["MAX_CASES_DEFAULT"], is_mandatory=False)
        sortCases = configuration.checkAndValidate(result, "sort_cases", default=defaults["SORT_CASES_DEFAULT"], is_mandatory=False)

        logger.debug("[THSC-5] Filters are: filterKeyword: "+filterKeyword+", filterStatus: "+filterStatus+", filterSeverity: "+filterSeverity+", filterTags: "+filterTags+", filterTitle: "+filterTitle+", filterAssignee: "+filterAssignee+", filterDate: "+filterDate+", max_cases: "+maxCases+", sort_cases: "+sortCases)

        # Format the query
        query = {}
        elements = []
        if filterKeyword != FILTER_KEYWORD_DEFAULT:
            element = String(filterKeyword)
            elements.append(element)
        if filterStatus != FILTER_STATUS_DEFAULT:
            element = String("("+" OR ".join(["status:\""+s+"\"" for s in filterStatus.replace(" ","").split(";") if s != "*"])+")")
            elements.append(element)
        if filterSeverity != FILTER_SEVERITY_DEFAULT:
            element = String("("+" OR ".join(["severity:\""+s+"\"" for s in filterSeverity.replace(" ","").split(";") if s != "*"])+")")
            elements.append(element)
        if filterTags != FILTER_TAGS_DEFAULT:
            element = String("("+" OR ".join(["tags:\""+s+"\"" for s in filterTags.replace(" ","").split(";") if s != "*"])+")")
            elements.append(element)
        if filterTitle != FILTER_TITLE_DEFAULT:
            element = String("title:"+filterTitle)
            elements.append(element)
        if filterAssignee != FILTER_ASSIGNEE_DEFAULT:
            element = String("("+" OR ".join(["owner:\""+s+"\"" for s in filterAssignee.replace(" ","").split(";") if s != "*"])+")")
            elements.append(element)
        if filterDate != FILTER_DATE_DEFAULT:
            filterDate = filterDate.split(" TO ")
            d1 = filterDate[0] if filterDate[0] != "*" else "*"
            d2 = filterDate[1] if filterDate[1] != "*" else "*"
            element = String("(startDate:[ "+d1+" TO "+d2+" ])")
            elements.append(element)
        query = And(*elements)

        logger.info("[THSC-15] Query is: "+json.dumps(query))
    
        ## CASES ##
        # Get cases using the query
        cases = thehive.find_cases(query=query,range='0-'+maxCases, sort=sortCases)

        # Check status_code and process results
        if cases.status_code not in (200,201):
            logger.error("[THSC-20-ERROR] "+str(cases.content))

        for case in cases.json():
             logger.debug("[THSC-25] Getting this case: "+str(case))
             result_copy = deepcopy(result)

             logger.debug("[THSC-26] Get case ID \""+str(case["id"])+"\"")

             event = { "thehive_case_"+k:v for k,v in case.items() if not k.startswith('_') }

             logger.debug("[THSC-30] Event before post processing: "+str(event))
             
             # Post processing for Splunk
             ## CUSTOM FIELDS ##
             if "thehive_case_customFields" in event and event["thehive_case_customFields"] != {}:
                 customFields = []
                 for cf in event["thehive_case_customFields"]:
                     customFields.append(cf+"::"+event["thehive_case_customFields"][cf]["string"])
                 event["thehive_case_customFields"] = customFields
                 logger.debug("[THSC-35] TheHive - Custom fields: "+str(customFields))

             ## METRICS ##
             if "thehive_case_metrics" in event and event["thehive_case_metrics"] != {}:
                 metrics = []
                 for m in event["thehive_case_metrics"]:
                     metrics.append(m+"::"+str(event["thehive_case_metrics"][m]))
                 event["thehive_case_metrics"] = metrics
                 logger.debug("[THSC-36] TheHive - Metrics: "+str(metrics))

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
             logger.debug("[THSC-40] TheHive - Tasks: "+str(event["thehive_case_tasks"]))

             ## OBSERVABLES ##
             observables = thehive.get_case_observables(case["id"])
             event["thehive_case_observables"] = len([o for o in observables.json() if "status" in o and o["status"] == "Ok"])
             logger.debug("[THSC-45] TheHive - Observables: "+str(event["thehive_case_observables"])) 

             logger.debug("[THSC-46] Event after post processing: "+str(event))
         
             result_copy.update(event)
             outputResults.append(deepcopy(result_copy))

    splunk.Intersplunk.outputResults(outputResults)
