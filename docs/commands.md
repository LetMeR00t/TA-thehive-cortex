
# Commands
This application allows you to use new commands related to TheHive/Cortex.

## thehivecases

This command is used to get cases from TheHive (\$..\$ are tokens examples but you can use it directly in your searches).


	| makeresults
	| eval keyword = "$filter_keyword$", status = "$filter_status$", severity = "$filter_severity$", tags = "$filter_tags$", title = "$filter_title$", assignee = "$filter_assignee$", date = "$filter_date_d1$ TO $filter_date_d2$", max_cases="$max_cases$", sort_cases="$sort_cases$"
	| thehivecases



### Parameters (input results)
One row will result in executing the script one time. So if you specify 5 rows, the script will be executed 5 times and all results will be appended.
If not set, no filter will be applied.

* (Optional) **keyword**: Filter on a specific keyword (Default: *)
* (Optional) **status**: Filter on a specific status (separated by ";") (Default: *)
* (Optional) **severity**: Filter on a specific severity (separated by ";") (Default: *)
* (Optional) **tags**: Filter on a specific tags (separated by ";") (Default: *)
* (Optional) **title**: Filter on a specific title (Default: *)
* (Optional) **assignee**: Filter on a specific assignee (separated by ";") (Default: *)
* (Optional) **date**: Filter on a specific date using the format "\$date1\$ TO \$date2\$" (Default: *)
* (Optional) **max_cases**: The maximum number of cases to return (Default: 100 or your own default)
* (Optional) **sort_cases**: The way how your cases are sorted (Default: "-startDate" or your own default)

**Note**: These parameters are the **expected fields name**.

### Return
This command append new fields per row to previous results.
Every new field will start with "cortex_*". As an exemple, you can recover:

 - thehive_case_caseId
 - thehive_case_createdAt
 - thehive_case_createdBy
 - thehive_case_customFields
 - thehive_case_description
 - thehive_case_endDate
 - thehive_case_flag
 - thehive_case_id
 - thehive_case_impactStatus
 - thehive_case_metrics
 - thehive_case_observables
 - thehive_case_owner
 - thehive_case_pap
 - thehive_case_resolutionStatus
 - thehive_case_severity
 - thehive_case_startDate
 - thehive_case_status
 - thehive_case_summary
 - thehive_case_tags
 - thehive_case_tasks

### Examples

	| makeresults count=1
	| thehivecases
	# This will recover any case
	
	| makeresults count=1
	| eval keyword = "github.com" 
	| thehivecases
	# This will recover any case concerning the keyword "github.com"
	
	| makeresults count=1
	| eval status = "Open"
	| thehivecases
	# This will recover any "Open" case
		 
	| makeresults count=1
	| eval status = "Open;Resolved"
	| thehivecases
	# This will recover any "Open" or "Resolved" case

## thehivecreate
This command is used to create a new case to TheHive (\$..\$ are tokens examples but you can use it directly in your searches).

	| makeresults
	| eval title="$create_title$", severity = "$create_severity$", tags="$create_tags$", pap = "$create_pap$", date = now(), tlp = "$create_tlp$", description="$create_description$", tasks = "$create_tasks$"
	| thehivecreate

### Parameters (input results)

One row will result in executing the script one time. So if you specify 5 rows, the script will be executed 5 times and all results will be appended.

* (Mandatory) **title**: Specify the title of the new case
* (Optional) **severity**: Specify the severity of the new case (1=LOW,2=MEDIUM,3=HIGH,4=CRITICAL) (Default: 2)
* (Optional) **tags**: Specify the tags of the new case (Default: None)
* (Optional) **pap**: PAP to use for analysis (0=WHITE,1=GREEN,2=AMBER,3=RED) (Default: 2)
* (Optional) **date**: Specify the date of the new case (Default: the current date/time)
* (Optional) **tlp**: TLP to use for analysis (0=WHITE,1=GREEN,2=AMBER,3=RED) (Default: 2)
* (Mandatory) **description**: Specify the description of the new case
* (Optional) **tasks**: Specify the tasks of the new case (Default: None)

**Note**: These parameters are the **expected fields name**.

### Return

This command append new fields per row to previous results.
Every new field will start with "thehive_*". As an exemple, you can recover:

 - thehive_case_caseId
 - thehive_case_createdAt
 - thehive_case_createdBy
 - thehive_case_customFields
 - thehive_case_description
 - thehive_case_endDate
 - thehive_case_flag
 - thehive_case_id
 - thehive_case_impactStatus
 - thehive_case_metrics
 - thehive_case_observables
 - thehive_case_owner
 - thehive_case_pap
 - thehive_case_resolutionStatus
 - thehive_case_severity
 - thehive_case_startDate
 - thehive_case_status
 - thehive_case_summary
 - thehive_case_tags
 - thehive_case_tasks


### Examples


	| makeresults
	| eval title="Test", description="Test 2"
	| thehivecases
	# This will create a new case with the title "Test" and the description set to "Test 2"

	| makeresults
	| eval title="Critical case", severity = "4", tags="important;emergency", pap = "4", date = now(), description="Very important case"
	| thehivecases
	# This will creater a new case with the title "Critical case", with a CRITICAL severity, with tags set to "important" and "emergency", with a PAP set to RED, with a description set to "Very important case"


