# encoding = utf-8
#
# Copyright: LGPLv3 (https://www.gnu.org/licenses/lgpl-3.0.txt)
#
"""Timeline events on a TheHive case: read them back, and add a custom one.

⚠️ Split out of `thehive.TheHive4Splunk` (project-management#24) the day that
class crossed its own line ceiling: these two methods are the whole surface
this add-on has for a case's timeline, and neither shares logic with the
`get_*_events` family that fetches alerts/cases/observables/audit logs/tasks
directly off TheHive's search endpoints -- timeline events are read by walking
cases page by page and calling `case.get_timeline()` on each one, which is its
own shape of pagination and its own failure modes.

Mixed into `TheHive4Splunk` rather than instantiated on its own: both methods
read `self.case`, `self.timeline`, `self.logger_file` and `self._utils`, which
only exist once `TheHiveApi.__init__` (and `TheHive4Splunk.__init__` after it)
has run.
"""

import ta_thehive_cortex_declare

import time

from thehive4py.query.filters import _FilterBase
from thehive4py.query.page import Paginate
from thehive4py.query.sort import SortExpr


class TimelineEventsMixin:
    """`get_case_timeline_events` and `create_custom_timeline_event`, together."""

    def get_case_timeline_events(
        self, filters: _FilterBase = None, sortby: SortExpr = None, **kwargs
    ) -> list:
        """This is used to recover timeline events from cases in TheHive

        Args:
            filters (_FilterBase, optional): Filters to be used for case discovery. Defaults to None.
            sortby (SortExpr, optional): Sort expression for case discovery. Defaults to None.

        Returns:
            list: List of timeline events processed
        """
        self.logger_file.info(id="TH180", message="Retrieving cases for timeline extraction...")

        # We fetch cases updated in the interval to discover potential new timeline events
        count_cases = self.case.count(filters=filters)
        self.logger_file.info(
            id="TH181",
            message=f"Got {count_cases} cases to check for timeline events.",
        )

        processed_timeline_events = []

        # Determine time interval from filters
        t_start = 0
        t_end = 9999999999999 # Far future

        if "_between" in filters:
            t_start = filters["_between"]["_from"]
            t_end = filters["_between"]["_to"]

        event_kinds = kwargs.get("timeline_event_kinds", [])
        if isinstance(event_kinds, str) and event_kinds:
            event_kinds = [k.strip() for k in event_kinds.split(",") if k.strip()]
        elif isinstance(event_kinds, list):
            event_kinds = [k for k in event_kinds if k]
        else:
            event_kinds = []

        max_events = int(kwargs.get("max_events_per_case", 0))

        step = 100
        for i in range(0, count_cases, step):
            paginate = Paginate(start=i, end=min(i + step, count_cases))
            cases = self.case.find(filters=filters, sortby=sortby, paginate=paginate)

            for case in cases:
                case_id = case.get("_id")
                case_number = case.get("number")

                self.logger_file.debug(id="TH182", message=f"Fetching timeline for case {case_number} ({case_id})")

                # Fetch full timeline for the case
                try:
                    timeline = self.case.get_timeline(case_id)
                except Exception as e:
                    self.logger_file.error(id="TH183", message=f"Failed to fetch timeline for case {case_id}: {str(e)}")
                    continue

                case_events = []
                # The response is a dict containing a list of events
                timeline_entries = timeline.get("events", []) if isinstance(timeline, dict) else timeline
                for entry in timeline_entries:
                    # entries in timeline are objects from thehive4py
                    event = dict(entry) if not isinstance(entry, dict) else entry.copy()

                    event_date = event.get("date", 0)
                    event_kind = event.get("kind")

                    # 1. Filter by kind if specified
                    if event_kinds and event_kind not in event_kinds:
                        self.logger_file.debug(id="TH186", message=f"Skipping timeline event {event.get('id', event.get('_id'))} because kind {event_kind} is not in {event_kinds}")
                        continue

                    # Enrichment
                    event["case_id"] = case_id
                    event["case_number"] = case_number

                    # Normalization
                    event["_time"] = int(time.time())

                    case_events.append(event)

                # 3. Apply max_events_per_case (most recent first)
                if max_events > 0:
                    case_events.sort(key=lambda x: x.get("date", 0), reverse=True)
                    case_events = case_events[:max_events]

                # Post-processing for each event
                for event in case_events:
                    # Remove underscore at the beginning for standard fields
                    for field in ["_id", "_type", "_createdAt", "_createdBy", "_updatedAt", "_updatedBy"]:
                        if field in event:
                            event[field.replace("_", "")] = event.pop(field)

                    # Handle size and removal
                    if "fields_removal" in kwargs and kwargs["fields_removal"]:
                        event = self._utils.remove_unwanted_keys_from_dict(
                            d=event, l=kwargs["fields_removal"].split(",")
                        )
                    if "max_size_value" in kwargs and kwargs["max_size_value"]:
                        event = self._utils.check_and_reduce_values_size(
                            d=event, max_size=int(kwargs["max_size_value"])
                        )

                    processed_timeline_events.append(event)

            self.logger_file.info(
                id="TH184",
                message=f"Processed timeline events for {len(processed_timeline_events)} entries so far...",
            )

        return processed_timeline_events

    def create_custom_timeline_event(
        self,
        case_id: str,
        title: str,
        description: str = None,
        date: int = None,
        endDate: int = None,
    ) -> dict:
        """This is used to create a custom timeline event in a TheHive case

        Args:
            case_id (str): The ID of the case where the event will be created
            title (str): The title of the event
            description (str, optional): The description of the event. Defaults to None.
            date (int, optional): The date of the event (ms). Defaults to None.
            endDate (int, optional): The end date of the event (ms). Defaults to None.

        Returns:
            dict: The created custom event
        """
        self.logger_file.info(
            id="TH200", message=f"Creating custom timeline event for case {case_id}..."
        )

        event = {"title": title}
        if description:
            event["description"] = description
        if date:
            event["date"] = date
        else:
            event["date"] = int(time.time() * 1000)
        if endDate:
            event["endDate"] = endDate

        try:
            created_event = self.timeline.create_event(case_id, event)
            self.logger_file.info(
                id="TH201",
                message=f"Custom timeline event created successfully for case {case_id}",
            )
            return created_event
        except Exception as e:
            self.logger_file.error(
                id="TH202",
                message=f"FAILED_TO_CREATE_TIMELINE_EVENT - Error: {str(e)}",
            )
            raise e
