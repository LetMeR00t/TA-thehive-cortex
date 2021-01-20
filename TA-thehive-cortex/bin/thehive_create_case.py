# encoding = utf-8
import sys, os
import ta_thehive_cortex_declare
import splunk.Intersplunk
from common import Settings
from thehive import TheHive
from thehive4py.models import Case, CaseTask
import splunklib.client as client
from ta_logging import setup_logging
from copy import deepcopy
import time

CREATE_SEVERITY_DEFAULT = 2 # MEDIUM
CREATE_DATE_DEFAULT = time.time()
CREATE_TLP_DEFAULT = 2 # AMBER
CREATE_PAP_DEFAULT = 2 # AMBER

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
    logger = setup_logging("thehive_cases")
    configuration = Settings(spl, settings, logger)

    MAX_CASES_DEFAULT = configuration.getTheHiveCasesMax()
    SORT_CASES_DEFAULT = configuration.getTheHiveCasesSort()

    # Create the TheHive instance
    (thehive_username, thehive_api_key) = configuration.getInstanceUsernameApiKey(instance_id)
    thehive_url = configuration.getInstanceURL(instance_id)
    thehive_proxies = configuration.getInstanceSetting(instance_id,"proxies")
    thehive_cert = configuration.getInstanceSetting(instance_id,"cert")
    thehive_organisation = configuration.getInstanceSetting(instance_id,"organisation")
    thehive_version = configuration.getInstanceSetting(instance_id,"type") 
    thehive = TheHive(url=thehive_url, apiKey=thehive_api_key, proxies=thehive_proxies, cert=thehive_cert, organisation=thehive_organisation, version=thehive_version, sid=settings["sid"], logger=logger)


    outputResults = []
    for result in results:
        createTitle = configuration.check_and_validate(result, "title", is_mandatory=True)
        createSeverity = int(configuration.check_and_validate(result, "severity", default=CREATE_SEVERITY_DEFAULT, is_mandatory=False))
        createTags = configuration.check_and_validate(result, "tags", default=[], is_mandatory=False).split("; ")
        createPAP = int(configuration.check_and_validate(result, "pap", default=CREATE_PAP_DEFAULT, is_mandatory=True))
        createDate = float(configuration.check_and_validate(result, "date", default=CREATE_DATE_DEFAULT, is_mandatory=False))*1000
        createTLP = int(configuration.check_and_validate(result, "tlp", default=CREATE_TLP_DEFAULT, is_mandatory=True))
        createDescription = configuration.check_and_validate(result, "description", default="", is_mandatory=True)
        createTasks = [CaseTask(title=t) for t in configuration.check_and_validate(result, "tasks", default=[], is_mandatory=False).split("; ")]

        # create the query from parameters
        new_case = Case(title=createTitle, severity=createSeverity, tags=createTags, pap=createPAP, startDate=createDate, tlp=createTLP, description=createDescription, tasks=createTasks)

        logger.info("Query is: "+str(new_case.jsonify()))

        ## CREATE THE CASE ##
        response = thehive.create_case(new_case)
        if response.status_code not in (200,201):
            logger.error(response.content)

        case = response.json()

        ## CREATE TASKS (apparently, they are not created when the case is created) ##
        for ct in createTasks:
            thehive.create_case_task(case["id"],ct)

        result_copy = deepcopy(result)

        logger.debug("Get case ID \""+case["id"]+"\"")
        logger.debug("Case details: "+str(case))

        event = { "thehive_case_"+k:v for k,v in case.items() if not k.startswith('_') }
        
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
        event["thehive_case_observables"] = len([o for o in observables.json() if o["status"] == "Ok"])

        
        result_copy.update(event)
        outputResults.append(deepcopy(result_copy))

    splunk.Intersplunk.outputResults(outputResults)
