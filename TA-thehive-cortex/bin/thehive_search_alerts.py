# encoding = utf-8
import ta_thehive_cortex_declare
import splunk.Intersplunk
from thehive import initialize_thehive_instance
from thehive4py.query import And, Eq, Or, Like, Between
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
    (thehive, configuration, defaults, logger) = initialize_thehive_instance(keywords, settings ,logger_name="thehive_search_alerts")

    logger.debug("[THSA-1] Input keywords: "+str(keywords))
    logger.debug("[THSA-2] Input results: "+str(results))

    outputResults = []
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
        sortAlerts = configuration.checkAndValidate(result, "sort_alerts", default=defaults["SORT_ALERTS_DEFAULT"], is_mandatory=False)

        logger.debug("[THSA-5] Filters are: filterType: "+filterType+", filterSeverity: "+filterSeverity+", filterTags: "+filterTags+", filterTitle: "+filterTitle+", filterRead: "+filterRead+", filterSource: "+filterSource+", filterDate: "+filterDate+", max_alerts: "+maxAlerts+", sort_alerts: "+sortAlerts)

        # Format the query
        query = {}
        elements = []
        if filterType != FILTER_TYPE_DEFAULT:
            element = Or(*[Like("type",s) for s in filterType.replace(" ","").split(";") if s != "*"])
            elements.append(element)
        if filterSeverity != FILTER_SEVERITY_DEFAULT:
            element = Or(*[Eq("severity",int(s)) for s in filterSeverity.replace(" ","").split(";") if s != "*"])
            elements.append(element)
        if filterTags != FILTER_TAGS_DEFAULT:
            element = Or(*[Eq("tags",s) for s in filterTags.replace(" ","").split(";") if s != "*"])
            elements.append(element)
        if filterTitle != FILTER_TITLE_DEFAULT:
            element = Like("title",filterTitle)
            elements.append(element)
        if filterRead != FILTER_READ_DEFAULT:
            read = False if int(filterRead)==0 else True
            element = Eq("read",read)
            elements.append(element)
        if filterSource != FILTER_SOURCE_DEFAULT:
            element = Or(*[Eq("source",s) for s in filterSource.replace(" ","").split(";") if s != "*"])
            elements.append(element)
        if filterDate != FILTER_DATE_DEFAULT:
            filterDate = filterDate.split(" TO ")
            d1 = filterDate[0] if filterDate[0] != "*" else "*"
            d2 = filterDate[1] if filterDate[1] != "*" else "*"
            element = Between("date",d1,d2)
            elements.append(element)
        query = And(*elements)

        logger.info("[THSA-15] Query is: "+json.dumps(query))
    
        ## ALERTS ##
        # Get alerts using the query
        alerts = thehive.find_alerts(query=query,range='0-'+maxAlerts, sort=sortAlerts)

        # Check status_code and process results
        if alerts.status_code not in (200,201):
            logger.error("[THSA-20-ERROR] "+str(alerts.content))

        for alert in alerts.json():
             logger.debug("[THSA-25] Getting this alert: "+str(alert))
             result_copy = deepcopy(result)

             logger.debug("[THSA-26] Get alert ID \""+str(alert["id"])+"\"")

             event = { "thehive_alert_"+k:v for k,v in alert.items() if not k.startswith('_') }

             logger.debug("[THSA-30] Event before post processing: "+str(event))
             
             # Post processing for Splunk
             ## CUSTOM FIELDS ##
             if "thehive_alert_customFields" in event and event["thehive_alert_customFields"] != {}:
                 customFields = []
                 logger.debug("[THSA-31] Found custom fields: "+str(event["thehive_alert_customFields"]))
                 for cf in event["thehive_alert_customFields"]:
                     for cftype in ["string","number","integer","boolean","date","float"]:
                         if cftype in event["thehive_alert_customFields"][cf]:
                             # Pre-processing
                             if cftype=="date":
                                 event["thehive_alert_customFields"][cf][cftype] = time.strftime("%c %z",time.gmtime(int(event["thehive_alert_customFields"][cf][cftype])/1000))
                             customFields.append(cf+"::"+str(event["thehive_alert_customFields"][cf][cftype]))
                             break
                 event["thehive_alert_customFields"] = customFields
                 logger.debug("[THSA-35] TheHive - Custom fields: "+str(customFields))

             ## METRICS ##
             if "thehive_alert_metrics" in event and event["thehive_alert_metrics"] != {}:
                 metrics = []
                 for m in event["thehive_alert_metrics"]:
                     metrics.append(m+"::"+str(event["thehive_alert_metrics"][m]))
                 event["thehive_alert_metrics"] = metrics
                 logger.debug("[THSA-36] TheHive - Metrics: "+str(metrics))

             ## DATES ##
             event["thehive_alert_date"] = event["thehive_alert_date"]/1000
             if "thehive_alert_endDate" in event and event["thehive_alert_endDate"] is not None:
                 event["thehive_alert_endDate"] = event["thehive_alert_endDate"]/1000
             event["thehive_alert_createdAt"] = event["thehive_alert_createdAt"]/1000
             if "thehive_alert_updatedAt" in event and event["thehive_alert_updatedAt"] is not None: 
                 event["thehive_alert_updatedAt"] = event["thehive_alert_updatedAt"]/1000

             ## ARTIFACTS ##
             event["thehive_alert_artifacts"] = len(event["thehive_alert_artifacts"])


             logger.debug("[THSA-46] Event after post processing: "+str(event))
         
             result_copy.update(event)
             outputResults.append(deepcopy(result_copy))

    splunk.Intersplunk.outputResults(outputResults)
