# encoding = utf-8
import sys
import splunk.Intersplunk
from thehive import initialize_thehive_instances
from thehive4py.query.filters import Eq, Contains, Between
from copy import deepcopy
import globals

# Global variables
QUERY = {
    'model': '',
    'field': '',
    'aggs': [{'_agg': 'count', '_name': 'count'}],
    'filter': {},
    'size': 0,
    'withOther': True,
    'cache': False
}

SUPPORTED_CONDITIONS = ["any", "all", "not", "is empty", "is not empty"]
MODEL_DEFAULT = "Case"
FIELD_DEFAULT = "assignee"
FILTER_DATE_DEFAULT = None
FILTER_FIELD_DEFAULT = None
FILTER_CONDITION_DEFAULT = None
FILTER_VALUES_DEFAULT = None

if __name__ == '__main__':
    
    globals.initialize_globals()

    # First, parse the arguments
    # get the keywords and options passed to this command
    keywords, options = splunk.Intersplunk.getKeywordsAndOptions()

    # get the previous search results
    results,dummyresults,settings = splunk.Intersplunk.getOrganizedResults()

    # Initialize this script and return a thehive instance object, a configuration object and defaults values
    instances = initialize_thehive_instances(keywords, settings, acronym="THGS", logger_name="thehive_get_stats")

    outputResults = []

    for (thehive, configuration, defaults, logger_file, instance_id) in instances:

        logger_file.debug(id="1",message="Input keywords: "+str(keywords))
        logger_file.debug(id="2",message="Input results: "+str(results))
        logger_file.info(id="3",message="Start processing with the instance: "+str(instance_id))

        # Prepare and get all cases queries 
        for result in results:

            ## FILTERS ##
            # Check the results to extract interesting fields
            model = configuration.checkAndValidate(result, "model", default=MODEL_DEFAULT, is_mandatory=True)
            field = configuration.checkAndValidate(result, "field", default=FIELD_DEFAULT, is_mandatory=True)
            filterCreatedAt = configuration.checkAndValidate(result, "_createdAt", default=FILTER_DATE_DEFAULT, is_mandatory=False)
            filterUpdatedAt = configuration.checkAndValidate(result, "_updatedAt", default=FILTER_DATE_DEFAULT, is_mandatory=False)
            filterField = configuration.checkAndValidate(result, "filtered_field", default=FILTER_FIELD_DEFAULT, is_mandatory=False)
            filterCondition = configuration.checkAndValidate(result, "filtered_condition", default=FILTER_CONDITION_DEFAULT, is_mandatory=False)
            if filterCondition is not None and filterCondition not in SUPPORTED_CONDITIONS:
                logger_file.error(id="6",message=f"Filter condition not supported, got '{filterCondition}' when only those are supported: {SUPPORTED_CONDITIONS}")
                sys.exit(6)
            filterValues = configuration.checkAndValidate(result, "filtered_values", default=FILTER_VALUES_DEFAULT, is_mandatory=False)

            # Format the query
            filters = {}

            if filterCreatedAt is not None:
                filterCreatedAt = filterCreatedAt.split(" TO ")
                d1 = filterCreatedAt[0] if filterCreatedAt[0] != "*" else "*"
                d2 = filterCreatedAt[1] if filterCreatedAt[1] != "*" else "*"
                if d1 != "*" and d2 != "*":
                    f = Between("_createdAt",d1,d2)
                    filters = f if filters == {} else f&filters
            if filterUpdatedAt is not None:
                filterUpdatedAt = filterUpdatedAt.split(" TO ")
                d1 = filterUpdatedAt[0] if filterUpdatedAt[0] != "*" else "*"
                d2 = filterUpdatedAt[1] if filterUpdatedAt[1] != "*" else "*"
                if d1 != "*" and d2 != "*":
                    f = Between("_updatedAt",d1,d2)
                    filters = f if filters == {} else f&filters
            if filterField is not None and filterCondition is not None:
                if filterValues is not None:
                    sanitizedValues = filterValues.replace(" ","").split(";")
                    if str(sanitizedValues[0]).isdigit():
                        subFilters = [Eq(filterField,int(s)) for s in sanitizedValues if s != "*"]
                    else:
                        subFilters = [Eq(filterField,s) for s in sanitizedValues if s != "*"]

                    # Build the condition
                    f = subFilters.pop()
                    for otherSubF in subFilters:
                        if filterCondition in ["any", "not"]:
                            f = f|otherSubF
                        elif filterCondition == "all":
                            f = f&otherSubF
                    if filterCondition == "not":
                        f = ~f
                    filters = f if filters == {} else f&filters
                
                elif filterCondition in ["is empty", "is not empty"]:
                    filters = Contains(field=filterField)
                    if filterCondition == "is empty":
                        filters = ~filters

            filters = {"_and": [filters]}

            logger_file.debug(id="15",message="Filter is: "+str(filters))

            # Build the query
            QUERY["model"] = model
            QUERY["field"] = field
            QUERY["filter"] = filters

            logger_file.debug(id="20",message="Executing request...")
            response = thehive.session.make_request("POST", path="/api/v1/chart/category", json=QUERY)
            logger_file.debug(id="25",message="Got response: " + str(response))

            for stat in response:
                result_copy = deepcopy(result)
                result_copy["thehive_instance_id"] = instance_id

                if "count" in stat:
                    if stat["_key"] == "_total":
                        stat["_key"] = "Total"
                    result_copy.update({f"thehive_{field}": stat['_key'], "thehive_count": stat['count']})

                
                outputResults.append(deepcopy(result_copy))

            logger_file.debug(id="30",message="Output results: " + str(outputResults))

        splunk.Intersplunk.outputResults(outputResults)