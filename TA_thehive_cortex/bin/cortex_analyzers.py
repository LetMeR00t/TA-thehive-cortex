# encoding = utf-8
import sys, os
import json
import traceback
import time
from splunk.persistconn.application import PersistentServerConnectionApplication

sys.path.insert(0, os.path.dirname(__file__))

import ta_thehive_cortex_declare_lib
from common import Settings
from ta_logging import setup_logging

from cortex import Cortex, CortexJob
import splunklib.client as client


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
        spl = client.connect(app="TA_thehive_cortex",owner="nobody",token=sessionKey)

        logger = setup_logging("cortex_analyzers")
        # Initialiaze settings
        configuration = Settings(spl, logger)
    
        # Create the Cortex instance
        cortex = Cortex(configuration.getCortexURL(), configuration.getCortexApiKey(), logger=logger)

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
