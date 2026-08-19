# Log identifiers

> ⚠️ **Generated file — do not edit.**
> `python tools/checks/log_ids_unique.py --write` rebuilds it, and the CI
> fails when it no longer matches the code. A registry maintained by hand
> drifts within a release, and then documents a past state while looking
> authoritative.

A rendered line reads `[serial][<command_id>-<id>]`. `command_id` namespaces
the identifier per command, so an identifier must be unique **within its
module** -- which is exactly what the check enforces.

## `backfill_alerts_cases.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `MI-ERR-DATES` | 97 | error | … |
| `70` | 145 | info | {…} events (type: {…}, date: {…}) were recovered. |
| `MI-ERR-COLLECT` | 147 | error | Error: {…} |

## `backfill_audit.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `MI-ERR-DATES` | 92 | error | … |
| `70` | 106 | info | {…} events were recovered. |
| `MI-ERR-COLLECT` | 108 | error | Error: {…} |

## `backfill_observables.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `70` | 127 | info | {…} events (date: {…}) were recovered. |

## `backfill_tasks.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `MI-BTSK-ERR-DATE` | 88 | error | … |
| `1` | 104 | info | Starting backfill tasks collection for interval [from {…} to {…}] using {…} |
| `2` | 122 | info | Successfully backfilled {…} tasks. |
| `ERR` | 125 | error | Error during backfill tasks collection: {…} |

## `backfill_timeline.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `MI-BTL-ERR-DATE` | 86 | error | … |
| `1` | 101 | info | Starting backfill timeline collection for interval [from {…} to {…}] |
| `2` | 118 | info | Successfully backfilled {…} timeline events. |
| `ERR` | 121 | error | Error during backfill timeline collection: {…} |

