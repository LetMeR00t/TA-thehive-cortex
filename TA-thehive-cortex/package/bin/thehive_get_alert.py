# encoding = utf-8
import splunk.Intersplunk
from thehive import initialize_thehive_instances
from copy import deepcopy
import globals
import time

if __name__ == '__main__':
    
    globals.initialize_globals()

    # First, parse the arguments
    # get the keywords and options passed to this command
    keywords, options = splunk.Intersplunk.getKeywordsAndOptions()

    # get the previous search results
    results,dummyresults,settings = splunk.Intersplunk.getOrganizedResults()

    # Initialize this script and return a thehive instance object, a configuration object and defaults values
    instances = initialize_thehive_instances(keywords, settings, acronym="THGA", logger_name="thehive_get_alert")

    outputResults = []

    for (thehive, configuration, defaults, logger_file, instance_id) in instances:

        logger_file.debug(id="1",message="Input keywords: "+str(keywords))
        logger_file.debug(id="2",message="Input results: "+str(results))
        logger_file.info(id="3",message="Start processing with the instance: "+str(instance_id))

        # Prepare and get all queries 
        for result in results:
            ## FILTERS ##
            # Check the results to extract interesting fields
            alert_id = configuration.checkAndValidate(result, "alert_id", is_mandatory=True)
            logger_file.debug(id="5",message="Getting this alert: " + str(alert_id))
        
            # Get alert using the alert endpoint
            alert = thehive.alert.get(alert_id)
            result_copy = deepcopy(result)

            # Remove double underscore due to private data in the response
            event = {("thehive_alert_"+k).replace("__","_"):v for k,v in alert.items()}

            # Remove double underscore due to private data in the response
            event = {("thehive_alert_"+k).replace("__","_"):v for k,v in alert.items()}

            logger_file.debug(id="15",message="Event before post processing: "+str(event))
            
            ## CUSTOM FIELDS ##
            if "thehive_alert_customFields" in event and event["thehive_alert_customFields"] != []:
                customFields = []
                logger_file.debug(id="30",message="Found custom fields: "+str(event["thehive_alert_customFields"]))
                for cf in event["thehive_alert_customFields"]:
                    cftype = cf["type"]
                    if cftype=="date":
                        if "value" in cf and cf["value"] is not None:
                            cf["value"] = time.strftime("%c %z",time.gmtime(int(cf["value"])/1000))
                        else:
                            cf["value"] = "None"
                    customFields.append(cf["name"]+"::"+str(cf["value"]))
                event["thehive_alert_customFields"] = customFields
                logger_file.debug(id="35",message="TheHive - Custom fields: "+str(customFields))

            ## DATES ##
            event["thehive_alert_date"] = event["thehive_alert_date"]/1000
            if "thehive_alert_endDate" in event and event["thehive_alert_endDate"] is not None:
                event["thehive_alert_endDate"] = event["thehive_alert_endDate"]/1000
            event["thehive_alert_createdAt"] = event["thehive_alert_createdAt"]/1000
            if "thehive_alert_updatedAt" in event and event["thehive_alert_updatedAt"] is not None: 
                event["thehive_alert_updatedAt"] = event["thehive_alert_updatedAt"]/1000

            ## OBSERVABLES ##
            observables = thehive.alert.find_observables(alert["_id"])
            event["thehive_alert_observables"] = [str(o) for o in observables]
            logger_file.debug(id="45",message="thehive - observables: "+str(len(event["thehive_alert_observables"]))) 

            ## TTPS ##
            ttps = thehive.alert.find_procedures(alert["_id"])
            event["thehive_alert_ttps"] = [str(ttp) for ttp in ttps]
            logger_file.debug(id="50",message="thehive - ttps: "+str(len(event["thehive_alert_ttps"]))) 


            logger_file.debug(id="55",message="Event after post processing: "+str(event))
        
            result_copy.update(event)
            result_copy["thehive_instance_id"] = instance_id
            outputResults.append(deepcopy(result_copy))

    splunk.Intersplunk.outputResults(outputResults)