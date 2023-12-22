# encoding = utf-8
import splunk.Intersplunk
from thehive import initialize_thehive_instances
from thehive4py.query.sort import Asc, Desc
from thehive4py.query import Eq, Like, Between
from thehive4py.query.page import Paginate
from copy import deepcopy
import json
import time

# Global variables
FILTER_TYPE_DEFAULT = "*"
FILTER_SEVERITY_DEFAULT = "*"
FILTER_TAGS_DEFAULT = "*"
FILTER_READ_DEFAULT = "*"
FILTER_TITLE_DEFAULT = "*"
FILTER_SOURCE_DEFAULT = "*"
FILTER_DATE_DEFAULT = "* TO *"

if __name__ == '__main__':
    
    # First, parse the arguments
    # get the keywords and options passed to this command
    keywords, options = splunk.Intersplunk.getKeywordsAndOptions()

    # get the previous search results
    results,dummyresults,settings = splunk.Intersplunk.getOrganizedResults()

    # Initialize this script and return a thehive instance object, a configuration object and defaults values
    instances = initialize_thehive_instances(keywords, settings ,logger_name="thehive_search_alerts")

    outputResults = []

    for (thehive, configuration, defaults, logger, instance_id) in instances:

        logger.debug("[THSA-1] Input keywords: "+str(keywords))
        logger.debug("[THSA-2] Input results: "+str(results))
        logger.info("[THSA-3] Start processing with the instance: "+str(instance_id))

        # Prepare and get all alerts queries 
        for result in results:
            ## FILTERS ##
            # Check the results to extract interesting fields
            filterType = configuration.checkAndValidate(result, "type", default=FILTER_TYPE_DEFAULT, is_mandatory=False)
            filterSeverity = configuration.checkAndValidate(result, "severity", default=FILTER_SEVERITY_DEFAULT, is_mandatory=False)
            filterTags = configuration.checkAndValidate(result, "tags", default=FILTER_TAGS_DEFAULT, is_mandatory=False)
            filterTitle = configuration.checkAndValidate(result, "title", default=FILTER_TITLE_DEFAULT, is_mandatory=False)
            filterRead = configuration.checkAndValidate(result, "read", default=FILTER_READ_DEFAULT, is_mandatory=False)
            filterSource = configuration.checkAndValidate(result, "source", default=FILTER_SOURCE_DEFAULT, is_mandatory=False)
            filterDate = configuration.checkAndValidate(result, "date", default=FILTER_DATE_DEFAULT, is_mandatory=False)
            maxAlerts = configuration.checkAndValidate(result, "max_alerts", default=defaults["MAX_ALERTS_DEFAULT"], is_mandatory=False)
            paginate = Paginate(start=0,end=int(maxAlerts))
            sortAlerts = configuration.checkAndValidate(result, "sort_alerts", default=defaults["SORT_ALERTS_DEFAULT"], is_mandatory=False)
            # Check if the sortCases is using the right object (will not if set manually in the search)
            if type(sortAlerts) not in [Asc,Desc]:
                sortAlerts = Desc(sortAlerts[1:]) if sortAlerts[0] == "-" else Asc(sortAlerts)

            logger.debug("[THSA-5] Filters are: filterType: "+filterType+", filterSeverity: "+filterSeverity+", filterTags: "+filterTags+", filterTitle: "+filterTitle+", filterRead: "+filterRead+", filterSource: "+filterSource+", filterDate: "+filterDate+", max_alerts: "+str(maxAlerts)+", sort_alerts: "+str(sortAlerts))

            # Format the query
            filters = {}

            if filterType != FILTER_TYPE_DEFAULT:
                subFilters = [Like("type",s) for s in filterType.replace(" ","").split(";") if s != "*"]
                f = subFilters.pop()
                for otherSubF in subFilters:
                    f = f|otherSubF
                filters = f
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
            if filterRead != FILTER_READ_DEFAULT:
                read = False if int(filterRead)==0 else True
                f = Eq("read", read)
                filters = f if filters == {} else f&filters
            if filterSource != FILTER_SOURCE_DEFAULT:
                subFilters = [Eq("source",s) for s in filterSource.replace(" ","").split(";") if s != "*"]
                f = subFilters.pop()
                for otherSubF in subFilters:
                    f = f|otherSubF
                filters = f if filters == {} else f&filters
            if filterDate != FILTER_DATE_DEFAULT:
                filterDate = filterDate.split(" TO ")
                d1 = filterDate[0] if filterDate[0] != "*" else "*"
                d2 = filterDate[1] if filterDate[1] != "*" else "*"
                f = Between("date",d1,d2)
                filters = f if filters == {} else f&filters

            logger.info("[THSA-15] Query is: "+str(filters))
        
            ## ALERTS ##
            # Get alerts using the query
            alerts = thehive.alert.find(filters=filters, sortby=sortAlerts, paginate=paginate)

            for alert in alerts:
                logger.debug("[THSA-25] Getting this alert: "+str(alert))
                result_copy = deepcopy(result)

                logger.debug("[THSA-26] Get alert ID \""+str(alert["_id"])+"\"")

                # Remove double underscore due to private data in the response
                event = {("thehive_alert_"+k).replace("__","_"):v for k,v in alert.items()}

                logger.debug("[THSA-30] Event before post processing: "+str(event))
                
                ## CUSTOM FIELDS ##
                if "thehive_alert_customFields" in event and event["thehive_alert_customFields"] != []:
                    customFields = []
                    logger.debug("[THSA-31] Found custom fields: "+str(event["thehive_alert_customFields"]))
                    for cf in event["thehive_alert_customFields"]:
                        cftype = cf["type"]
                        if cftype=="date":
                            if "value" in cf and cf["value"] is not None:
                                cf["value"] = time.strftime("%c %z",time.gmtime(int(cf["value"])/1000))
                            else:
                                cf["value"] = "None"
                        customFields.append(cf["name"]+"::"+str(cf["value"]))
                    event["thehive_alert_customFields"] = customFields
                    logger.debug("[THSA-35] TheHive - Custom fields: "+str(customFields))

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
                logger.debug("[THSC-45] thehive - observables: "+str(len(event["thehive_alert_observables"]))) 

                ## TTPS ##
                ttps = thehive.alert.find_procedures(alert["_id"])
                event["thehive_alert_ttps"] = [str(ttp) for ttp in ttps]
                logger.debug("[THSC-46] thehive - ttps: "+str(len(event["thehive_alert_ttps"]))) 


                logger.debug("[THSA-46] Event after post processing: "+str(event))
            
                result_copy.update(event)
                outputResults.append(deepcopy(result_copy))

    splunk.Intersplunk.outputResults(outputResults)
