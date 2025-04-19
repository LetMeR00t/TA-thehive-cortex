# encoding = utf-8
import sys
from typing import Tuple
import ta_thehive_cortex_declare
from thehive4py.client import TheHiveApi
from thehive4py.query.filters import _FilterBase
from thehive4py.query.page import Paginate
from thehive4py.query.sort import Asc, SortExpr
from common import LoggerFile, Settings, Utils
import splunklib.client as client
from ta_logging import setup_logging
import certifi


def initialize_thehive_instances(keywords, settings, acronym, logger_name="script"):
    """This function is used to initialize a TheHive instance"""
    logger = setup_logging(logger_name)
    logger_file = LoggerFile(logger, acronym)

    # Check the existence of the instance_id
    if len(keywords) == 1:
        instances_id = keywords[0].split(",")
    else:
        logger_file.error(
            id="TH1",
            message="MISSING_INSTANCE_ID - No instance ID was given to the script",
        )
        exit(1)

    instances = []
    for instance_id in instances_id:
        instances.append(
            create_thehive_instance(instance_id, settings, logger, acronym=acronym)
        )

    return instances


def create_thehive_instance(instance_id, settings, logger, acronym):
    """This function is used to create an instance of TheHive"""
    logger_file = LoggerFile(logger, acronym)
    # Initialize settings
    token = (
        settings["sessionKey"] if "sessionKey" in settings else settings["session_key"]
    )
    spl = client.connect(app="TA-thehive-cortex", owner="nobody", token=token)
    logger_file.debug(id="TH5", message="Connection to Splunk done")
    configuration = Settings(spl, settings, logger_file)
    logger_file.debug(id="TH6", message="Settings recovered")

    defaults = {
        "MAX_CASES_DEFAULT": configuration.getTheHiveCasesMax(),
        "SORT_CASES_DEFAULT": configuration.getTheHiveCasesSort(),
        "MAX_ALERTS_DEFAULT": configuration.getTheHiveAlertsMax(),
        "SORT_ALERTS_DEFAULT": configuration.getTheHiveAlertsSort(),
        "TTP_CATALOG_NAME": configuration.getTheHiveTTPCatalogName(),
        "ATTACHMENT_PREFIX": configuration.getTheHiveCreationAttachmentPrefix(),
        "MAX_CREATION_RETRY": configuration.getTheHiveCreationMaxRetry(),
    }

    # Get default instance if any is set
    thehive_default_instance = configuration.getTheHiveDefaultInstance()
    instance_id_final = (
        thehive_default_instance if instance_id == "<default>" else instance_id
    )

    if instance_id_final is None or (
        instance_id_final == "" and instance_id == "<default>"
    ):
        logger_file.error(
            id="TH10",
            message="Your alert is using the <default> instance ID setting which is empty in your configuration page. Please update the parameter accordingly",
        )
        sys.exit(10)

    # Create the TheHive instance
    (thehive_username, thehive_secret) = configuration.getInstanceUsernameApiKey(
        instance_id_final
    )
    thehive_url = configuration.getInstanceURL(instance_id_final)
    thehive_authentication_type = configuration.getInstanceSetting(
        instance_id_final, "authentication_type"
    )
    thehive_proxies = configuration.getInstanceSetting(instance_id_final, "proxies")
    thehive_cert = configuration.getInstanceSetting(instance_id_final, "client_cert")
    thehive_cert = None if thehive_cert == "-" else thehive_cert
    thehive_organisation = configuration.getInstanceSetting(
        instance_id_final, "organisation"
    )
    thehive_version = configuration.getInstanceSetting(instance_id_final, "type")
    thehive = None

    if thehive_authentication_type == "password":
        logger_file.debug(
            id="TH15",
            message="TheHive instance will be initialized with a password (not an API key)",
        )
        thehive = TheHive4Splunk(
            url=thehive_url,
            username=thehive_username,
            password=thehive_secret,
            proxies=thehive_proxies,
            verify=True,
            cert=thehive_cert,
            organisation=thehive_organisation,
            version=thehive_version,
            sid=settings["sid"],
            logger_file=logger_file,
        )
    elif thehive_authentication_type == "api_key":
        logger_file.debug(
            id="TH16",
            message="TheHive instance will be initialized with an API Key (not a password)",
        )
        thehive = TheHive4Splunk(
            url=thehive_url,
            apiKey=thehive_secret,
            proxies=thehive_proxies,
            verify=True,
            cert=thehive_cert,
            organisation=thehive_organisation,
            version=thehive_version,
            sid=settings["sid"],
            logger_file=logger_file,
        )
    else:
        logger_file.error(
            id="TH20",
            message="WRONG_AUTHENTICATION_TYPE - Authentication type is not one of the expected values (password or api_key), given value: "
            + thehive_authentication_type,
        )
        exit(20)

    return (thehive, configuration, defaults, logger_file, instance_id)


