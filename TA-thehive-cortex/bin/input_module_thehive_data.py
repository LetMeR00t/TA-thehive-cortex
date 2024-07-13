
# encoding = utf-8

import time
import sys
import datetime
import json
from thehive import create_thehive_instance_modular_input
from thehive4py.query.filters import Between
from thehive4py.query.page import Paginate
import globals

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
    """

    globals.initialize_globals()

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
    (thehive, configuration, logger_file) = create_thehive_instance_modular_input(instance_id=instance_id, helper=helper, acronym="MI-THD")

    logger_file.debug(id="20",message="TheHive URL instance used after retrieving the configuration: " + str(thehive.session.hive_url))
    logger_file.debug(id="25",message="TheHive connection is ready. Processing modular input parameters...")

    # Get alert arguments
    modular_input_args = {}
    # Get string values from the input form
    modular_input_args["type"] = helper.get_arg('type')
    modular_input_args["date"] = helper.get_arg('date')
    logger_file.debug(id="30",message="Arguments recovered: " + str(modular_input_args))

    # Retrieve the data
    logger_file.debug(id="35",message="Configuration is ready. Collecting the data...")
    
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
    logger_file.debug(id="40",message="This filter will be used: "+str(filters))

    if modular_input_args["type"] == "cases":
        ## CASES ##
        # Get cases using the query
        new_events = thehive.case.find(filters=filters, paginate=paginate)
    elif modular_input_args["type"] == "alerts":
        ## ALERTS ##
        # Get alerts using the query
        new_events = thehive.alert.find(filters=filters, paginate=paginate)
    else:
        logger_file.error(id="50",message="This type of data is not managed by this modular input")
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
            logger_file.debug(id="60",message="TheHive - Tasks: "+str(event["tasks"]))

        ## OBSERVABLES ##
        observables = []
        if modular_input_args["type"] == "cases":
            ## CASES ##
            observables = thehive.case.find_observables(event["_id"])
        elif modular_input_args["type"] == "alerts":
            ## ALERTS ##
            observables = thehive.alert.find_observables(event["_id"])
        event["observables"] = observables
        logger_file.debug(id="65",message="thehive - observables: "+str(event["observables"])) 

        # Index the event
        e = helper.new_event(source="thehive:"+modular_input_args["type"], host=thehive.session.hive_url[8:], index=helper.get_output_index(), sourcetype=helper.get_sourcetype(), data=json.dumps(event))
        ew.write_event(e)

    logger_file.debug(id="70",message=str(len(new_events))+" events were recovered.")

    return 0
