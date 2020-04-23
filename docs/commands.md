# Commands
This application allows you to use new commands related to cortex.

## cortexjobs

This command is used to get jobs from Cortex.

	| cortexjobs (<filter_data> <filter_datatypes> <filter_analyzers>)

### Parameters
All parameters are optional. If not set, no filter will be applied on the jobs history.

* **filter_data**: Specify an exact match string for the data (Default: *)
* **filter_datatypes**: A list of data types to search for separated by a semicolon (Default: *)
* **filter_analyzers**: A list of analyzers name to search for separated by a semicolon (Default: *)

**Note**: These parameters aren't fields name, it's directly a string parameter.

### Return
This command append new fields/rows to previous results.

* **id**: ID of the job
* **data**: data used for the job
* **analyzer**: analyzer of the job
* **createdAt**: timestamp of the job creation
* **createdBy**: user/organization used of the job
* **tlp**: TLP level (integer) of the job
* **status**: status of the job
* **summary**: summary of the job results
* **startDate**: timestamp of the job start date
* **endDate**: timestamp of the job end date


### Examples

	| cortexjobs
	# This will recover any job
	 
	| cortexjobs "github.com"
	# This will recover any job concerning the exact match "github.com" as data
	
	| cortexjobs "*" "ip" "*"
	# This will recover any job based on an "ip" data type
		 
	| cortexjobs "*" "ip;domain"
	# This will recover any job based on an "ip" or "domain" data type
		 
	| cortexjobs "" "*" "Abuse_Finder_3_0 ;GoogleDNS_resolve_1_0_0"
	# This will recover any job based on the "Abuse_Finder_3_0" or "GoogleDNS_resolve_1_0_0" analyzers

## cortexrun
This command is used to run new jobs to Cortex.

	| cortexrun data dataType (tlp pap analyzers)

### Parameters
**This command is expecting exact fields name**.
"data" and "dataType" fields are required. Other parameters are optional. If not set, default values will be used.

* **data**: this field contains the data to analyze.
* **dataType**: this field contains the data type of the data. Unique value is expected
* **tlp**: this field contains the TLP level (upper string or integer) to use (Default: 2 - AMBER)
* **pap**: this field contains the PAP level (upper string or integer) to use (Default: 2 - AMBER)
* **analyzers**: this field contains a list of analyzers to use separated by a semicolon. If not set, all available analyzers for the given data type will be used (Default: Any analyzer for the data type)

**Note**: These parameters are fields name, you can't pass strings directly as parameters

### Return
This command append new fields/rows to previous results. For each row, a new field will be added with the result of the command

* **cortex**: this field is a multi-value fields (one line = one data with one analyzer) that contains a key-value string separated by "::" such as :
	* **id**: id of the created job
	* **analyzer**: analyzer used for the given job id
	* **status**: status for the given data/analyzer


### Examples


	| makeresults
	| eval data = "8.8.8.8", dataType = "ip"
	| cortexrun data dataType
	# This will start as many jobs as there is available analyzers for the data type "ip" with TLP and PAP level set to AMBER (default)

	| makeresults
	| eval data = "8.8.8.8;8.8.4.4", dataType = "ip", analyzers = "GoogleDNS_resolve_1_0_0 ;Abuse_Finder_3_0"
	| makemv delim=";" data
	| mvexpand data
	| cortexrun data dataType analyzers
	# This will start four jobs (two data and two analyzers) with TLP and PAP level set to AMBER (default)
	 
	| makeresults
	| eval data = "8.8.8.8;8.8.4.4", dataType = "ip", tlp = "GREEN", pap = "WHITE", analyzers = "GoogleDNS_resolve_1_0_0 ;Abuse_Finder_3_0"
	| makemv delim=";" data
	| mvexpand data
	| cortexrun data dataType tlp pap analyzers
	# This will start four jobs (two data and two analyzers) with TLP and PAP level set respectively to GREEN and WHITE
