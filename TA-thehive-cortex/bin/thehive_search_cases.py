# encoding = utf-8
import splunk.Intersplunk
from thehive import initialize_thehive_instances
from thehive4py.query.filters import Eq, Like, Between
from thehive4py.query.sort import Asc, Desc
from thehive4py.query.page import Paginate
from copy import deepcopy
import time
import globals

# Global variables
FILTER_KEYWORD_DEFAULT = "*"
FILTER_STATUS_DEFAULT = "*"
FILTER_SEVERITY_DEFAULT = "*"
FILTER_TAGS_DEFAULT = "*"
FILTER_TITLE_DEFAULT = "*"
FILTER_ASSIGNEE_DEFAULT = "*"
FILTER_DATE_DEFAULT = "* TO *"

if __name__ == '__main__':
    
    globals.initialize_globals()

    # First, parse the arguments
    # get the keywords and options passed to this command
    keywords, options = splunk.Intersplunk.getKeywordsAndOptions()

    # get the previous search results
    results,dummyresults,settings = splunk.Intersplunk.getOrganizedResults()

    # Initialize this script and return a thehive instance object, a configuration object and defaults values
    instances = initialize_thehive_instances(keywords, settings, acronym="THSC", logger_name="thehive_search_cases")

    outputResults = []

    for (thehive, configuration, defaults, logger_file, instance_id) in instances:

        logger_file.debug(id="1",message="Input keywords: "+str(keywords))
        logger_file.debug(id="2",message="Input results: "+str(results))
        logger_file.info(id="3",message="Start processing with the instance: "+str(instance_id))

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
            paginate = Paginate(start=0,end=int(maxCases))
            sortCases = configuration.checkAndValidate(result, "sort_cases", default=defaults["SORT_CASES_DEFAULT"], is_mandatory=False)
            # Check if the sortCases is using the right object (will not if set manually in the search)
            if type(sortCases) not in [Asc,Desc]:
                sortCases = Desc(sortCases[1:]) if sortCases[0] == "-" else Asc(sortCases)

            logger_file.debug(id="5",message="Filters are: filterKeyword: "+filterKeyword+", filterStatus: "+filterStatus+", filterSeverity: "+filterSeverity+", filterTags: "+filterTags+", filterTitle: "+filterTitle+", filterAssignee: "+filterAssignee+", filterDate: "+filterDate+", max_cases: "+str(paginate)+", sort_cases: "+str(sortCases))

            # Format the query
            filters = {}
            
            if filterKeyword != FILTER_KEYWORD_DEFAULT:
                f = Eq("keyword", filterKeyword)
                filters = f
            if filterStatus != FILTER_STATUS_DEFAULT:
                subFilters = [Eq("status",s) for s in filterStatus.replace(" ","").split(";") if s != "*"]
                f = subFilters.pop()
                for otherSubF in subFilters:
                    f = f|otherSubF
                filters = f if filters == {} else f&filters
            if filterSeverity != FILTER_SEVERITY_DEFAULT:
                subFilters = [Eq("severity",int(s)) for s in filterSeverity.replace(" ","").split(";") if s != "*"]
                f = subFilters.pop()
                for otherSubF in subFilters:
                    f = f|otherSubF
                filters = f if filters == {} else f&filters
            if filterTags != FILTER_TAGS_DEFAULT:
                subFilters = [Eq("tags",s) for s in filterTags.replace(" ","").split(";") if s != "*"]
                f = subFilters.pop()
                for otherSubF in subFilters:
                    f = f|otherSubF
                filters = f if filters == {} else f&filters
            if filterTitle != FILTER_TITLE_DEFAULT:
                f = Like("title", filterTitle)
                filters = f if filters == {} else f&filters
            if filterAssignee != FILTER_ASSIGNEE_DEFAULT:
                subFilters = [Eq("assignee",s) for s in filterAssignee.replace(" ","").split(";") if s != "*"]
                f = subFilters.pop()
                for otherSubF in subFilters:
                    f = f|otherSubF
                filters = f if filters == {} else f&filters
            if filterDate != FILTER_DATE_DEFAULT:
                filterDate = filterDate.split(" TO ")
                d1 = filterDate[0] if filterDate[0] != "*" else "*"
                d2 = filterDate[1] if filterDate[1] != "*" else "*"
                f = Between("startDate",d1,d2)
                filters = f if filters == {} else f&filters

            logger_file.debug(id="15",message="Query is: "+str(filters))
        
            ## CASES ##
            # Get cases using the query
            cases = thehive.case.find(filters=filters, sortby=sortCases, paginate=paginate)

            for case in cases:
                logger_file.debug(id="25",message="Getting this case: "+str(case))
                result_copy = deepcopy(result)

                logger_file.debug(id="26",message="Get case ID \""+str(case["_id"])+"\"")

                # Remove double underscore due to private data in the response
                event = {("thehive_case_"+k).replace("__","_"):v for k,v in case.items()}

                logger_file.debug(id="30",message="Event before post processing: "+str(event))
                
                # Post processing for Splunk
                ## CUSTOM FIELDS ##
                if "thehive_case_customFields" in event and event["thehive_case_customFields"] != []:
                    customFields = []
                    logger_file.debug(id="31",message="Found custom fields: "+str(event["thehive_case_customFields"]))
                    for cf in event["thehive_case_customFields"]:
                        cftype = cf["type"]
                        if cftype=="date":
                            if "value" in cf and cf["value"] is not None:
                                cf["value"] = time.strftime("%c %z",time.gmtime(int(cf["value"])/1000))
                            else:
                                cf["value"] = "None"
                        customFields.append(cf["name"]+"::"+str(cf["value"]))
                    event["thehive_case_customFields"] = customFields
                    logger_file.debug(id="35",message="TheHive - Custom fields: "+str(customFields))

                ## DATES ##
                event["thehive_case_startDate"] = event["thehive_case_startDate"]/1000
                if "thehive_case_endDate" in event and event["thehive_case_endDate"] is not None:
                    event["thehive_case_endDate"] = event["thehive_case_endDate"]/1000
                event["thehive_case_createdAt"] = event["thehive_case_createdAt"]/1000
                if "thehive_case_updatedAt" in event and event["thehive_case_updatedAt"] is not None: 
                    event["thehive_case_updatedAt"] = event["thehive_case_updatedAt"]/1000

                ## TASKS ##
                tasks = thehive.case.find_tasks(case["_id"])
                tasks_statuses = {}
                for task in tasks:
                    if task["status"] in tasks_statuses:
                        tasks_statuses[task["status"]] += 1
                    else:
                        tasks_statuses[task["status"]] = 1
                event["thehive_case_tasks"] = [k+":"+str(v) for k,v in tasks_statuses.items()]
                logger_file.debug(id="40",message="TheHive - Tasks: "+str(event["thehive_case_tasks"]))

                ## OBSERVABLES ##
                observables = thehive.case.find_observables(case["_id"])
                event["thehive_case_observables"] = [str(o) for o in observables]
                logger_file.debug(id="45",message="thehive - observables: "+str(len(event["thehive_case_observables"]))) 

                ## TTPS ##
                ttps = thehive.case.find_procedures(case["_id"])
                event["thehive_case_ttps"] = [str(ttp) for ttp in ttps]
                logger_file.debug(id="46",message="thehive - ttps: "+str(len(event["thehive_case_ttps"]))) 

                logger_file.debug(id="47",message="Event after post processing: "+str(event))
            
                result_copy.update(event)
                result_copy["thehive_instance_id"] = instance_id
                outputResults.append(deepcopy(result_copy))

    splunk.Intersplunk.outputResults(outputResults)