## cortexjobs

This command is used to get jobs from Cortex (\$..\$ are tokens examples but you can use it directly in your searches).


	| makeresults
	| eval data = "$filter_data$", datatypes = "$filter_datatypes$", analyzers = "$filter_analyzers$", max_jobs="$max_jobs$", sort_jobs="$sort_jobs$"
	| cortexjobs

### Parameters (input results)
One row will result in executing the script one time. So if you specify 5 rows, the script will be executed 5 times and all results will be appended.
If not set, no filter will be applied on the jobs history.

* (Optional) **data**: Specify an exact match string for the data (Default: *)
* (Optional) **datatypes**: A list of data types to search for separated by a semicolon (Default: *)
* (Optional) **analyzers**: A list of analyzers name to search for separated by a semicolon (Default: *)
* (Optional) **max_jobs**: The maximum number of jobs to return (Default: 100 or your own default)
* (Optional) **sort_jobs**: The way how your jobs are sorted (Default: "-createdAt" or your own default)

**Note**: These parameters are the **expected fields name**.

### Return
This command append new fields per row to previous results.
Every new field will start with "cortex_*". As an exemple, you can recover:

 - cortex_job_analyzerDefinitionId
 - cortex_job_analyzerId
 - cortex_job_analyzerName
 - cortex_job_cacheTag
 - cortex_job_createdAt
 - cortex_job_createdBy
 - cortex_job_data
 - cortex_job_dataType
 - cortex_job_date
 - cortex_job_id
 - cortex_job_message
 - cortex_job_organization
 - cortex_job_pap
 - cortex_job_parameters
 - cortex_job_status
 - cortex_job_tlp
 - cortex_job_type
 - cortex_job_workerDefinitionId
 - cortex_job_workerId
 - cortex_job_workerName

### Examples

	| makeresults count=1
	| cortexjobs
	# This will recover any job
	
	| makeresults count=1
	| eval data = "github.com" 
	| cortexjobs
	# This will recover any job concerning the exact match "github.com" as data
	
	| makeresults count=1
	| eval datatypes = "ip"
	| cortexjobs
	# This will recover any job based on an "ip" data type
		 
	| makeresults count=1
	| eval datatypes = "ip;domain"
	| cortexjobs
	# This will recover any job based on an "ip" or "domain" data type
		
	| makeresults count=1
	| eval analyzers = "Abuse_Finder_3_0 ;GoogleDNS_resolve_1_0_0" 
	| cortexjobs
	# This will recover any job based on the "Abuse_Finder_3_0" or "GoogleDNS_resolve_1_0_0" analyzers

## cortexrun
This command is used to run new jobs to Cortex (\$..\$ are tokens examples but you can use it directly in your searches).

	| makeresults
	| eval data = "$data$", dataType = "$dataType$", tlp = "$tlp$", pap = "$pap$", analyzers = "$analyzers$"
	| cortexjobs

### Parameters (input results)

One row will result in executing the script one time. So if you specify 5 rows, the script will be executed 5 times and all results will be appended.

* (Mandatory) **data**: Specify the data to analyze (separated by ";" for the same datatype)
* (Mandatory) **dataType**: Specify the datatype to analyze 
* (Optional) **analyzers**: A list of analyzers name to search for separated by a semicolon (Default: *)
* (Optional) **tlp**: TLP to use for analysis (0=WHITE,1=GREEN,2=AMBER,3=RED) (Default: 2)
* (Optional) **pap**: PAP to use for analysis (0=WHITE,1=GREEN,2=AMBER,3=RED) (Default: 2)

**Note**: These parameters are the **expected fields name**.

### Return

This command append new fields per row to previous results.
Every new field will start with "cortex_*". As an exemple, you can recover:

 - cortex_job_analyzerDefinitionId
 - cortex_job_analyzerId
 - cortex_job_analyzerName
 - cortex_job_cacheTag
 - cortex_job_createdAt
 - cortex_job_createdBy
 - cortex_job_data
 - cortex_job_dataType
 - cortex_job_date
 - cortex_job_id
 - cortex_job_message
 - cortex_job_organization
 - cortex_job_pap
 - cortex_job_parameters
 - cortex_job_status
 - cortex_job_tlp
 - cortex_job_type
 - cortex_job_workerDefinitionId
 - cortex_job_workerId
 - cortex_job_workerName


### Examples


	| makeresults
	| eval data = "8.8.8.8", dataType = "ip"
	| cortexrun
	# This will start as many jobs as there is available analyzers for the data type "ip" with TLP and PAP level set to AMBER (default)

	| makeresults
	| eval data = "8.8.8.8;8.8.4.4", dataType = "ip", analyzers = "GoogleDNS_resolve_1_0_0;Abuse_Finder_3_0"
	| cortexrun
	# This will start four jobs (two data and two analyzers) with TLP and PAP level set to AMBER (default)
	 
	| makeresults
	| eval data = "8.8.8.8;8.8.4.4", dataType = "ip", tlp = "GREEN", pap = "WHITE", analyzers = "GoogleDNS_resolve_1_0_0 ;Abuse_Finder_3_0"
	| cortexrun
	# This will start four jobs (two data and two analyzers) with TLP and PAP level set respectively to GREEN and WHITE

