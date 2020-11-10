
# encoding = utf-8

import os
import sys
import time
import datetime
import ta_thehive_cortex_declare
from cortex4py.api import Api
import cortex4py
import json
import splunklib.client as client

'''
    IMPORTANT
    Edit only the validate_input and collect_events functions.
    Do not edit any other part in this file.
    This file is generated only once when creating the modular input.
'''
'''
# For advanced users, if you want to create single instance mod input, uncomment this method.
def use_single_instance_mode():
    return True
'''

def validate_input(helper, definition):
    """Implement your own validation logic to validate the input stanza configurations"""
    # This example accesses the modular input variable
    # cortex_protocol = definition.parameters.get('cortex_protocol', None)
    # cortex_host = definition.parameters.get('cortex_host', None)
    # cortex_port = definition.parameters.get('cortex_port', None)
    # cortex_api_key = definition.parameters.get('cortex_api_key', None)
    pass

def collect_events(helper, ew):
    """Implement your data collection logic here

    # The following examples get the arguments of this input.
    # Note, for single instance mod input, args will be returned as a dict.
    # For multi instance mod input, args will be returned as a single value.
    opt_cortex_protocol = helper.get_arg('cortex_protocol')
    opt_cortex_host = helper.get_arg('cortex_host')
    opt_cortex_port = helper.get_arg('cortex_port')
    opt_cortex_api_key = helper.get_arg('cortex_api_key')
    # In single instance mode, to get arguments of a particular input, use
    opt_cortex_protocol = helper.get_arg('cortex_protocol', stanza_name)
    opt_cortex_host = helper.get_arg('cortex_host', stanza_name)
    opt_cortex_port = helper.get_arg('cortex_port', stanza_name)
    opt_cortex_api_key = helper.get_arg('cortex_api_key', stanza_name)

    # get input type
    helper.get_input_type()

    # The following examples get input stanzas.
    # get all detailed input stanzas
    helper.get_input_stanza()
    # get specific input stanza with stanza name
    helper.get_input_stanza(stanza_name)
    # get all stanza names
    helper.get_input_stanza_names()

    # The following examples get options from setup page configuration.
    # get the loglevel from the setup page
    loglevel = helper.get_log_level()
    # get proxy setting configuration
    proxy_settings = helper.get_proxy()
    # get account credentials as dictionary
    account = helper.get_user_credential_by_username("username")
    account = helper.get_user_credential_by_id("account id")
    # get global variable configuration
    global_userdefined_global_var = helper.get_global_setting("userdefined_global_var")

    # The following examples show usage of logging related helper functions.
    # write to the log for this modular input using configured global log level or INFO as default
    helper.log("log message")
    # write to the log using specified log level
    helper.log_debug("log message")
    helper.log_info("log message")
    helper.log_warning("log message")
    helper.log_error("log message")
    helper.log_critical("log message")
    # set the log level for this modular input
    # (log_level can be "debug", "info", "warning", "error" or "critical", case insensitive)
    helper.set_log_level(log_level)

    # The following examples send rest requests to some endpoint.
    response = helper.send_http_request(url, method, parameters=None, payload=None,
                                        headers=None, cookies=None, verify=True, cert=None,
                                        timeout=None, use_proxy=True)
    # get the response headers
    r_headers = response.headers
    # get the response body as text
    r_text = response.text
    # get response body as json. If the body text is not a json string, raise a ValueError
    r_json = response.json()
    # get response cookies
    r_cookies = response.cookies
    # get redirect history
    historical_responses = response.history
    # get response status code
    r_status = response.status_code
    # check the response status, if the status is not sucessful, raise requests.HTTPError
    response.raise_for_status()

    # The following examples show usage of check pointing related helper functions.
    # save checkpoint
    helper.save_check_point(key, state)
    # delete checkpoint
    helper.delete_check_point(key)
    # get checkpoint
    state = helper.get_check_point(key)

    # To create a splunk event
    helper.new_event(data, time=None, host=None, index=None, source=None, sourcetype=None, done=True, unbroken=True)
    """

    '''
    # The following example writes a random number as an event. (Multi Instance Mode)
    # Use this code template by default.
    import random
    data = str(random.randint(0,100))
    event = helper.new_event(source=helper.get_input_type(), index=helper.get_output_index(), sourcetype=helper.get_sourcetype(), data=data)
    ew.write_event(event)
    '''

    '''
    # The following example writes a random number as an event for each input config. (Single Instance Mode)
    # For advanced users, if you want to create single instance mod input, please use this code template.
    # Also, you need to uncomment use_single_instance_mode() above.
    import random
    input_type = helper.get_input_type()
    for stanza_name in helper.get_input_stanza_names():
        data = str(random.randint(0,100))
        event = helper.new_event(source=input_type, index=helper.get_output_index(stanza_name), sourcetype=helper.get_sourcetype(stanza_name), data=data)
        ew.write_event(event)
    '''
    
    # Get Splunk account
    opt_splunk_username = helper.get_global_setting('splunk_username')
    opt_splunk_password = helper.get_global_setting('splunk_password') 
    
    # Initialiaze settings
    spl = client.connect(owner="nobody",username=opt_splunk_username,password=opt_splunk_password)
    
    # Health status
    status = ""
    
    # Get options
    opt_cortex_protocol = helper.get_arg('cortex_protocol')
    opt_cortex_host = helper.get_arg('cortex_host')
    opt_cortex_port = helper.get_arg('cortex_port')
    opt_cortex_api_key = helper.get_arg('cortex_api_key')
    
    url = opt_cortex_protocol+"://"+opt_cortex_host+":"+opt_cortex_port
    
    try :
        api = Api(url, opt_cortex_api_key)
        # Try to connect to the API by recovering all enabled analyzers
        api.analyzers.find_all({}, range='all')
        status = "GREEN - Everything works fine !"
        helper.log_info(status)

        # Get analyzers
        kv_cortex_analyzers = spl.kvstore["kv_cortex_analyzers"].data
        kv_cortex_analyzers.delete()
        analyzers = api.analyzers.find_all({}, range='all')
    
        # Display enabled analyzers' names
        for analyzer in analyzers:
            response = kv_cortex_analyzers.insert(json.dumps({"analyzer": analyzer.name, "description": analyzer.description, "dataTypeAllowed": ";".join(analyzer.dataTypeList)}))
          
    except cortex4py.exceptions.NotFoundError as e:
        status = "RED - [10-RESOURCE NOT FOUND] Cortex service is unavailable, is configuration correct ?"
        helper.log_error(status)
    except cortex4py.exceptions.ServiceUnavailableError as e:
        status = "RED - [11-SERVICE UNAVAILABLE] Cortex service is unavailable, is configuration correct ?"
        helper.log_error(status)
    except cortex4py.exceptions.AuthenticationError as e:
        status = "ORANGE - [12-AUTHENTICATION ERROR] Credentials are invalid"
        helper.log_error(status)
    event = helper.new_event(source=helper.get_input_type(), index=helper.get_output_index(), sourcetype=helper.get_sourcetype(), data="{\"status\": \""+status+"\"}")
    ew.write_event(event)