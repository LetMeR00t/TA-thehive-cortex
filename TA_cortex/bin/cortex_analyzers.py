# encoding = utf-8
import sys, os
import logging, logging.handlers
import json
import traceback
import time
import splunk
from splunk.persistconn.application import PersistentServerConnectionApplication

sys.path.insert(0, os.path.dirname(__file__))

import ta_cortex_declare_lib

from cortex import Cortex, CortexJob, Settings
import splunklib.client as client


def setup_logging():
    logger = logging.getLogger('command_cortex_analyzer.log')
    SPLUNK_HOME = os.environ['SPLUNK_HOME']

    LOGGING_DEFAULT_CONFIG_FILE = os.path.join(SPLUNK_HOME, 'etc', 'log.cfg')
    LOGGING_LOCAL_CONFIG_FILE = os.path.join(SPLUNK_HOME, 'etc', 'log-local.cfg')
    LOGGING_STANZA_NAME = 'python'
    LOGGING_FILE_NAME = "command_cortex_analyzer.log"
    BASE_LOG_PATH = os.path.join('var', 'log', 'splunk')
    LOGGING_FORMAT = "%(asctime)s %(levelname)-s\t%(module)s:%(lineno)d - %(message)s"
    splunk_log_handler = logging.handlers.RotatingFileHandler(os.path.join(SPLUNK_HOME, BASE_LOG_PATH, LOGGING_FILE_NAME), mode='a')
    splunk_log_handler.setFormatter(logging.Formatter(LOGGING_FORMAT))
    logger.addHandler(splunk_log_handler)
    splunk.setupSplunkLogger(logger, LOGGING_DEFAULT_CONFIG_FILE, LOGGING_LOCAL_CONFIG_FILE, LOGGING_STANZA_NAME)
    return logger

logger = setup_logging()
# Default logging
logger.setLevel(logging.INFO)

class CortexAnalyzers(PersistentServerConnectionApplication):
    def __init__(self, _command_line, _command_arg):
        super(PersistentServerConnectionApplication, self).__init__()

    # Handle a syncronous from splunkd.
    def handle(self, in_string):
        """
        Called for a simple synchronous request.
        @param in_string: request data passed in
        @rtype: string or dict
        @return: String to return in response.  If a dict was passed in,
                 it will automatically be JSON encoded before being returned.
        """

        # Parse the arguments
        args = self.parse_in_string(in_string)

        # Get the user information
        sessionKey = args['session']['authtoken']
        spl = client.connect(app="TA_cortex",owner="nobody",token=sessionKey)

        # Initialiaze settings
        configuration = Settings(spl, logger)
        if int(configuration.getSetting("logging","debug")) == 1:
            logger.setLevel(logging.DEBUG)
            logger.debug("LEVEL changed to DEBUG according to the configuration")
    
        # Create the Cortex instance
        cortex = Cortex(configuration.getURL(), configuration.getApiKey(), logger=logger)

        kv_cortex_analyzers = spl.kvstore["kv_cortex_analyzers"].data
        kv_cortex_analyzers.delete()

        try:
          analyzers = cortex.api.analyzers.find_all({}, range='all')
  
          # Display enabled analyzers' names
          for analyzer in analyzers:
              response = kv_cortex_analyzers.insert(json.dumps({"analyzer": analyzer.name, "description": analyzer.description, "dataTypeAllowed": ";".join(analyzer.dataTypeList)}))
              logger.debug("Response: "+str(response))

          logger.info("Recovered analyzers: "+", ".join([a.name for a in analyzers]))
  
        except Exception as e:
            tb = traceback.format_exc()
            logger.error(str(e)+" - "+str(tb))


        payload = {
            "updated": time.time(),
            "result": "Your analyzers have been reloaded"
        }
        return {'payload': payload, 'status': 200}


    def convert_to_dict(self, query):
        """
        Create a dictionary containing the parameters.
        """
        parameters = {}

        for key, val in query:

            # If the key is already in the list, but the existing entry isn't a list then make the
            # existing entry a list and add thi one
            if key in parameters and not isinstance(parameters[key], list):
                parameters[key] = [parameters[key], val]

            # If the entry is already included as a list, then just add the entry
            elif key in parameters:
                parameters[key].append(val)

            # Otherwise, just add the entry
            else:
                parameters[key] = val

        return parameters

    def parse_in_string(self, in_string):
        """
        Parse the in_string
        """

        params = json.loads(in_string)

        params['method'] = params['method'].lower()

        params['form_parameters'] = self.convert_to_dict(params.get('form', []))
        params['query_parameters'] = self.convert_to_dict(params.get('query', []))

        return params