def create_thehive_instance_modular_input(instance_id, helper, acronym):
    """This function is used to create an instance of TheHive specifically for modular inputs that don't provide settings information"""
    logger_file = LoggerFile(helper.logger, command_id=acronym)

    # Initialize settings
    token = (
        helper.context_meta["session_key"]
        if "session_key" in helper.context_meta
        else None
    )
    if token is not None:
        spl = client.connect(app="TA-thehive-cortex", owner="nobody", token=token)
    else:
        spl = None
    configuration = Settings(client=spl, settings=None, logger_file=logger_file)
    logger_file.debug(id="TH25", message="Settings recovered")

    # Get default instance if any is set
    thehive_default_instance = configuration.getTheHiveDefaultInstance()
    instance_id_final = (
        thehive_default_instance if instance_id == "<default>" else instance_id
    )

    if instance_id_final == "" and instance_id == "<default>":
        logger_file.error(
            id="TH30",
            message="Your alert is using the <default> instance ID setting which is empty in your configuration page. Please update the parameter accordingly",
        )
        sys.exit(30)

    # Create the TheHive instance
    (thehive_username, thehive_secret) = configuration.getInstanceUsernameApiKey(
        instance_id_final
    )
    # As we are in a modular input, we can't retrieve the thehive_secret information, we will use the helper instead
    thehive_secret = helper.get_user_credential_by_username(thehive_username)[
        "password"
    ]
    thehive_url = configuration.getInstanceURL(instance_id_final)
    thehive_authentication_type = configuration.getInstanceSetting(
        instance_id_final, "authentication_type"
    )
    thehive_proxies = configuration.getInstanceSetting(instance_id_final, "proxies")
    thehive_cert = configuration.getInstanceSetting(instance_id_final, "client_cert")
    thehive_cert = None if thehive_cert == "-" else thehive_cert
    thehive_organisation = configuration.getInstanceSetting(
        instance_id_final, "organisation"
    )
    thehive_version = configuration.getInstanceSetting(instance_id_final, "type")
    thehive = None

    if thehive_authentication_type == "password":
        logger_file.debug(
            id="TH35",
            message="TheHive instance will be initialized with a password (not an API key)",
        )
        thehive = TheHive4Splunk(
            url=thehive_url,
            username=thehive_username,
            password=thehive_secret,
            proxies=thehive_proxies,
            verify=True,
            cert=thehive_cert,
            organisation=thehive_organisation,
            version=thehive_version,
            sid=None,
            logger_file=logger_file,
        )
    elif thehive_authentication_type == "api_key":
        logger_file.debug(
            id="TH40",
            message="TheHive instance will be initialized with an API Key (not a password)",
        )
        thehive = TheHive4Splunk(
            url=thehive_url,
            apiKey=thehive_secret,
            proxies=thehive_proxies,
            verify=True,
            cert=thehive_cert,
            organisation=thehive_organisation,
            version=thehive_version,
            sid=None,
            logger_file=logger_file,
        )
    else:
        logger_file.error(
            id="TH50",
            message="WRONG_AUTHENTICATION_TYPE - Authentication type is not one of the expected values (password or api_key), given value: "
            + thehive_authentication_type,
        )
        exit(20)

    return (thehive, configuration, logger_file)


