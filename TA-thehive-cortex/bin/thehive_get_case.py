# encoding = utf-8
import sys
import splunk.Intersplunk
from thehive import initialize_thehive_instances
from thehive4py.query.filters import Eq
from copy import deepcopy
import time
import globals

if __name__ == '__main__':
    
    globals.initialize_globals()

    # First, parse the arguments
    # get the keywords and options passed to this command
    keywords, options = splunk.Intersplunk.getKeywordsAndOptions()

    # get the previous search results
    results,dummyresults,settings = splunk.Intersplunk.getOrganizedResults()

    # Initialize this script and return a thehive instance object, a configuration object and defaults values
    instances = initialize_thehive_instances(keywords, settings, acronym="THGC", logger_name="thehive_get_case")

    outputResults = []

    for (thehive, configuration, defaults, logger_file, instance_id) in instances:

        logger_file.debug(id="1",message="Input keywords: "+str(keywords))
        logger_file.debug(id="2",message="Input results: "+str(results))
        logger_file.info(id="3",message="Start processing with the instance: "+str(instance_id))

        # Prepare and get all cases queries 
        for result in results:
            ## FILTERS ##
            # Check the results to extract interesting fields
            case_number = configuration.checkAndValidate(result, "case_number", is_mandatory=True)
            logger_file.debug(id="10",message="Getting this case number: " + str(case_number))

            case = thehive.case.get(int(case_number.replace("#","")))

            result_copy = deepcopy(result)
            event = {("thehive_case_"+k).replace("__","_"):v for k,v in case.items()}
            logger_file.debug(id="15",message="Event before post processing: "+str(event))

            ## CUSTOM FIELDS ##
            if "thehive_case_customFields" in event and event["thehive_case_customFields"] != []:
                customFields = []
                logger_file.debug(id="30",message="Found custom fields: "+str(event["thehive_case_customFields"]))
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