## `common.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `S1` | 217 | debug | Python version detected: … |
| `S2` | 236 | debug | Logging mode set to … |
| `S3` | 254 | debug | Accounts retrieved: {…} |
| `S3_SKIP` | 263 | debug | Skipping unusable stored value for account {…} |
| `S3_ERROR` | 268 | error | Failed to access storage_passwords: {…} |
| `S4` | 271 | debug | Passwords retrieved for accounts: {…} |
| `S5` | 284 | debug | New instance detected, getting … |
| `S13` | 317 | warn | Be aware that a client certificate for instance " … … … |
| `S13b` | 339 | warn | Be aware that a CA certificate for instance " … … … |
| `S14` | 390 | debug | New instance parsed, adding key " … … … |
| `S15` | 406 | debug | Getting these additional parameters: … |
| `S26` | 449 | debug | Configuration … … … … … |
| `S27` | 459 | debug | Configuration … … … … |
| `S28` | 474 | debug | Configuration retrieved for the filename ' … … … |
| `S29` | 495 | debug | This account ( … … |
| `S30` | 516 | error | … |
| `S32` | 522 | debug | This instance ID ( … … … |
| `S31` | 544 | error | … |
| `S35` | 552 | debug | This instance ID ( … … … |
| `S40` | 569 | debug | this instance id ( … … … … … |
| `S41` | 579 | warn | Can't recover the setting " … … … … |
| `S45` | 600 | debug | Getting this parameter : thehive_default_instance= … |
| `S46` | 613 | debug | Getting this parameter : thehive_max_cases= … |
| `S50` | 626 | debug | Getting this parameter: thehive_sort_cases= … |
| `S51` | 638 | debug | Getting this parameter: thehive_max_alerts= … |
| `S52` | 651 | debug | Getting this parameter: thehive_sort_alerts= … |
| `S53` | 664 | debug | Getting this parameter: thehive_ttp_catalog_name= … |
| `S54` | 677 | debug | Getting this parameter: thehive_creation_attachment_prefix= … |
| `S57` | 691 | debug | Getting this parameter: thehive_cortex_http_timeout= … |
| `S58` | 704 | debug | Getting this parameter: thehive_creation_max_retry= … |
| `S55` | 717 | debug | Getting this parameter: … |
| `S56` | 729 | debug | Getting this parameter: … |
| `S60` | 737 | debug | Found parameter " … … … |
| `S66` | 744 | error | … |
| `S67` | 747 | debug | Parameter " … … … … |
| `U1` | 765 | debug | Utils class initiated |
| `U5` | 784 | debug | Event before processing (remove_unwanted_keys_from_dict): {…} |
| `U10` | 791 | debug | Event after processing (remove_unwanted_keys_from_dict): {…} |

## `cortex.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `C5` | 75 | debug | Connection to Splunk done |
| `C6` | 77 | debug | Settings recovered |
| `C7` | 98 | error | Cortex instance will be initialized with a password (not an API key) - This i… |
| `C8` | 101 | debug | Cortex instance will be initialized with an API Key (not a password) |
| `C9` | 104 | error | WRONG_AUTHENTICATION_TYPE - Authentication type is not one of the expected va… |
| `C15` | 117 | error | API Key is null, this is the only way to connect to a Cortex instance |
| `C19` | 120 | debug | Cortex object will be instanciated with url '{…}' |
| `C20` | 122 | debug | Cortex object instanciated |
| `C21` | 127 | debug | Cortex API connection to (URL=" … … |
| `C25` | 129 | error | RESOURCE NOT FOUND - Cortex service is unavailable, is the configuration corr… |
| `C26` | 132 | error | SERVICE UNAVAILABLE - Cortex service is unavailable, is the configuration cor… |
| `C27` | 135 | error | AUTHENTICATION ERROR - Credentials are invalid |
| `C30` | 143 | debug | Getting jobs: … |
| `C35` | 158 | warn | UNKNOWN DATA TYPE - This data type ( … … |
| `C40` | 170 | error | ANALYZER NOT FOUND - This analyzer ( … … |
| `C41` | 172 | debug | Analyzers recovered: … |
| `C42` | 175 | debug | Job instance created |
| `C45` | 187 | debug | JOB sent: … |
| `C46` | 191 | error | … … … |
| `CJ1` | 208 | warn | UNKNOWN DATA TYPE - This data type ( … … |
| `CJ5` | 215 | debug | [ … … … … |
| `CJ6` | 216 | debug | [ … … … … |
| `CJ7` | 217 | debug | [ … … … … |
| `CJ8` | 218 | debug | [ … … … |

## `cortex_refresh_analyzers.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `CRA1` | 38 | debug | Input keywords: … |
| `CRA2` | 39 | debug | Input results: … |
| `CRA5` | 48 | debug | Getting this analyzer: … |

## `cortex_run_jobs.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `1` | 42 | debug | Input keywords: … |
| `2` | 43 | debug | Input results: … |
| `5` | 57 | debug | Adding a new job (no details) |
| `6` | 59 | debug | Job(s) are running |
| `10` | 64 | debug | Job details: … |
| `15` | 78 | debug | Event details: … |

## `cortex_search_jobs.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `1` | 47 | debug | Input keywords: … |
| `2` | 48 | debug | Input results: … |
| `10` | 78 | info | Query is: … |
| `15` | 85 | debug | Job details: … |
| `16` | 89 | debug | Report details: " … … … |
| `20` | 95 | debug | Event before post processing: … |
| `25` | 112 | debug | Event after post processing: … |

## `ta_thehive_cortex/alert_actions_base.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `MA-ERR` | 59 | error | … |
| `MA-INF` | 63 | info | … |
| `MA-DBG` | 67 | debug | … |
| `MA-WRN` | 71 | warn | … |

## `ta_thehive_cortex/attachment_builder.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `141` | 75 | debug | Processing results file: {…} |
| `145` | 86 | warn | Uncompressing Splunk search results file located at {…}... |
| `148` | 116 | error | Error during uncompressing process: {…} |
| `146` | 159 | error | Attachment format isn't supported, given: {…} |

## `ta_thehive_cortex/modalert_args.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `50` | 86 | debug | scope: {} |

## `ta_thehive_cortex/modalert_cortex_run_a_new_job_helper.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `43` | 53 | debug | Cortex connection is ready. Processing job parameters... |
| `44` | 79 | debug | Arguments recovered: … |
| `45` | 82 | info | Job preparation is finished. Running the job... |
| `46` | 84 | info | Job creation is done. |

## `ta_thehive_cortex/modalert_thehive_add_observables_helper.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `THAO-20` | 87 | warning | Invalid target type '{…}', defaulting to 'alert' |
| `THAO-25` | 125 | warning | Invalid sighted date value '{…}', defaulting to now(). |
| `THAO-30` | 143 | info | No observables found in current row, skipping. |
| `THAO-35` | 150 | error | Invalid target ID format: '{…}'. Must match ^~[0-9]+$. Skipping this ID. |
| `THAO-40` | 175 | info | Adding observable to {…} {…}: Type={…}, Data={…}, TLP={…}, PAP={…}, IOC={…}, … |
| `THAO-50` | 182 | info | Successfully added observable to {…} {…} |
| `THAO-60` | 187 | warning | Observable already exists in {…} {…} (Status={…}). Skipping. |
| `THAO-70` | 193 | error | Failed to add observable to {…} {…}: {…}{…} |

## `ta_thehive_cortex/modalert_thehive_add_timeline_event_helper.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `THTE-20` | 53 | warning | No case ID resolved for result, skipping. |
| `THTE-30` | 88 | warning | Invalid date format for {…}: {…} |
| `THTE-ERR` | 103 | error | Failed to create timeline event for case {…}: {…} |

## `ta_thehive_cortex/modalert_thehive_common.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `THC-4` | 114 | error | {} exists but could not be read, refresh aborted to avoid losing its content |
| `THC-2` | 125 | debug | Datatypes recovered from TheHive: … |
| `THC-5` | 149 | error | FATAL {} could not be opened in write mode |
| `THC-6` | 156 | error | Could not recover datatypes from TheHive API: … |
| `THC-10` | 176 | debug | Directory found: … |
| `THC-11` | 183 | info | File {…} is older than 24h ({…}s). Merging new datatypes from API (existing r… |
| `THC-12` | 198 | warn | API refresh failed for {…}. Falling back to existing file. |
| `THC-13` | 203 | error | API refresh failed and no existing file {…} found. |
| `THC-15` | 223 | debug | dataType_dict built from thehive_datatypes.csv |
| `THC-16` | 228 | error | file {…} empty, malformed or not readable |
| `THC-61` | 309 | debug | Row before pre-processing: … |
| `THC-62` | 332 | debug | Row after pre-processing: … |
| `THC-63` | 368 | debug | original sourceRef: {} was cut as it was a string too long (max 128 char). |
| `THC-64` | 376 | debug | sourceRef: {} |
| `THC-87` | 477 | warn | timestamp_field '{…}' holds a non-numeric value ('{…}'); falling back to curr… |
| `THC-80` | 483 | debug | new Timestamp from row: {} |
| `THC-88` | 493 | warn | timestamp_field '{…}' is neither a 10 nor a 13 digit epoch ('{…}'); falling b… |
| `THC-85` | 500 | debug | alert timestamp: {} |
| `THC-86` | 505 | warn | timestamp_field '{…}' missing; falling back to current time |
| `THC-90` | 515 | debug | field to process: {…} |
| `THC-91` | 519 | debug | composite fieldvalue detected: {…} |
| `THC-92` | 543 | debug | field: {} enriched with the information {} set to |
| `THC-93` | 555 | warn | composite key '{…}' was NOT mapped: '{…}' is not a known datatype. The raw va… |
| `THC-95` | 564 | debug | key is an observable: {} |
| `THC-96` | 585 | debug | key is a custom field: {}, with type {} |
| `THC-118` | 653 | warn | custom field '{…}' has type '{…}', which this add-on does not map; forwarding… |
| `THC-117` | 667 | warn | custom field '{…}' was NOT mapped: type '{…}' is not handled, or value '{…}' … |
| `THC-108` | 693 | debug | ttp was parsed correctly and added to the alert: {} |
| `THC-109` | 700 | debug | ttp already exist, ignoring duplicates: {} |
| `THC-105` | 715 | debug | key is added as another observable (scope is False): {} |
| `THC-106` | 733 | warn | key is used by TheHive as an internal field (scope is False): {}. Key ignored… |
| `THC-111` | 743 | debug | Processing observable data: {} ({}) |
| `THC-112` | 756 | debug | Multi-value split for {…}: '{…}' -> {…} |
| `THC-113` | 808 | warn | Observable '{0}' doesn't have any value set (no field '{0}' or '{0}:value' wa… |
| `THC-115` | 817 | debug | observables found for an alert: … |
| `THC-116` | 823 | debug | No observable found in current row (sourceRef={…}). |
| `THC-77` | 894 | debug | Append results to description as markdown table |

## `ta_thehive_cortex/modalert_thehive_create_a_new_alert_helper.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `55` | 49 | debug | Arguments recovered: … |
| `56` | 52 | info | Configuration is ready. Creating the alert... |
| `57` | 55 | debug | TheHive URL instance used after retrieving the configuration: … |
| `58` | 60 | debug | Processing following instance ID: … |
| `1` | 92 | warn | Cannot determine external link url={}, results_link={} |
| `120` | 119 | debug | Processing alert: … |
| `125` | 132 | info | TheHive alert {} is successfully created on url={} |
| `126` | 141 | error | TheHive alert creation has failed. url={}, data={}, content={} |
| `140` | 165 | info | Processing attachment of the Splunk search results to the alert... |
| `151` | 184 | error | The search results could not be prepared for attachment: {…} |

## `ta_thehive_cortex/modalert_thehive_create_a_new_case_helper.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `55` | 47 | debug | Arguments recovered: … |
| `56` | 50 | info | Configuration is ready. Creating the case... |
| `57` | 53 | debug | TheHive URL instance used after retrieving the configuration: … |
| `58` | 58 | debug | Processing following instance ID: … |
| `120` | 101 | debug | Processing case: … |
| `130` | 114 | info | TheHive case #{} is successfully created on url={} |
| `135` | 123 | error | TheHive case creation has failed. url={}, data={}, content={} |
| `132` | 141 | error | TheHive observable update on recent case creation has failed. url={}, data={}… |
| `131` | 155 | info | TheHive case {} was successfully updated with the observable {} on url={} |
| `136` | 168 | warning | Observable already exists in case {} (Status={}). Skipping. url={}, data={} |
| `137` | 176 | error | TheHive observable update on recent case creation has failed. url={}, data={}… |
| `140` | 204 | info | Processing attachment of the Splunk search results to the case... |
| `151` | 223 | error | The search results could not be prepared for attachment: {…} |

## `ta_thehive_cortex/modalert_thehive_run_function_helper.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `56` | 65 | info | Configuration is ready. Running the function... |
| `57` | 68 | debug | TheHive URL instance used after retrieving the configuration: … |
| `58` | 73 | debug | Processing following instance ID: … |
| `65` | 88 | debug | Row before pre-processing: … |
| `67` | 111 | debug | Row after pre-processing: … |
| `70` | 119 | debug | Run function "{}" with the events: |
| `75` | 128 | info | Function was run on the events: {} |
| `80` | 132 | error | Function didn't run correctly on the events: {} |

## `ta_thehive_cortex/post_creation.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `138` | 33 | info | Object {…} was successfully updated with the TTPs on url={…} |
| `139` | 38 | error | TTPs update on recent creation has failed. url={…}, {…}, content={…}, ttp={…} |

## `thehive.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `TH1` | 45 | error | MISSING_INSTANCE_ID - No instance ID was given to the script |
| `TH5` | 68 | debug | Connection to Splunk done |
| `TH6` | 70 | debug | Settings recovered |
| `TH10` | 91 | error | Your alert is using the <default> instance ID setting which is empty in your … |
| `TH11` | 106 | debug | Secret length: {…} |
| `TH15` | 130 | debug | TheHive instance will be initialized with a password (not an API key) |
| `TH16` | 148 | debug | TheHive instance will be initialized with an API Key (not a password) |
| `TH20` | 165 | error | WRONG_AUTHENTICATION_TYPE - Authentication type is not one of the expected va… |
| `TH25` | 197 | debug | Settings recovered |
| `TH30` | 206 | error | Your alert is using the <default> instance ID setting which is empty in your … |
| `TH35` | 236 | debug | TheHive instance will be initialized with a password (not an API key) |
| `TH40` | 254 | debug | TheHive instance will be initialized with an API Key (not a password) |
| `TH50` | 271 | error | WRONG_AUTHENTICATION_TYPE - Authentication type is not one of the expected va… |
| `TH2` | 304 | debug | Version is: … |
| `TH119` | 309 | debug | Verification of CA cert path: {…}. Exists? {…} |
| `TH31` | 338 | error | THE_HIVE_AUTHENTICATION - Password AND API Key are null values |
| `TH41` | 344 | debug | TheHive instance is initialized, try a request to {} |
| `TH45` | 355 | error | THE_HIVE_AUTHENTICATION_RESPONSE - Server didn't respond with a valid respons… |
| `TH46` | 359 | debug | Payload content - Headers: … |
| `TH47` | 363 | debug | Payload content - URL: … |
| `TH51` | 368 | debug | TheHive API connection to (URL=" … … |
| `TH60` | 375 | debug | TheHive API connection to (URL=" … … … … |
| `TH85` | 386 | warn | THE_HIVE_CERTIFICATE_FAILED - It seems that the certificate verification fail… |
| `TH90` | 395 | warn | THE_HIVE_HANDHSHAKE_FAILURE - It seems that the SSL handshake failed. A possi… |
| `TH95` | 402 | warn | THE_HIVE_PROXY_AUTHENTICATION_ERROR - It seems that the connection to the pro… |
| `TH100` | 411 | warn | THE_HIVE_PROXY_ERROR - It seems that the connection to the proxy has failed. … |
| `TH109` | 422 | error | THEHIVE_HTML_RESPONSE_ERROR - The server at {…} returned an HTML page instead… |
| `TH110` | 427 | error | THEHIVE_CONNECTION_ERROR - Error: … … |
| `TH112` | 458 | info | Resolving internal ID for case number {…}... |
| `TH113` | 463 | info | Case number {…} resolved to {…} |
| `TH114` | 466 | warning | No case found with number {…} |
| `TH118` | 469 | error | Error resolving case number {…}: {…} |
| `TH115` | 481 | info | Retrieving instance status... |
| `TH116` | 484 | info | Got instance status successfully |
| `TH117` | 490 | error | FAILED_TO_GET_INSTANCE_STATUS - Error: {…} |
| `TH120` | 511 | info | Retrieving alerts count... |
| `TH121` | 513 | info | Got {…} alerts. Estimated time for processing all events: less than {…} secon… |
| `TH122` | 562 | debug | thehive - observables: … |
| `TH123` | 574 | debug | thehive - attachments: … |
| `TH125` | 618 | debug | Event after processing (check_and_reduce_values_size): {…} |
| `TH126` | 625 | info | {…} events have been processed... |
| `TH130` | 644 | info | Retrieving cases count... |
| `TH131` | 646 | info | Got {…} cases. Estimated time for processing all events: less than {…} seconds |
| `TH133` | 700 | debug | thehive - observables: … |
| `TH134` | 711 | debug | thehive - attachments: … |
| `TH135` | 722 | debug | thehive - pages: … |
| `TH136` | 733 | debug | thehive - ttps: … |
| `TH137` | 777 | debug | Event after processing (check_and_reduce_values_size): {…} |
| `TH138` | 784 | info | {…} events have been processed... |
| `TH141` | 796 | info | Tasks recovery detected. Got {…} tasks with filters: {…}. |
| `TH142` | 830 | debug | Event after processing (check_and_reduce_values_size): {…} |
| `TH139` | 837 | debug | TheHive - Tasks: … |
| `TH140` | 856 | info | Retrieving observables count... |
| `TH143` | 858 | info | Got {…} observables. Estimated time for processing all events: less than {…} … |
| `TH145` | 934 | debug | Event after processing (check_and_reduce_values_size): {…} |
| `TH146` | 940 | info | {…} events have been processed... |
| `TH170` | 959 | info | Retrieving audit logs count... |
| `TH171` | 961 | info | Got {…} audit logs. Estimated time for processing all events: less than {…} s… |
| `TH175` | 1026 | debug | Event after processing (check_and_reduce_values_size): {…} |
| `TH176` | 1032 | info | {…} events have been processed... |
| `TH190` | 1051 | info | Retrieving tasks... |
| `TH191` | 1060 | info | Got {…} tasks. |
| `TH180` | 1126 | info | Retrieving cases for timeline extraction... |
| `TH181` | 1130 | info | Got {…} cases to check for timeline events. |
| `TH182` | 1164 | debug | Fetching timeline for case {…} ({…}) |
| `TH183` | 1170 | error | Failed to fetch timeline for case {…}: {…} |
| `TH186` | 1185 | debug | Skipping timeline event {…} because kind {…} is not in {…} |
| `TH184` | 1221 | info | Processed timeline events for {…} entries so far... |
| `TH200` | 1248 | info | Creating custom timeline event for case {…}... |
| `TH201` | 1264 | info | Custom timeline event created successfully for case {…} |
| `TH202` | 1270 | error | FAILED_TO_CREATE_TIMELINE_EVENT - Error: {…} |

## `thehive_alerts_cases.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `MI-ERR` | 126 | error | Error: {…} |

## `thehive_audit.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `MI-ERR` | 89 | error | Error: {…} |

## `thehive_get_alert.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `1` | 44 | debug | Input keywords: … |
| `2` | 45 | debug | Input results: … |
| `3` | 46 | info | Start processing with the instance: … |
| `5` | 53 | debug | Getting this alert: … |
| `15` | 65 | debug | Event before post processing: … |
| `30` | 70 | debug | Found custom fields: … |
| `35` | 80 | debug | TheHive - Custom fields: … |
| `45` | 93 | debug | thehive - observables: … |
| `50` | 98 | debug | thehive - ttps: … |
| `55` | 101 | debug | Event after post processing: … |

## `thehive_get_alerts_from_case.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `1` | 46 | debug | Input keywords: … |
| `2` | 47 | debug | Input results: … |
| `3` | 48 | info | Start processing with the instance: … |
| `10` | 55 | debug | Getting this case number: … |
| `25` | 68 | debug | Getting this alert: … |
| `26` | 71 | debug | Get alert ID " … … |
| `30` | 76 | debug | Event before post processing: … |
| `31` | 81 | debug | Found custom fields: … |
| `35` | 91 | debug | TheHive - Custom fields: … |
| `45` | 104 | debug | thehive - observables: … |
| `46` | 109 | debug | thehive - ttps: … |
| `50` | 112 | debug | Event after post processing: … |

## `thehive_get_case.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `1` | 46 | debug | Input keywords: … |
| `2` | 47 | debug | Input results: … |
| `3` | 48 | info | Start processing with the instance: … |
| `10` | 55 | debug | Getting this case number: … |
| `15` | 61 | debug | Event before post processing: … |
| `30` | 66 | debug | Found custom fields: … |
| `35` | 76 | debug | TheHive - Custom fields: … |
| `40` | 96 | debug | TheHive - Tasks: … |
| `45` | 101 | debug | thehive - observables: … |
| `46` | 106 | debug | thehive - ttps: … |
| `47` | 108 | debug | Event after post processing: … |

## `thehive_get_stats.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `1` | 64 | debug | Input keywords: … |
| `2` | 65 | debug | Input results: … |
| `3` | 66 | info | Start processing with the instance: … |
| `6` | 80 | error | Filter condition not supported, got '{…}' when only those are supported: {…} |
| `15` | 127 | debug | Filter is: … |
| `20` | 134 | debug | Executing request... |
| `25` | 136 | debug | Got response: … |
| `30` | 150 | debug | Output results: … |

## `thehive_instance_status.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `1` | 68 | info | Starting instance status collection |
| `2` | 97 | info | Successfully indexed instance status. |
| `ERR` | 100 | error | Error during instance status collection: {…} |

## `thehive_search_alerts.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `1` | 57 | debug | Input keywords: … |
| `2` | 58 | debug | Input results: … |
| `3` | 59 | info | Start processing with the instance: … |
| `5` | 79 | debug | Filters are: filterType: … … … … … … … … … … … … … … … … … |
| `15` | 132 | debug | Query is: … |
| `25` | 139 | debug | Getting this alert: … |
| `26` | 142 | debug | Get alert ID " … … |
| `30` | 147 | debug | Event before post processing: … |
| `31` | 152 | debug | Found custom fields: … |
| `35` | 162 | debug | TheHive - Custom fields: … |
| `45` | 175 | debug | thehive - observables: … |
| `46` | 180 | debug | thehive - ttps: … |
| `50` | 183 | debug | Event after post processing: … |

## `thehive_search_cases.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `1` | 57 | debug | Input keywords: … |
| `2` | 58 | debug | Input results: … |
| `3` | 59 | info | Start processing with the instance: … |
| `5` | 79 | debug | Filters are: filterKeyword: … … … … … … … … … … … … … … … … … |
| `15` | 134 | debug | Query is: … |
| `25` | 141 | debug | Getting this case: … |
| `26` | 144 | debug | Get case ID " … … |
| `30` | 149 | debug | Event before post processing: … |
| `31` | 155 | debug | Found custom fields: … |
| `35` | 165 | debug | TheHive - Custom fields: … |
| `40` | 184 | debug | TheHive - Tasks: … |
| `45` | 189 | debug | thehive - observables: … |
| `46` | 194 | debug | thehive - ttps: … |
| `47` | 196 | debug | Event after post processing: … |

## `thehive_tasks.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `1` | 95 | info | Starting tasks collection for interval [from {…} to {…}] using {…} |
| `2` | 114 | info | Successfully indexed {…} tasks. |
| `ERR` | 117 | error | Error during tasks collection: {…} |

## `thehive_timeline.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `1` | 95 | info | Starting timeline collection for interval [from {…} to {…}] |
| `2` | 113 | info | Successfully indexed {…} timeline events. |
| `ERR` | 116 | error | Error during timeline collection: {…} |

*337 call sites.*