class TheHive4Splunk(TheHiveApi):
    """This class is used to represent a TheHive instance
    Most of parameters are reused from the python library of TheHive
    """

    def __init__(
        self,
        url=None,
        username=None,
        password=None,
        apiKey=None,
        proxies={},
        cert=None,
        verify=True,
        organisation=None,
        version=None,
        sid=None,
        logger_file=None,
    ):

        self._logger_file = logger_file

        self.logger_file.debug(id="TH1", message="Version is: " + version)

        self._utils = Utils(logger_file=logger_file)

        try:
            if apiKey is not None:
                super().__init__(
                    url=str(url),
                    username=username,
                    apikey=str(apiKey),
                    proxies=proxies,
                    verify=verify,
                    cert=cert,
                    organisation=organisation,
                )
            elif password is not None:
                super().__init__(
                    url=str(url),
                    username=username,
                    password=password,
                    proxies=proxies,
                    verify=verify,
                    cert=cert,
                    organisation=organisation,
                )
            else:
                self.logger_file.error(
                    id="TH30",
                    message="THE_HIVE_AUTHENTICATION - Password AND API Key are null values",
                )
                exit(30)

            self.logger_file.debug(
                id="TH40",
                message="TheHive instance is initialized, try a request to {}".format(
                    url
                ),
            )

            # Try to connect to the API by getting information about the user used
            test = self.user.get_current()

            if "_id" not in test:
                self.logger_file.error(
                    id="TH45",
                    message="THE_HIVE_AUTHENTICATION_RESPONSE - Server didn't respond with a valid response.",
                )
                self.logger_file.debug(
                    id="TH46",
                    message="Payload content - Headers: " + str(self.session.headers),
                )
                self.logger_file.debug(
                    id="TH47",
                    message="Payload content - URL: " + str(self.session.hive_url),
                )
            elif apiKey is not None:
                self.logger_file.debug(
                    id="TH50",
                    message='TheHive API connection to (URL="'
                    + url
                    + '") is successful',
                )
            elif password is not None:
                self.logger_file.debug(
                    id="TH60",
                    message='TheHive API connection to (URL="'
                    + url
                    + '",Username="'
                    + username
                    + '") is successful',
                )

        except Exception as e:
            if "CERTIFICATE_VERIFY_FAILED" in str(e):
                self.logger_file.warn(
                    id="TH85",
                    message='THE_HIVE_CERTIFICATE_FAILED - It seems that the certificate verification failed. Please check that the certificate authority is added to "'
                    + str(certifi.where())
                    + '". Complete error: '
                    + str(e),
                )
                sys.exit(85)
            elif "HANDSHAKE_FAILURE" in str(e):
                self.logger_file.warn(
                    id="TH90",
                    message="THE_HIVE_HANDHSHAKE_FAILURE - It seems that the SSL handshake failed. A possible solution is to check if the remote server/proxy is not expecting a client certificate. Complete error: "
                    + str(e),
                )
                sys.exit(90)
            elif "Proxy Authentication Required" in str(e):
                self.logger_file.warn(
                    id="TH95",
                    message="THE_HIVE_PROXY_AUTHENTICATION_ERROR - It seems that the connection to the proxy has failed as it's required an authentication (none was provided or the username/password is not working). Proxy information are: "
                    + str(proxies)
                    + ". Complete error: "
                    + str(e),
                )
                sys.exit(95)
            elif "ProxyError" in str(e):
                self.logger_file.warn(
                    id="TH100",
                    message="THE_HIVE_PROXY_ERROR - It seems that the connection to the proxy has failed. Proxy information are: "
                    + str(proxies)
                    + ". Complete error: "
                    + str(e),
                )
                sys.exit(100)
            else:
                self.logger_file.error(
                    id="TH110",
                    message="THEHIVE_CONNECTION_ERROR - Error: "
                    + str(e)
                    + ". Check any error in the TheHive instance logs following this API REST call. If the error is persisting after several tries, please raise an issue to the application maintainer.",
                )
                sys.exit(110)

        self.__sid = sid

    @property
    def logger_file(self):
        return self._logger_file

    def get_alerts_events(
        self,
        filters: _FilterBase = None,
        sortby: SortExpr = None,
        **kwargs,
    ) -> list:
        """This is used to recover alerts from TheHive

        Args:
            filters (_FilterBase, optional): Filters to be used. Defaults to None.
            sortby (SortExpr, optional): Sort expression to be used for results. Defaults to None.

        Returns:
            list: List of events processed
        """
        self.logger_file.info(id="TH120", message="Retrieving alerts count...")
        count_events = self.alert.count(filters=filters)
        self.logger_file.info(
            id="TH121",
            message=f"Got {count_events} alerts. Estimated time for processing all events: less than {(count_events)*10} seconds",
        )
        processed_events = []

        final_sortby = sortby if sortby is not None else Asc(field="_createdAt")
        step = 100
        for i in range(0, count_events, step):
            if i + step < count_events:
                paginate = Paginate(
                    start=i, end=i + step, extra_data=kwargs["extra_data"]
                )
            else:
                paginate = Paginate(
                    start=i, end=count_events, extra_data=kwargs["extra_data"]
                )

            # Get alerts using the query
            raw_events = self.alert.find(
                filters=filters, sortby=final_sortby, paginate=paginate
            )

            # Store the events accordingly
            for event in raw_events:
                # Post processing before indexing
                ### Generic for all inputs
                event["_createdAt"] = event["_createdAt"] / 1000
                if "_updatedAt" in event and event["_updatedAt"] is not None:
                    event["_updatedAt"] = event["_updatedAt"] / 1000

                # Set the _time of the event to the created/updated time
                event["_time"] = int(event[kwargs["date"]])

                if "observables" in kwargs["additional_information"]:
                    ## OBSERVABLES ##
                    observables = []
                    ## ALERTS ##
                    observables = self.alert.get_alert_observables(
                        alert_id=event["_id"]
                    )
                    event["observables"] = observables
                    self.logger_file.debug(
                        id="TH122",
                        message="thehive - observables: " + str(event["observables"]),
                    )

                ## ATTACHMENTS ##
                if "attachments" in kwargs["additional_information"]:
                    ## ALERTS ##
                    attachments = self.alert.get_alert_attachments(
                        alert_id=event["_id"]
                    )
                    event["attachments"] = attachments
                    self.logger_file.debug(
                        id="TH123",
                        message="thehive - attachments: " + str(event["attachments"]),
                    )

                # Rework of the custom fields
                if "customFields" in event and len(event["customFields"]) > 0:
                    custom_fields = [cf["_id"] for cf in event["customFields"]]
                    new_custom_fields = []
                    for cf in custom_fields:
                        cf_split = cf.split(":", maxsplit=1)
                        if len(cf_split) > 1:
                            new_custom_fields.append({cf_split[0]: cf_split[1]})
                        elif len(cf_split) > 0:
                            new_custom_fields.append({cf_split[0]: None})
                    event["customFields"] = new_custom_fields

                # Remove underscore at the beginning
                for field in [
                    "_createdAt",
                    "_createdBy",
                    "_id",
                    "_time",
                    "_type",
                    "_updatedAt",
                    "_updatedBy",
                ]:
                    if field in event:
                        event[field.replace("_", "")] = event.pop(field)

                # Manage orig_* fields
                if "source" in event:
                    event["orig_source"] = event["source"]
                    del event["source"]

                # Sanitize the event from the configuration
                if "fields_removal" in kwargs and kwargs["fields_removal"] is not None:
                    event = self._utils.remove_unwanted_keys_from_dict(
                        d=event, l=kwargs["fields_removal"].split(",")
                    )
                if "max_size_value" in kwargs and kwargs["max_size_value"] is not None:
                    event = self._utils.check_and_reduce_values_size(
                        d=event, max_size=kwargs["max_size_value"]
                    )
                self.logger_file.debug(
                    id="TH125",
                    message=f"Event after processing (check_and_reduce_values_size): {event}",
                )

                processed_events.append(event)

            self.logger_file.info(
                id="TH126",
                message=f"{len(processed_events)} events have been processed...",
            )

        return processed_events

    def get_cases_events(
        self, filters: _FilterBase = None, sortby: SortExpr = None, **kwargs
    ) -> Tuple[list, list]:
        """This is used to recover cases from TheHive

        Args:
            filters (_FilterBase, optional): Filters to be used. Defaults to None.
            sortby (SortExpr, optional): Sort expression to be used for results. Defaults to None.

        Returns:
            list: List of events processed
        """
        self.logger_file.info(id="TH130", message="Retrieving cases count...")
        count_events = self.case.count(filters=filters)
        self.logger_file.info(
            id="TH131",
            message=f"Got {count_events} cases. Estimated time for processing all events: less than {(count_events)*8} seconds",
        )
        processed_events = []
        processed_tasks = []

        final_sortby = sortby if sortby is not None else Asc(field="_createdAt")
        step = 100
        for i in range(0, count_events, step):
            if i + step < count_events:
                paginate = Paginate(
                    start=i, end=i + step, extra_data=kwargs["extra_data"]
                )
            else:
                paginate = Paginate(
                    start=i, end=count_events, extra_data=kwargs["extra_data"]
                )

            # Get cases using the query
            raw_events = self.case.find(
                filters=filters, sortby=final_sortby, paginate=paginate
            )

            # Store the events accordingly
            for event in raw_events:
                # Post processing before indexing

                ## DATES ##
                event["startDate"] = event["startDate"] / 1000
                if "endDate" in event and event["endDate"] is not None:
                    event["endDate"] = event["endDate"] / 1000

                ### Generic for all inputs
                event["_createdAt"] = event["_createdAt"] / 1000
                if "_updatedAt" in event and event["_updatedAt"] is not None:
                    event["_updatedAt"] = event["_updatedAt"] / 1000

                # Set the _time of the event to the created/updated time
                event["_time"] = int(event[kwargs["date"]])

                if "observables" in kwargs["additional_information"]:
                    ## OBSERVABLES ##
                    observables = []
                    ## CASES ##
                    observables = self.case.get_case_observables(case_id=event["_id"])
                    event["observables"] = observables
                    self.logger_file.debug(
                        id="TH133",
                        message="thehive - observables: "
                        + str(len(event["observables"])),
                    )

                ## ATTACHMENTS ##
                if "attachments" in kwargs["additional_information"]:
                    ## CASES ##
                    attachments = self.case.get_case_attachments(case_id=event["_id"])
                    event["attachments"] = attachments
                    self.logger_file.debug(
                        id="TH134",
                        message="thehive - attachments: "
                        + str(len(event["attachments"])),
                    )

                ## PAGES ##
                if "pages" in kwargs["additional_information"]:
                    ## CASES ##
                    pages = self.case.get_case_pages(case_id=event["_id"])
                    event["pages"] = pages
                    self.logger_file.debug(
                        id="TH135",
                        message="thehive - pages: " + str(len(event["pages"])),
                    )

                ## TTPS ##
                if "ttps" in kwargs["additional_information"]:
                    ## CASES ##
                    paginate = Paginate(start=0, end=100)
                    ttps = self.case.find_procedures(event["_id"], paginate=paginate)
                    event["ttps"] = ttps
                    self.logger_file.debug(
                        id="TH136", message="thehive - ttps: " + str(len(event["ttps"]))
                    )

                # Rework of the custom fields
                if "customFields" in event and len(event["customFields"]) > 0:
                    custom_fields = [cf["_id"] for cf in event["customFields"]]
                    new_custom_fields = []
                    for cf in custom_fields:
                        cf_split = cf.split(":", maxsplit=1)
                        if len(cf_split) > 1:
                            new_custom_fields.append({cf_split[0]: cf_split[1]})
                        elif len(cf_split) > 0:
                            new_custom_fields.append({cf_split[0]: None})
                    event["customFields"] = new_custom_fields

                # Remove underscore at the beginning
                for field in [
                    "_createdAt",
                    "_createdBy",
                    "_id",
                    "_time",
                    "_type",
                    "_updatedAt",
                    "_updatedBy",
                ]:
                    if field in event:
                        event[field.replace("_", "")] = event.pop(field)

                # Manage orig_* fields
                if "source" in event:
                    event["orig_source"] = event["source"]
                    del event["source"]

                # Sanitize the event from the configuration
                if "fields_removal" in kwargs and kwargs["fields_removal"] is not None:
                    event = self._utils.remove_unwanted_keys_from_dict(
                        d=event, l=kwargs["fields_removal"].split(",")
                    )
                if "max_size_value" in kwargs and kwargs["max_size_value"] is not None:
                    event = self._utils.check_and_reduce_values_size(
                        d=event, max_size=kwargs["max_size_value"]
                    )
                self.logger_file.debug(
                    id="TH137",
                    message=f"Event after processing (check_and_reduce_values_size): {event}",
                )

                processed_events.append(event)

            self.logger_file.info(
                id="TH138",
                message=f"{len(processed_events)} events have been processed...",
            )

        if "tasks" in kwargs["additional_information"]:
            ## TASKS ##
            tasks = []
            tasks = self.task.get_tasks(filters=filters)
            for task in tasks:
                event = task
                # Remove underscore at the beginning
                for field in [
                    "_createdAt",
                    "_createdBy",
                    "_id",
                    "_time",
                    "_type",
                    "_updatedAt",
                    "_updatedBy",
                ]:
                    if field in event:
                        event[field.replace("_", "")] = event.pop(field)

                # Sanitize the event from the configuration
                if "fields_removal" in kwargs and kwargs["fields_removal"] is not None:
                    event = self._utils.remove_unwanted_keys_from_dict(
                        d=event, l=kwargs["fields_removal"].split(",")
                    )
                if "max_size_value" in kwargs and kwargs["max_size_value"] is not None:
                    event = self._utils.check_and_reduce_values_size(
                        d=event, max_size=kwargs["max_size_value"]
                    )
                self.logger_file.debug(
                    id="TH139",
                    message=f"Event after processing (check_and_reduce_values_size): {event}",
                )

                processed_tasks.append(event)
            self.logger_file.debug(
                id="TH140", message="TheHive - Tasks: " + str(len(processed_tasks))
            )

        return (processed_events, processed_tasks)

    def get_observables_events(
        self, filters: _FilterBase = None, sortby: SortExpr = None, **kwargs
    ) -> list:
        """This is used to get observables from TheHive

        Args:
            filters (_FilterBase): Filters to be used. Defaults to None.
            sortby (SortExpr, optional): Sort expression to be used for results. Defaults to None.

        Returns:
            list: List of events processed
        """
        self.logger_file.info(id="TH140", message="Retrieving observables count...")
        count_events = self.observable.count(filters=filters)
        self.logger_file.info(
            id="TH141",
            message=f"Got {count_events} observables. Estimated time for processing all events: less than {((int(count_events/100))+1)*14} seconds",
        )
        processed_events = []

        final_sortby = sortby if sortby is not None else Asc(field="_createdAt")
        step = 100
        for i in range(0, count_events, step):
            if i + step < count_events:
                paginate = Paginate(start=i, end=i + step)
            else:
                paginate = Paginate(start=i, end=count_events)

            raw_events = self.observable.find(
                filters=filters, sortby=final_sortby, paginate=paginate
            )

            # Store the events accordingly
            for event in raw_events:
                # Post processing before indexing

                ### Generic for all inputs
                event["_createdAt"] = event["_createdAt"] / 1000
                if "_updatedAt" in event and event["_updatedAt"] is not None:
                    event["_updatedAt"] = event["_updatedAt"] / 1000

                # Set the _time of the event to the created/updated time
                event["_time"] = int(event[kwargs["date"]])

                # Remove underscore at the beginning
                for field in [
                    "_createdAt",
                    "_createdBy",
                    "_id",
                    "_time",
                    "_type",
                    "_updatedAt",
                    "_updatedBy",
                ]:
                    if field in event:
                        event[field.replace("_", "")] = event.pop(field)

                # Manage orig_* fields
                if "source" in event:
                    event["orig_source"] = event["source"]
                    del event["source"]

                # Sanitize the event from the configuration
                event = self._utils.remove_unwanted_keys_from_dict(
                    d=event, l=kwargs["fields_removal"].split(",")
                )
                event = self._utils.check_and_reduce_values_size(
                    d=event, max_size=int(kwargs["max_size_value"])
                )
                self.logger_file.debug(
                    id="TH145",
                    message=f"Event after processing (check_and_reduce_values_size): {event}",
                )
                processed_events.append(event)

            self.logger_file.info(
                id="TH146",
                message=f"{len(processed_events)} events have been processed...",
            )

        return processed_events

    def get_audit_logs_events(
        self, filters: _FilterBase = None, sortby: SortExpr = None, **kwargs
    ) -> list:
        """This is used to get audit logs from TheHive

        Args:
            filters (_FilterBase): Filters to be used. Defaults to None.
            sortby (SortExpr, optional): Sort expression to be used for results. Defaults to None.

        Returns:
            list: List of events processed
        """
        self.logger_file.info(id="TH170", message="Retrieving audit logs count...")
        count_events = self.organisation.count_audit_logs(filters=filters)
        self.logger_file.info(
            id="TH171",
            message=f"Got {count_events} audit logs. Estimated time for processing all events: less than {((int(count_events/100))+1)*14} seconds",
        )
        processed_events = []

        final_sortby = sortby if sortby is not None else Asc(field="_createdAt")
        step = 100
        for i in range(0, count_events, step):
            if i + step < count_events:
                paginate = Paginate(start=i, end=i + step)
            else:
                paginate = Paginate(start=i, end=count_events)

            raw_events = self.organisation.get_audit_logs(
                filters=filters, sortby=final_sortby, paginate=paginate
            )

            # Store the events accordingly
            for event in raw_events:
                # Post processing before indexing

                ### Generic for all inputs
                event["_createdAt"] = event["_createdAt"] / 1000
                if "_updatedAt" in event and event["_updatedAt"] is not None:
                    event["_updatedAt"] = event["_updatedAt"] / 1000

                # Set the _time of the event to the created/updated time
                event["_time"] = int(event["_createdAt"])

                # Remove underscore at the beginning
                for field in [
                    "_createdAt",
                    "_createdBy",
                    "_id",
                    "_time",
                    "_type",
                    "_updatedAt",
                    "_updatedBy",
                ]:
                    if field in event:
                        event[field.replace("_", "")] = event.pop(field)

                # Manage orig_* fields
                if "source" in event:
                    event["orig_source"] = event["source"]
                    del event["source"]

                # Sanitize the event from the configuration
                if "fields_removal" in kwargs and kwargs["fields_removal"] is not None:
                    event = self._utils.remove_unwanted_keys_from_dict(
                        d=event, l=kwargs["fields_removal"].split(",")
                    )
                if "max_size_value" in kwargs and kwargs["max_size_value"] is not None:
                    event = self._utils.check_and_reduce_values_size(
                        d=event, max_size=kwargs["max_size_value"]
                    )
                self.logger_file.debug(
                    id="TH175",
                    message=f"Event after processing (check_and_reduce_values_size): {event}",
                )
                processed_events.append(event)

            self.logger_file.info(
                id="TH176",
                message=f"{len(processed_events)} events have been processed...",
            )

        return processed_events
