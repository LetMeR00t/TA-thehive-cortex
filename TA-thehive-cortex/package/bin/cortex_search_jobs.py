# encoding = utf-8
# Author: Alexandre Demeyer <letmer00t@gmail.com>
#
# Copyright: LGPLv3 (https://www.gnu.org/licenses/lgpl-3.0.txt)
# Feel free to use the code, but please share the changes you've made

__author__ = "Alexandre Demeyer"
__license__ = "LGPLv3"
__version__ = "4.0.0"
__maintainer__ = "Alexandre Demeyer"
__email__ = "letmer00t@gmail.com"

import ta_thehive_cortex_declare

# Standard library imports
from copy import deepcopy

# Third-party imports
import splunk.Intersplunk
from cortex4py.query import And, Eq, In

# Local application/library specific imports
from cortex import initialize_cortex_instance
import globals

# Global parameters
FILTER_DATA_DEFAULT = ""
FILTER_DATATYPES_DEFAULT = "*"
FILTER_ANALYZERS_DEFAULT = "*"
MAX_JOBS = None
SORT_JOBS = None

# The statuses at which a job has nothing more to say. Anything else means the
# analyzer is still working, and its report is not a result yet.
# ⚠️ "Deleted" belongs here: it is final, even though no report will follow.
JOB_FINISHED_STATUSES = ("Success", "Failure", "Deleted")


def collect_job(cortex, job, wait, logger_file):
    """Build the Splunk event for ONE Cortex job: wait, distinguish, harvest.

    Lives outside `__main__` so it can be exercised against stubbed Cortex
    responses -- the previous shape ran only inside a Splunk process, which is
    why none of the three defects it repairs was ever caught by a test."""

    logger_file.debug(id="15", message="Job details: " + str(job))

    status = getattr(job, "status", None)

    # ⚠️ Asking for the report of a job that is still running returns an EMPTY
    # one, and an empty report is indistinguishable from an analyzer that found
    # nothing. Cortex can hold the answer instead: `waitreport?atMost=` blocks
    # server-side, which is one call rather than a polling loop. `wait = 0`
    # keeps the behaviour every previous version had.
    if wait > 0 and status not in JOB_FINISHED_STATUSES:
        logger_file.info(id="31", message="Job \"" + str(job.id) + "\" is " + str(status) + ", asking Cortex to hold its report for at most " + str(wait) + "s")
        report = cortex.jobs.get_report_async(job.id, timeout=str(wait) + "seconds")
    else:
        report = cortex.jobs.get_report(job.id)

    logger_file.debug(id="16", message="Report details: \"" + str(job.id) + "\": " + str(report))

    job_report = {"cortex_job_" + k: v for k, v in vars(report).items() if not k.startswith('_')}
    event = {"cortex_job_" + k: v for k, v in vars(job).items() if not k.startswith('_')}

    # The report carries the status as of the moment it was read, which is
    # later than the one the search returned -- and, when we waited, that
    # difference is the whole point.
    status = job_report.get("cortex_job_status") or status
    event["cortex_job_status"] = status

    # ⚠️ Explicit, and never inferred from an empty report: "not finished yet"
    # and "found nothing" are two different facts that used to produce the very
    # same line.
    finished = status in JOB_FINISHED_STATUSES
    event["cortex_job_finished"] = 1 if finished else 0

    logger_file.debug(id="20", message="Event before post processing: " + str(event))

    # Post processing for Splunk
    ## REPORT ##
    if not finished:
        # No report field at all rather than an empty one: a field that is
        # absent cannot be mistaken for an analyzer's empty answer.
        logger_file.info(id="32", message="Job \"" + str(job.id) + "\" is still " + str(status) + ", no report is reported for it")
        return event

    keys = []
    report_content = job_report.get("cortex_job_report") or {}
    for k in report_content:
        keys.append(k + "::" + str(report_content[k]))
    event["cortex_job_report"] = keys

    ## ARTIFACTS ##
    # The observables the analyzer EXTRACTED -- the enrichment Cortex produces.
    # cortex4py has always been able to fetch them (`job/{id}/artifacts`);
    # nothing in this add-on ever called it, so that enrichment never came back
    # to Splunk. Only a job that succeeded can have any.
    if status == "Success":
        try:
            artifacts = cortex.jobs.get_artifacts(job.id)
        except Exception as e:
            # ⚠️ A report that arrived is not thrown away because the artifacts
            # did not: they are two separate calls, and the line says which one
            # is missing.
            logger_file.warn(id="33", message="ARTIFACTS_UNREACHABLE - artifacts of job \"" + str(job.id) + "\" could not be read: " + str(e))
            artifacts = None
        if artifacts is not None:
            event["cortex_job_artifacts"] = [
                str(getattr(a, "dataType", "")) + "::" + str(getattr(a, "data", ""))
                for a in artifacts
            ]
            event["cortex_job_artifacts_count"] = len(artifacts)

    ## DATES ##
    if "cortex_job_startDate" in event:
        event["cortex_job_startDate"] = event["cortex_job_startDate"] / 1000
    if "cortex_job_endDate" in event:
        event["cortex_job_endDate"] = event["cortex_job_endDate"] / 1000
    if "cortex_job_createdAt" in event:
        event["cortex_job_createdAt"] = event["cortex_job_createdAt"] / 1000
    if "cortex_job_updatedAt" in event:
        event["cortex_job_updatedAt"] = event["cortex_job_updatedAt"] / 1000

    logger_file.debug(id="25", message="Event after post processing: " + str(event))

    return event

