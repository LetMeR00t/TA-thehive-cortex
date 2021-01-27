# encoding = utf-8
import sys, os
import ta_thehive_cortex_declare
from common import Settings
from cortex import Cortex, CortexJob
import splunklib.client as client
from cortex import initialize_cortex_instance
from copy import deepcopy
import splunk.Intersplunk

if __name__ == '__main__':
    
    # First, parse the arguments
    # get the keywords and options passed to this command
    keywords, options = splunk.Intersplunk.getKeywordsAndOptions()

    # get the previous search results
    results,dummyresults,settings = splunk.Intersplunk.getOrganizedResults()

    # Initialize this script and return a cortex instance object, a configuration object and defaults values
    (cortex, configuration, defaults, logger) = initialize_cortex_instance(keywords, settings ,logger_name="cortex_refresh_analyzers")


    outputResults = []
    # Get analyzers
    analyzers = cortex.analyzers.find_all({}, range='all')

    for analyzer in analyzers:
        result = { "cortex_analyzer_"+k:v for k,v in analyzer.__dict__.items()}

        outputResults.append(result)

    splunk.Intersplunk.outputResults(outputResults)
