# encoding = utf-8
import ta_thehive_cortex_declare
from cortex import initialize_cortex_instance
import splunk.Intersplunk
import globals

if __name__ == '__main__':
    
    globals.initialize_globals()

    # First, parse the arguments
    # get the keywords and options passed to this command
    keywords, options = splunk.Intersplunk.getKeywordsAndOptions()

    # get the previous search results
    results,dummyresults,settings = splunk.Intersplunk.getOrganizedResults()

    # Initialize this script and return a cortex instance object, a configuration object and defaults values
    (cortex, configuration, defaults, logger_file) = initialize_cortex_instance(keywords, settings ,logger_name="cortex_refresh_analyzers")

    logger_file.debug(id="CRA1",message="Input keywords: "+str(keywords))
    logger_file.debug(id="CRA2",message="Input results: "+str(results))


    outputResults = []
    # Get analyzers
    analyzers = cortex.analyzers.find_all({}, range='all')

    for analyzer in analyzers:
        result = { "cortex_analyzer_"+k:v for k,v in analyzer.__dict__.items()}
        logger_file.debug(id="CRA5",message="Getting this analyzer: "+str(result))
        outputResults.append(result)

    splunk.Intersplunk.outputResults(outputResults)
