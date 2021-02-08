# encoding = utf-8
import ta_thehive_cortex_declare
from cortex import initialize_cortex_instance
import splunk.Intersplunk

if __name__ == '__main__':
    
    # First, parse the arguments
    # get the keywords and options passed to this command
    keywords, options = splunk.Intersplunk.getKeywordsAndOptions()

    # get the previous search results
    results,dummyresults,settings = splunk.Intersplunk.getOrganizedResults()

    # Initialize this script and return a cortex instance object, a configuration object and defaults values
    (cortex, configuration, defaults, logger) = initialize_cortex_instance(keywords, settings ,logger_name="cortex_refresh_analyzers")

    logger.debug("[CRA-1] Input keywords: "+str(keywords))
    logger.debug("[CRA-2] Input results: "+str(results))


    outputResults = []
    # Get analyzers
    analyzers = cortex.analyzers.find_all({}, range='all')

    for analyzer in analyzers:
        result = { "cortex_analyzer_"+k:v for k,v in analyzer.__dict__.items()}
        logger.debug("[CRA-5] Getting this analyzer: "+str(result))
        outputResults.append(result)

    splunk.Intersplunk.outputResults(outputResults)
