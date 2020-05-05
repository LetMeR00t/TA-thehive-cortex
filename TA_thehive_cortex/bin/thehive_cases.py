# encoding = utf-8
import sys, os
import ta_thehive_cortex_declare_lib
import splunk.Intersplunk
from cortex import Cortex, CortexJob, Settings
import splunklib.client as client
from ta_logging import setup_logging

if __name__ == '__main__':
    
    # First, parse the arguments
    # get the keywords and options passed to this command
    keywords, options = splunk.Intersplunk.getKeywordsAndOptions()

    # get the previous search results
    results,dummyresults,settings = splunk.Intersplunk.getOrganizedResults()

    # Initialiaze settings
    spl = client.connect(app="TA_thehive_cortex",owner="nobody",token=settings["sessionKey"])
    logger = setup_logging("thehive_cases")
    configuration = Settings(spl, logger)
    logger.debug("Fields found = "+str(keywords)) 

    # Create the TheHive instance
    thehive = TheHive(configuration.getTheHiveURL(), configuration.getTheHiveApiKey(), settings["sid"], logger)

    # Get cases


    splunk.Intersplunk.outputResults(results)