if __name__ == '__main__':
    
    globals.initialize_globals()

    # First, parse the arguments
    # get the keywords and options passed to this command
    keywords, options = splunk.Intersplunk.getKeywordsAndOptions()

    # get the previous search results
    results,dummyresults,settings = splunk.Intersplunk.getOrganizedResults()

    # Initialize this script and return a cortex instance object, a configuration object and defaults values
    (cortex, configuration, defaults, logger_file) = initialize_cortex_instance(keywords, settings, acronym="CSJ", logger_name="cortex_search_jobs")

    logger_file.debug(id="1",message="Input keywords: "+str(keywords))
    logger_file.debug(id="2",message="Input results: "+str(results))

    outputResults = []
    # Prepare and get all jobs queries 
    for result in results:
        ## FILTERS ##
        # Check the results to extract interesting fields
        filterData = configuration.checkAndValidate(result, "data", default=FILTER_DATA_DEFAULT, is_mandatory=False)
        filterDatatypes = configuration.checkAndValidate(result, "datatypes", default=FILTER_DATATYPES_DEFAULT, is_mandatory=False)
        filterAnalyzers = configuration.checkAndValidate(result, "analyzers", default=FILTER_ANALYZERS_DEFAULT, is_mandatory=False)
        maxJobs = configuration.checkAndValidate(result, "max_jobs", default=defaults["MAX_JOBS_DEFAULT"], is_mandatory=False)
        sortJobs = configuration.checkAndValidate(result, "sort_jobs", default=defaults["SORT_JOBS_DEFAULT"], is_mandatory=False)
        waitJob = configuration.checkAndValidate(result, "wait", default=defaults["JOB_MAX_WAIT_DEFAULT"], is_mandatory=False)
        try:
            waitJob = int(waitJob)
        except (TypeError, ValueError):
            # ⚠️ A malformed value must not decide to block: falling back to 0
            # keeps the previous behaviour, and says so.
            logger_file.warn(id="30", message="WAIT_NOT_A_NUMBER - wait=\"" + str(waitJob) + "\" is not a number of seconds, not waiting for running jobs")
            waitJob = 0

        # create the query from filters
        query = {}
        elements = []
        if filterData != FILTER_DATA_DEFAULT:
            element = Eq("data",filterData)
            elements.append(element)
        if filterDatatypes != FILTER_DATATYPES_DEFAULT:
            element = In("dataType",filterDatatypes.replace(" ","").split(";"))
            elements.append(element)
        if filterAnalyzers != FILTER_ANALYZERS_DEFAULT:
            element = In("workerDefinitionId",filterAnalyzers.replace(" ","").split(";"))
            elements.append(element)

        if len(elements)>1:
            query = And(*elements)
        elif len(elements)==1:
            query = elements[0]
        logger_file.info(id="10",message="Query is: "+str(query))
    
        ## JOBS ##
        jobs = cortex.jobs.find_all(query ,range='0-'+maxJobs, sort=sortJobs)

        for job in jobs:
             result_copy = deepcopy(result)
             result_copy.update(collect_job(cortex, job, waitJob, logger_file))
             outputResults.append(deepcopy(result_copy))

    splunk.Intersplunk.outputResults(outputResults)
