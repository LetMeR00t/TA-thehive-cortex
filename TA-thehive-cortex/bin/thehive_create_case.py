# encoding = utf-8
import ta_thehive_cortex_declare
import splunk.Intersplunk
from thehive import initialize_thehive_instance
from thehive4py.models import Case, CaseTask, Severity, Tlp, Pap
from copy import deepcopy
import time

# Global variables
SEVERITY_DEFAULT = Severity.MEDIUM
DATE_DEFAULT = time.time()
TLP_DEFAULT = Tlp.AMBER
PAP_DEFAULT = Pap.AMBER

if __name__ == '__main__':
    
    # First, parse the arguments
    # get the keywords and options passed to this command
    keywords, options = splunk.Intersplunk.getKeywordsAndOptions()

    # get the previous search results
    results,dummyresults,settings = splunk.Intersplunk.getOrganizedResults()

    # Initialize this script and return a thehive instance object, a configuration object and defaults values
    (thehive, configuration, defaults, logger) = initialize_thehive_instance(keywords, settings ,logger_name="thehive_create_cases")

    logger.debug("[THCC-1] Input keywords: "+str(keywords))
    logger.debug("[THCC-2] Input results: "+str(results))

    outputResults = []
    for result in results:
        createTitle = configuration.checkAndValidate(result, "title", is_mandatory=True)
        createSeverity = int(configuration.checkAndValidate(result, "severity", default=SEVERITY_DEFAULT, is_mandatory=False))
        createTags = configuration.checkAndValidate(result, "tags", default=[], is_mandatory=False).split("; ")
        createPAP = int(configuration.checkAndValidate(result, "pap", default=PAP_DEFAULT, is_mandatory=True))
        createDate = float(configuration.checkAndValidate(result, "date", default=DATE_DEFAULT, is_mandatory=False))*1000
        createTLP = int(configuration.checkAndValidate(result, "tlp", default=TLP_DEFAULT, is_mandatory=True))
        createDescription = configuration.checkAndValidate(result, "description", default="", is_mandatory=True)
        createTasks = [CaseTask(title=t) for t in configuration.checkAndValidate(result, "tasks", default=[], is_mandatory=False).split(" ;")]

        # create the query from parameters
        new_case = Case(title=createTitle, severity=createSeverity, tags=createTags, pap=createPAP, startDate=createDate, tlp=createTLP, description=createDescription, tasks=createTasks)

        logger.info("[THCC-5] Query is: "+str(new_case.jsonify()))

        ## CREATE THE CASE ##
        response = thehive.create_case(new_case)
        if response.status_code not in (200,201):
            logger.error("[THCC-10-ERROR] "+str(response.content))

        case = response.json()
        logger.debug("[THCC-15] Getting this case: "+str(case))

        ## CREATE TASKS (apparently, they are not created when the case is created) ##
        #for ct in createTasks:
        #    logger.debug("[THCC-20] Create a new task for the case: "+str(ct))
        #    thehive.create_case_task(case["id"],ct)

        result_copy = deepcopy(result)

        logger.debug("[THCC-25] Get case ID \""+str(case["id"])+"\"")

        event = { "thehive_case_"+k:v for k,v in case.items() if not k.startswith('_') }

        logger.debug("[THCC-30] Event before post processing: "+str(event))
        
        # Post processing for Splunk
        ## CUSTOM FIELDS ##
        if "thehive_case_customFields" in event and event["thehive_case_customFields"] != {}:
            customFields = []
            for cf in event["thehive_case_customFields"]:
                customFields.append(cf+"::"+event["thehive_case_customFields"][cf]["string"])
            event["thehive_case_customFields"] = customFields
            logger.debug("[THCC-35] TheHive - Custom fields: "+str(customFields))

        ## METRICS ##
        if "thehive_case_metrics" in event and event["thehive_case_metrics"] != {}:
            metrics = []
            for m in event["thehive_case_metrics"]:
                metrics.append(m+"::"+str(event["thehive_case_metrics"][m]))
            event["thehive_case_metrics"] = metrics
            logger.debug("[THCC-36] TheHive - Metrics: "+str(metrics))

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
        logger.debug("[THCC-40] TheHive - Tasks: "+str(event["thehive_case_tasks"]))

        ## OBSERVABLES ##
        observables = thehive.get_case_observables(case["id"])
        event["thehive_case_observables"] = len([o for o in observables.json() if o["status"] == "Ok"])
        logger.debug("[THCC-45] TheHive - Observables: "+str(event["thehive_case_observables"])) 

        logger.debug("[THCC-46] Event after post processing: "+str(event))
        
        result_copy.update(event)
        outputResults.append(deepcopy(result_copy))

    splunk.Intersplunk.outputResults(outputResults)
