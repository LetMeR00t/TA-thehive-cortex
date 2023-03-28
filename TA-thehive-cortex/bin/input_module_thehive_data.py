
# encoding = utf-8

import time
import sys
import datetime
import json
from thehive import TheHive, create_thehive_instance_modular_input
from thehive4py.query.filters import Between
from thehive4py.query.page import Paginate

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
    # instance_id = definition.parameters.get('instance_id', None)
    # type = definition.parameters.get('type', None)
    # date = definition.parameters.get('date', None)
    pass

def collect_events(helper, ew):
    """Implement your data collection logic here

    # The following examples get the arguments of this input.
    # Note, for single instance mod input, args will be returned as a dict.
    # For multi instance mod input, args will be returned as a single value.
    opt_instance_id = helper.get_arg('instance_id')
    opt_type = helper.get_arg('type')
    opt_date = helper.get_arg('date')
    # In single instance mode, to get arguments of a particular input, use
    opt_instance_id = helper.get_arg('instance_id', stanza_name)
    opt_type = helper.get_arg('type', stanza_name)
    opt_date = helper.get_arg('date', stanza_name)

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
    # Set the current LOG level
    helper.log_info("[MI-THD-5] LOG level to: " + helper.log_level)
    helper.set_log_level(helper.log_level)

    # Get current stanza information
    input_stanza = helper.get_input_stanza()
    stanza = list(input_stanza.keys())[0]

    helper.log_info("[MI-THD-10] Modular input \"{}\" for TheHive data started at {}".format(stanza,time.time()))

    # Get the instance connection and initialize settings
    instance_id = helper.get_arg("instance_id")
    helper.log_debug("[MI-THD-15] TheHive instance found: " + str(instance_id))

    # get the previous search results
    (thehive, configuration, logger) = create_thehive_instance_modular_input(instance_id=instance_id, helper=helper)

    helper.log_debug("[MI-THD-20] TheHive URL instance used after retrieving the configuration: " + str(thehive.session.hive_url))
    helper.log_debug("[MI-THD-25] TheHive connection is ready. Processing modular input parameters...")

    # Get alert arguments
    modular_input_args = {}
    # Get string values from the input form
    modular_input_args["type"] = helper.get_arg('type')
    modular_input_args["date"] = helper.get_arg('date')
    helper.log_debug("[MI-THD-30] Arguments recovered: " + str(modular_input_args))

    # Retrieve the data
    helper.log_debug("[MI-THD-35] Configuration is ready. Collecting the data...")
    
    # Prepare to store the new events
    new_events = []
    # Limit set to 50,000 results to recover
    paginate = Paginate(start=0,end=50000)

    # Check the interval set
    interval = int(input_stanza[stanza]["interval"])

    # Calculte d2 which is the latest date
    now = datetime.datetime.timestamp(datetime.datetime.now())

    ## Round it to the minute
    d2 = now - now%60

    # Calculate d1 which is the earliest date
    d1 = d2 - interval

    # Multiply by 1,000 for TheHive
    filters = Between(modular_input_args["date"],d1*1000,d2*1000)
    helper.log_debug("[MI-THD-40] This filter will be used: "+str(filters))

    if modular_input_args["type"] == "cases":
        ## CASES ##
        # Get cases using the query
        new_events = thehive.case.find(filters=filters, paginate=paginate)
    elif modular_input_args["type"] == "alerts":
        ## ALERTS ##
        # Get alerts using the query
        new_events = thehive.alert.find(filters=filters, paginate=paginate)
    else:
        helper.log_error("[MI-THD-50-ERROR] This type of data is not managed by this modular input")
        sys.exit(50)

    # Store the events accordingly
    for event in new_events:
        # Post processing before indexing

        ## DATES ##
        if modular_input_args["type"] == "cases":
            event["startDate"] = event["startDate"]/1000
            if "endDate" in event and event["endDate"] is not None:
                event["endDate"] = event["endDate"]/1000
        event["_createdAt"] = event["_createdAt"]/1000
        if "_updatedAt" in event and event["_updatedAt"] is not None: 
            event["_updatedAt"] = event["_updatedAt"]/1000

        # Set the _time of the event to the created/updated time
        event["_time"] = event[modular_input_args["date"]]

        ## TASKS ##
        tasks = []
        if modular_input_args["type"] == "cases":
            ## CASES ##
            tasks = thehive.case.find_tasks(event["_id"])
            event["tasks"] = tasks
            logger.debug("[MI-THD-60] TheHive - Tasks: "+str(event["tasks"]))

        ## OBSERVABLES ##
        observables = []
        if modular_input_args["type"] == "cases":
            ## CASES ##
            observables = thehive.case.find_observables(event["_id"])
        elif modular_input_args["type"] == "alerts":
            ## ALERTS ##
            observables = thehive.alert.find_observables(event["_id"])
        event["observables"] = observables
        logger.debug("[MI-THD-60] thehive - observables: "+str(event["observables"])) 

        # Index the event
        e = helper.new_event(source="thehive:"+modular_input_args["type"], host=thehive.session.hive_url[8:], index=helper.get_output_index(), sourcetype=helper.get_sourcetype(), data=json.dumps(event))
        ew.write_event(e)

    helper.log_info("[MI-THD-60] "+str(len(new_events))+" events were recovered.")

    return 0
