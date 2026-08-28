# Log identifiers — what each code means, and what to do about it

Every line this add-on writes carries a code. This document says what each one
means, and for the ones that signal a problem, what to do next.

> ⚠️ **The interpretation below is written by hand.** The inventory at the end
> is generated from the source, and `tools/checks/log_ids_unique.py` fails when
> a code exists in the code but not here. So this file can be incomplete — it
> cannot silently stop matching reality.

## Anatomy of a line

```
[000123][THCC-140] exec_id=a1b2c3d4 - Processing attachment of the Splunk search results…
   │       │  │        │
   │       │  │        └── one execution of one command or alert action
   │       │  └─────────── the code documented here
   │       └────────────── which component is speaking
   └────────────────────── a serial number, unique per line
```

⚠️ **The code is unique within its module, not across the add-on.** The
component prefix is what disambiguates: `[THCC-140]` and `[THCA-140]` are two
different events. Reading a code without its prefix tells you nothing.

| Prefix | Component |
| :--- | :--- |
| `THCC` / `THCA` | alert actions "create a new case" / "create a new alert" |
| `THAO` / `THTE` | alert actions "add observables" / "add timeline event" |
| `CRJ` / `CSJ` / `CRA` | Cortex commands: run jobs, search jobs, refresh analyzers |
| `THSC` / `THSA` / `THGC` / `THGA` / `THGS` / `THGAFC` | TheHive search/get commands |
| `MI-*` | modular inputs (the collectors that index TheHive into Splunk) |
| `MA-*` | the alert action base class |
| `S*` | settings and instance resolution (`common.py`) |
| `TH*` / `C*` | the TheHive and Cortex clients |

## Finding them in Splunk

```
index=_internal sourcetype=tathehivecortex:log
index=_internal sourcetype=tathehivecortex:log "[THCC-"      ← one component
index=_internal sourcetype=tathehivecortex:log exec_id=a1b2c3d4   ← one run
```

⚠️ If that returns nothing on an installation upgraded from 4.0.0–4.2.2, the
sourcetype was never assigned — see `release_notes/v5.0.0.md`, which
explains the manual purge of `etc/apps/learned/local/props.conf`. Fall back to
`index=_internal source=*TA-thehive-cortex_*.log`.

---

# Codes that signal a problem

## Connecting to TheHive or Cortex

| Code | Meaning | What to do |
| :--- | :--- | :--- |
| `TH1` | No instance id was given to the command. | The command was called without its first argument. Check the SPL: `\| thehivesearchcases <instance_id> …`. |
| `TH10` `TH30` | The alert uses `<default>` but no default instance is configured. | Configuration → Settings → set a default instance, or name the instance explicitly in the alert action. |
| `TH20` `TH50` | Authentication type is neither `password` nor `api_key`. | Configuration → Instances → fix the type. A value written by hand into `local/thehive_cortex_instances.conf` is the usual cause. |
| `TH31` | Both password **and** API key are empty for this instance. | The account exists but carries no secret. Re-enter it in Configuration → Accounts — a stored password is not readable back, so an interrupted edit leaves it blank. |
| `TH45` | The server answered, but not with something this add-on can read. | Usually a reverse proxy or portal answering instead of TheHive. Check the URL and port point at TheHive itself. |
| `TH85` | Certificate verification failed. | Either the CA is not trusted by Splunk, or the certificate does not match the host. Set the CA in the instance settings; disabling verification hides the problem rather than fixing it. |
| `TH90` | TLS handshake failed. | Often a TLS version mismatch, or something that is not TLS on that port. |
| `TH95` `TH100` | The proxy refused, or could not be reached. | Check the proxy settings of the instance, and that its credentials are still valid. |
| `TH109` | The server returned an **HTML page** instead of JSON. | Almost always an authentication portal or an error page. Open the URL in a browser: what you see is what the add-on received. |
| `TH110` | The connection itself failed. | Network, DNS or firewall between the Splunk search head and TheHive. |
| `C7` | A Cortex instance was configured with a password. | Cortex only accepts an API key. Change the authentication type. |
| `C9` | Cortex authentication type is not one of the expected values. | Same as `TH20`, on the Cortex side. |
| `C15` | The Cortex API key is empty. | Re-enter it in the account; an empty key cannot connect. |
| `C25` | Cortex answered 404. | The URL is reachable but is not a Cortex API root. Check the path. |
| `C26` | Cortex answered "service unavailable". | Cortex is up but not ready, or behind a load balancer with no backend. |
| `C27` | Cortex rejected the credentials. | The API key is wrong or has been revoked. |
| `S13` `S13b` | A client or CA certificate is configured but the file was not found. | The path is relative to the search head that runs the search. A file present on one node is not present on the others. |
| `S41` | A setting could not be read; the default is used. | Harmless in itself, but it means the configuration page never wrote that value. Open it and save once. |
| `S3_ERROR` | Reading `storage/passwords` failed entirely. | ⚠️ No account has a password after this. Usually a permissions problem on the Splunk user running the search. |

## Resolving an instance or a case

| Code | Meaning | What to do |
| :--- | :--- | :--- |
| `S30` `S31` | The instance id does not match anything in the configuration. | The alert or search names an instance that was renamed or deleted. ⚠️ Since 4.2.3 this raises a named error instead of ending the Splunk process — a search that used to stop without a word now says why. |
| `S66` | The HTTP timeout setting could not be read. | Falls back to the built-in default. Save the Settings page once. |
| `TH114` | No case matches that number. | Not necessarily a fault: a case number that does not exist, or one in another organisation than the account's. |
| `TH118` | The lookup of a case number failed. | Distinct from `TH114`: here the query itself failed. Read the attached error. |
| `THAO-35` | A target id does not look like `~123`. | TheHive ids start with `~`. A case **number** (`42`) is not an id — the add-on resolves numbers separately. |

## Reading the events Splunk hands over

| Code | Meaning | What to do |
| :--- | :--- | :--- |
| `THC-86` | The configured timestamp field is absent from the row; now is used. | Check the field name against what the search actually produces. |
| `THC-87` | The timestamp field holds something non-numeric; now is used. | ⚠️ A date like `2026-01-01` lands here. The field must be an epoch, in seconds or milliseconds. |
| `THC-88` | The timestamp is numeric but is neither 10 nor 13 digits. | Microseconds, or a truncated value. Convert in the SPL: `eval ts=round(_time)`. |
| `THC-93` | A composite key `field:subfield` names a datatype the add-on does not know. | The raw value is forwarded rather than dropped. Add the datatype to the datatypes lookup if it is legitimate. |
| `THC-118` | A custom field has a type this add-on does not map. | Forwarded as text. Harmless if the field is textual; report the type otherwise. |
| `THC-117` | A custom field was **dropped**: its type is not handled, or its value does not match its declared type. | ⚠️ The alert or case is created *without* that field, and until 4.2.2 this happened in silence. Check the field's type in TheHive against the value the search produces. |
| `THC-106` | A key was ignored because TheHive reserves it as an internal field. | Rename the field in the SPL. The list of reserved names belongs to TheHive, not to this add-on. |
| `THC-120` | The MITRE catalogue could not be read; pattern ids go unchecked this time. | ⚠️ Not a rejection: an unreachable catalogue must not silently drop legitimate TTPs. Check the catalogue name in Settings, and that the account can read it. |
| `THC-122` | A TTP names a `patternId` that is **not in the catalogue**; the TTP is dropped. | The message names the id. Check it against the catalogue in TheHive — until 4.2.3 this was accepted here and refused by TheHive later, in a message naming neither the row nor the field. |
| `THC-113` | An observable was declared but carries no value. | The composite key names an observable (`myfield:ip`) but neither `myfield` nor `myfield:value` exists in the row. Usually a typo, or a field that is empty for that event. |
| `THC-4` | The datatypes collection exists but cannot be read; the refresh is aborted. | Deliberate: refreshing would overwrite content that could not be read first. Check that the KV store is up (`| inputlookup thehive_datatypes`). |
| `THC-5` | New datatypes could not be written to the collection. | Same family, on the write side. Nothing already stored is lost — only the new rows are missing. |
| `THC-6` | The datatypes could not be recovered from the TheHive API. | The add-on falls back to what the collection already holds. Check the connection. |
| `THC-7` | No Splunk client reached the code that reads the datatypes. | ⚠️ Internal: the client travels on the TheHive instance. Report it — an alert action cannot map observables without it. |
| `THC-8` | The KV store collection `kv_thehive_datatypes` is not reachable. | Check that the collection exists (`collections.conf`) and that the KV store is started on this search head. |
| `THC-9` | The legacy CSV exists but could not be read during the migration. | ⚠️ Rows customised in `lookups/thehive_datatypes.csv` are **not** migrated: fix the permissions, empty the collection, and let it seed again. |
| `THC-14` | The collection is being seeded from the legacy CSV. | Informational, once per installation. It names how many rows were migrated. |
| `THC-17` | The migrated rows could not be written to the collection. | ⚠️ The migration did not happen: the customised rows are still only in the CSV. Same causes as `THC-8`. |
| `THC-12` | The refresh failed; the rows already stored are used. | A warning, not a failure — but a datatype added in TheHive will not appear. |
| `THC-13` | The refresh failed **and** the collection holds no datatype. | ⚠️ Nothing to fall back on: custom field mapping will be wrong until this succeeds once. |
| `THC-16` | The datatypes collection is empty, malformed or unreadable. | Check the KV store on this search head; the add-on reseeds an empty collection by itself. |
| `THAO-20` | The target type is invalid; `alert` is assumed. | Check the alert action's parameter. |
| `THAO-25` | The sighted date is unreadable; now is used. | Same shape as `THC-87`: the field must be an epoch. |
| `THTE-20` | No case id could be resolved for a row; it is skipped. | The row carries neither a case id nor a resolvable number. |
| `THTE-30` | A date could not be parsed for a timeline event. | Check the format of the source field. |
| `C35` `CJ1` | Cortex does not know this data type. | ⚠️ Since 4.2.3 the job is submitted anyway and Cortex decides — the add-on no longer refuses on a list frozen at build time. |
| `C40` | The named analyzer does not exist on this Cortex. | Check the name, and that the analyzer is enabled for the organisation. |

## Sending to TheHive

| Code | Meaning | What to do |
| :--- | :--- | :--- |
| `THCA-122` `THCC-…` | The object already exists (duplicate); a retry follows. | Normal when a scheduled alert fires twice on overlapping windows. Use a stable `unique_id_field`. |
| `THCA-123` `THCC-126` | Creation failed; another attempt follows. | Read the attached error: it is the server's own message. |
| `THCC-135` `THCA-126` | The server accepted the request but returned **no id**. | ⚠️ Same event, two different codes — the two helpers never agreed. The object was probably not created: a validation rejection answered with 200. Check the payload in the attached `data=`. |
| `THCA-124` `THCC-127` | Every attempt failed. | ⚠️ The object was **not** created. Raise `thehive_creation_max_retry` only if the cause is transient. |
| `THCC-132` `THCC-137` | Adding an observable to a freshly created case failed. | The case exists, the observable does not. Check the observable's datatype and value. |
| `THCC-136` | The observable already exists on that case; it is skipped. | Informational. |
| `139` | Attaching MITRE TTPs failed. | The object exists without its TTPs. Check the `patternId` against the catalogue. |
| `THAO-60` | The observable already exists on the target. | Informational. |
| `THAO-70` | Adding the observable failed. | Read the attached response body — it carries TheHive's reason. |
| `THTE-ERR` | Creating a timeline event failed. | Check that the case still exists and the account can write to it. |
| `TH202` | Creating a timeline event failed, client side. | Same family, seen from the client. |
| `80` | The "run function" action failed on the events. | The function name, or the payload it received. |
| `THCA-1` | The external link back to Splunk could not be built. | The alert is created without its "results link". Set the Splunk base URL in the Settings page — the add-on cannot guess it from inside a search. |

## Attaching the search results

| Code | Meaning | What to do |
| :--- | :--- | :--- |
| `145` | The results file is being uncompressed. | Informational; it precedes the two below. |
| `148` | The results file could not be read. | ⚠️ Since 4.2.3 this aborts with a named error instead of failing three lines later inside the CSV writer. The file is the one Splunk wrote for the alert — a truncated dispatch directory is the usual cause. |
| `146` | The attachment format is not one of the four supported. | Was `141`, which also meant something else. Check the alert action's "attach format". |
| `151` | The results could not be prepared for attachment. | ⚠️ The object itself was created; only its attachment is missing. Processing continues with the next object. |
| `THCC-150` `THCA-150` | The upload to TheHive failed. | The file was built; TheHive refused it. Size limits are the usual cause. |
| `THCC-180` `THCA-160` | The upload returned nothing usable. | Same, seen from the response. |

## Collecting into Splunk (modular inputs)

| Code | Meaning | What to do |
| :--- | :--- | :--- |
| `MI-ERR-DATES` | The backfill date range could not be parsed. | Check the start and end dates of the input. |
| `MI-ERR-COLLECT` | The collection itself failed. | Read the attached error; it is the API's. |
| `MI-BTSK-ERR-DATE` `MI-BTL-ERR-DATE` | Same as `MI-ERR-DATES`, for tasks and timeline backfills. | |
| `ERR` | A collection failed. ⚠️ This bare code appears in several inputs — read the **prefix** to know which. | |
| `MI-ERR` | A collection failed, for the alerts/cases and audit inputs. | |
| `MA-ERR` `MA-WRN` | Error and warning of the alert action framework itself. | These come from the base class, before the add-on's own code runs. |
| `TH117` | The instance status could not be fetched. | The status input cannot reach TheHive. |
| `TH183` | The timeline of a case could not be fetched. | Often a case deleted between listing and fetching. |
| `6` | An unsupported filter was given to `thehivegetstats`. | The message lists the supported ones. |
| `C46` | A Cortex job could not be submitted. | Read the attached error. |

---

<!-- INVENTAIRE:DEBUT -->

# Complete inventory

> ⚠️ **Generated block — do not edit between the markers.**
> `python tools/checks/log_ids_unique.py --write` rebuilds it.

## `backfill_alerts_cases.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `MI-ERR-DATES` | 94 | error | … |
| `70` | 142 | info | {…} events (type: {…}, date: {…}) were recovered. |
| `MI-ERR-COLLECT` | 144 | error | Error: {…} |

## `backfill_audit.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `MI-ERR-DATES` | 89 | error | … |
| `70` | 103 | info | {…} events were recovered. |
| `MI-ERR-COLLECT` | 105 | error | Error: {…} |

## `backfill_observables.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `70` | 124 | info | {…} events (date: {…}) were recovered. |

## `backfill_tasks.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `MI-BTSK-ERR-DATE` | 85 | error | … |
| `1` | 101 | info | Starting backfill tasks collection for interval [from {…} to {…}] using {…} |
| `2` | 119 | info | Successfully backfilled {…} tasks. |
| `ERR` | 122 | error | Error during backfill tasks collection: {…} |

## `backfill_timeline.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `MI-BTL-ERR-DATE` | 83 | error | … |
| `1` | 98 | info | Starting backfill timeline collection for interval [from {…} to {…}] |
| `2` | 115 | info | Successfully backfilled {…} timeline events. |
| `ERR` | 118 | error | Error during backfill timeline collection: {…} |

## `common.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `S1` | 213 | debug | Python version detected: … |
| `S2` | 232 | debug | Logging mode set to … |
| `S3` | 250 | debug | Accounts retrieved: {…} |
| `S3_SKIP` | 259 | debug | Skipping unusable stored value for account {…} |
| `S3_ERROR` | 264 | error | Failed to access storage_passwords: {…} |
| `S4` | 267 | debug | Passwords retrieved for accounts: {…} |
| `S5` | 280 | debug | New instance detected, getting … |
| `S13` | 313 | warn | Be aware that a client certificate for instance " … … … |
| `S13b` | 335 | warn | Be aware that a CA certificate for instance " … … … |
| `S14` | 386 | debug | New instance parsed, adding key " … … … |
| `S15` | 402 | debug | Getting these additional parameters: … |
| `S26` | 445 | debug | Configuration … … … … … |
| `S27` | 455 | debug | Configuration … … … … |
| `S28` | 470 | debug | Configuration retrieved for the filename ' … … … |
| `S29` | 491 | debug | This account ( … … |
| `S30` | 512 | error | … |
| `S32` | 518 | debug | This instance ID ( … … … |
| `S31` | 540 | error | … |
| `S35` | 548 | debug | This instance ID ( … … … |
| `S40` | 565 | debug | this instance id ( … … … … … |
| `S41` | 575 | warn | Can't recover the setting " … … … … |
| `S45` | 596 | debug | Getting this parameter : thehive_default_instance= … |
| `S46` | 609 | debug | Getting this parameter : thehive_max_cases= … |
| `S50` | 622 | debug | Getting this parameter: thehive_sort_cases= … |
| `S51` | 634 | debug | Getting this parameter: thehive_max_alerts= … |
| `S52` | 647 | debug | Getting this parameter: thehive_sort_alerts= … |
| `S53` | 660 | debug | Getting this parameter: thehive_ttp_catalog_name= … |
| `S54` | 673 | debug | Getting this parameter: thehive_creation_attachment_prefix= … |
| `S57` | 687 | debug | Getting this parameter: thehive_cortex_http_timeout= … |
| `S58` | 700 | debug | Getting this parameter: thehive_creation_max_retry= … |
| `S55` | 713 | debug | Getting this parameter: … |
| `S56` | 725 | debug | Getting this parameter: … |
| `S60` | 733 | debug | Found parameter " … … … |
| `S66` | 740 | error | … |
| `S67` | 743 | debug | Parameter " … … … … |
| `U1` | 761 | debug | Utils class initiated |
| `U5` | 780 | debug | Event before processing (remove_unwanted_keys_from_dict): {…} |
| `U10` | 787 | debug | Event after processing (remove_unwanted_keys_from_dict): {…} |

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
| `THAO-20` | 85 | warning | Invalid target type '{…}', defaulting to 'alert' |
| `THAO-25` | 123 | warning | Invalid sighted date value '{…}', defaulting to now(). |
| `THAO-30` | 141 | info | No observables found in current row, skipping. |
| `THAO-35` | 148 | error | Invalid target ID format: '{…}'. Must match ^~[0-9]+$. Skipping this ID. |
| `THAO-40` | 173 | info | Adding observable to {…} {…}: Type={…}, Data={…}, TLP={…}, PAP={…}, IOC={…}, … |
| `THAO-50` | 180 | info | Successfully added observable to {…} {…} |
| `THAO-60` | 185 | warning | Observable already exists in {…} {…} (Status={…}). Skipping. |
| `THAO-70` | 191 | error | Failed to add observable to {…} {…}: {…}{…} |

## `ta_thehive_cortex/modalert_thehive_add_timeline_event_helper.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `THTE-20` | 51 | warning | No case ID resolved for result, skipping. |
| `THTE-30` | 86 | warning | Invalid date format for {…}: {…} |
| `THTE-ERR` | 101 | error | Failed to create timeline event for case {…}: {…} |

## `ta_thehive_cortex/modalert_thehive_common.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `THC-7` | 116 | error | no Splunk client carried by the TheHive instance: the datatype lookup cannot … |
| `THC-8` | 127 | error | KV store collection '{…}' is not reachable: {…} |
| `THC-9` | 152 | warn | {} exists but could not be read; the collection will be seeded from TheHive o… |
| `THC-14` | 160 | info | seeding '{}' with {} row(s) migrated from {} |
| `THC-4` | 191 | error | the datatype collection could not be read ({}), refresh aborted to avoid losi… |
| `THC-17` | 208 | error | the migrated rows could not be written to '{}': {} |
| `THC-2` | 225 | debug | Datatypes recovered from TheHive: … |
| `THC-5` | 249 | error | FATAL {} new datatype(s) could not be written to '{}': {} |
| `THC-6` | 256 | error | Could not recover datatypes from TheHive API: … |
| `THC-12` | 324 | warn | API refresh failed ({…}). Falling back to the rows already in the collection. |
| `THC-16` | 332 | error | collection '{…}' is empty, malformed or not readable: {…} |
| `THC-13` | 339 | error | API refresh failed and collection '{…}' holds no datatype. |
| `THC-15` | 348 | debug | dataType_dict built from '{}' ({} datatype(s)) |
| `THC-61` | 434 | debug | Row before pre-processing: … |
| `THC-62` | 457 | debug | Row after pre-processing: … |
| `THC-63` | 493 | debug | original sourceRef: {} was cut as it was a string too long (max 128 char). |
| `THC-64` | 501 | debug | sourceRef: {} |
| `THC-87` | 602 | warn | timestamp_field '{…}' holds a non-numeric value ('{…}'); falling back to curr… |
| `THC-80` | 608 | debug | new Timestamp from row: {} |
| `THC-88` | 618 | warn | timestamp_field '{…}' is neither a 10 nor a 13 digit epoch ('{…}'); falling b… |
| `THC-85` | 625 | debug | alert timestamp: {} |
| `THC-86` | 630 | warn | timestamp_field '{…}' missing; falling back to current time |
| `THC-90` | 640 | debug | field to process: {…} |
| `THC-91` | 644 | debug | composite fieldvalue detected: {…} |
| `THC-92` | 668 | debug | field: {} enriched with the information {} set to |
| `THC-93` | 680 | warn | composite key '{…}' was NOT mapped: '{…}' is not a known datatype. The raw va… |
| `THC-95` | 689 | debug | key is an observable: {} |
| `THC-96` | 710 | debug | key is a custom field: {}, with type {} |
| `THC-118` | 778 | warn | custom field '{…}' has type '{…}', which this add-on does not map; forwarding… |
| `THC-117` | 792 | warn | custom field '{…}' was NOT mapped: type '{…}' is not handled, or value '{…}' … |
| `THC-108` | 825 | debug | ttp was parsed correctly and added to the alert: {} |
| `THC-109` | 832 | debug | ttp already exist, ignoring duplicates: {} |
| `THC-122` | 842 | error | ttp '{…}' is not in the MITRE catalogue '{…}'; the TTP is dropped rather than… |
| `THC-105` | 859 | debug | key is added as another observable (scope is False): {} |
| `THC-106` | 877 | warn | key is used by TheHive as an internal field (scope is False): {}. Key ignored… |
| `THC-111` | 887 | debug | Processing observable data: {} ({}) |
| `THC-112` | 900 | debug | Multi-value split for {…}: '{…}' -> {…} |
| `THC-113` | 952 | warn | Observable '{0}' doesn't have any value set (no field '{0}' or '{0}:value' wa… |
| `THC-115` | 961 | debug | observables found for an alert: … |
| `THC-116` | 967 | debug | No observable found in current row (sourceRef={…}). |
| `THC-77` | 1038 | debug | Append results to description as markdown table |

## `ta_thehive_cortex/modalert_thehive_create_a_new_alert_helper.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `55` | 49 | debug | Arguments recovered: … |
| `56` | 52 | info | Configuration is ready. Creating the alert... |
| `57` | 55 | debug | TheHive URL instance used after retrieving the configuration: … |
| `58` | 60 | debug | Processing following instance ID: … |
| `1` | 92 | warn | Cannot determine external link url={}, results_link={} |
| `120` | 119 | debug | Processing alert: … |
| `122` | 121 | via helper | passed as `duplicate` to create_with_retry |
| `123` | 121 | via helper | passed as `retry` to create_with_retry |
| `124` | 121 | via helper | passed as `exhausted` to create_with_retry |
| `125` | 132 | info | TheHive alert {} is successfully created on url={} |
| `126` | 141 | error | TheHive alert creation has failed. url={}, data={}, content={} |
| `140` | 165 | info | Processing attachment of the Splunk search results to the alert... |
| `151` | 184 | error | The search results could not be prepared for attachment: {…} |
| `149` | 195 | via helper | passed as `uploading` to upload_attachment |
| `150` | 195 | via helper | passed as `failed` to upload_attachment |
| `155` | 195 | via helper | passed as `attached` to upload_attachment |
| `160` | 195 | via helper | passed as `not_attached` to upload_attachment |

## `ta_thehive_cortex/modalert_thehive_create_a_new_case_helper.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `55` | 47 | debug | Arguments recovered: … |
| `56` | 50 | info | Configuration is ready. Creating the case... |
| `57` | 53 | debug | TheHive URL instance used after retrieving the configuration: … |
| `58` | 58 | debug | Processing following instance ID: … |
| `120` | 101 | debug | Processing case: … |
| `126` | 103 | via helper | passed as `retry` to create_with_retry |
| `127` | 103 | via helper | passed as `exhausted` to create_with_retry |
| `130` | 114 | info | TheHive case #{} is successfully created on url={} |
| `135` | 123 | error | TheHive case creation has failed. url={}, data={}, content={} |
| `132` | 141 | error | TheHive observable update on recent case creation has failed. url={}, data={}… |
| `131` | 155 | info | TheHive case {} was successfully updated with the observable {} on url={} |
| `136` | 168 | warning | Observable already exists in case {} (Status={}). Skipping. url={}, data={} |
| `137` | 176 | error | TheHive observable update on recent case creation has failed. url={}, data={}… |
| `140` | 204 | info | Processing attachment of the Splunk search results to the case... |
| `151` | 223 | error | The search results could not be prepared for attachment: {…} |
| `149` | 234 | via helper | passed as `uploading` to upload_attachment |
| `150` | 234 | via helper | passed as `failed` to upload_attachment |
| `170` | 234 | via helper | passed as `attached` to upload_attachment |
| `180` | 234 | via helper | passed as `not_attached` to upload_attachment |

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

## `ta_thehive_cortex/ttp_catalogue.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `THC-120` | 59 | warn | the MITRE catalogue '{…}' could not be read ({…}); pattern ids are forwarded … |
| `THC-121` | 72 | debug | MITRE catalogue '{…}': {…} pattern id(s) loaded |

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
| `TH25` | 209 | debug | Settings recovered |
| `TH30` | 218 | error | Your alert is using the <default> instance ID setting which is empty in your … |
| `TH35` | 248 | debug | TheHive instance will be initialized with a password (not an API key) |
| `TH40` | 266 | debug | TheHive instance will be initialized with an API Key (not a password) |
| `TH50` | 283 | error | WRONG_AUTHENTICATION_TYPE - Authentication type is not one of the expected va… |
| `TH2` | 323 | debug | Version is: … |
| `TH119` | 328 | debug | Verification of CA cert path: {…}. Exists? {…} |
| `TH31` | 357 | error | THE_HIVE_AUTHENTICATION - Password AND API Key are null values |
| `TH41` | 363 | debug | TheHive instance is initialized, try a request to {} |
| `TH45` | 374 | error | THE_HIVE_AUTHENTICATION_RESPONSE - Server didn't respond with a valid respons… |
| `TH46` | 378 | debug | Payload content - Headers: … |
| `TH47` | 382 | debug | Payload content - URL: … |
| `TH51` | 387 | debug | TheHive API connection to (URL=" … … |
| `TH60` | 394 | debug | TheHive API connection to (URL=" … … … … |
| `TH85` | 405 | warn | THE_HIVE_CERTIFICATE_FAILED - It seems that the certificate verification fail… |
| `TH90` | 414 | warn | THE_HIVE_HANDHSHAKE_FAILURE - It seems that the SSL handshake failed. A possi… |
| `TH95` | 421 | warn | THE_HIVE_PROXY_AUTHENTICATION_ERROR - It seems that the connection to the pro… |
| `TH100` | 430 | warn | THE_HIVE_PROXY_ERROR - It seems that the connection to the proxy has failed. … |
| `TH109` | 441 | error | THEHIVE_HTML_RESPONSE_ERROR - The server at {…} returned an HTML page instead… |
| `TH110` | 446 | error | THEHIVE_CONNECTION_ERROR - Error: … … |
| `TH112` | 477 | info | Resolving internal ID for case number {…}... |
| `TH113` | 482 | info | Case number {…} resolved to {…} |
| `TH114` | 485 | warning | No case found with number {…} |
| `TH118` | 488 | error | Error resolving case number {…}: {…} |
| `TH115` | 500 | info | Retrieving instance status... |
| `TH116` | 503 | info | Got instance status successfully |
| `TH117` | 509 | error | FAILED_TO_GET_INSTANCE_STATUS - Error: {…} |
| `TH120` | 530 | info | Retrieving alerts count... |
| `TH121` | 532 | info | Got {…} alerts. Estimated time for processing all events: less than {…} secon… |
| `TH122` | 581 | debug | thehive - observables: … |
| `TH123` | 593 | debug | thehive - attachments: … |
| `TH125` | 637 | debug | Event after processing (check_and_reduce_values_size): {…} |
| `TH126` | 644 | info | {…} events have been processed... |
| `TH130` | 663 | info | Retrieving cases count... |
| `TH131` | 665 | info | Got {…} cases. Estimated time for processing all events: less than {…} seconds |
| `TH133` | 719 | debug | thehive - observables: … |
| `TH134` | 730 | debug | thehive - attachments: … |
| `TH135` | 741 | debug | thehive - pages: … |
| `TH136` | 752 | debug | thehive - ttps: … |
| `TH137` | 796 | debug | Event after processing (check_and_reduce_values_size): {…} |
| `TH138` | 803 | info | {…} events have been processed... |
| `TH141` | 815 | info | Tasks recovery detected. Got {…} tasks with filters: {…}. |
| `TH142` | 849 | debug | Event after processing (check_and_reduce_values_size): {…} |
| `TH139` | 856 | debug | TheHive - Tasks: … |
| `TH140` | 875 | info | Retrieving observables count... |
| `TH143` | 877 | info | Got {…} observables. Estimated time for processing all events: less than {…} … |
| `TH145` | 953 | debug | Event after processing (check_and_reduce_values_size): {…} |
| `TH146` | 959 | info | {…} events have been processed... |
| `TH170` | 978 | info | Retrieving audit logs count... |
| `TH171` | 980 | info | Got {…} audit logs. Estimated time for processing all events: less than {…} s… |
| `TH175` | 1045 | debug | Event after processing (check_and_reduce_values_size): {…} |
| `TH176` | 1051 | info | {…} events have been processed... |
| `TH190` | 1070 | info | Retrieving tasks... |
| `TH191` | 1079 | info | Got {…} tasks. |
| `TH180` | 1145 | info | Retrieving cases for timeline extraction... |
| `TH181` | 1149 | info | Got {…} cases to check for timeline events. |
| `TH182` | 1183 | debug | Fetching timeline for case {…} ({…}) |
| `TH183` | 1189 | error | Failed to fetch timeline for case {…}: {…} |
| `TH186` | 1204 | debug | Skipping timeline event {…} because kind {…} is not in {…} |
| `TH184` | 1240 | info | Processed timeline events for {…} entries so far... |
| `TH200` | 1267 | info | Creating custom timeline event for case {…}... |
| `TH201` | 1283 | info | Custom timeline event created successfully for case {…} |
| `TH202` | 1289 | error | FAILED_TO_CREATE_TIMELINE_EVENT - Error: {…} |

## `thehive_alerts_cases.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `MI-ERR` | 123 | error | Error: {…} |

## `thehive_audit.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `MI-ERR` | 86 | error | Error: {…} |

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
| `1` | 44 | debug | Input keywords: … |
| `2` | 45 | debug | Input results: … |
| `3` | 46 | info | Start processing with the instance: … |
| `10` | 53 | debug | Getting this case number: … |
| `25` | 66 | debug | Getting this alert: … |
| `26` | 69 | debug | Get alert ID " … … |
| `30` | 74 | debug | Event before post processing: … |
| `31` | 79 | debug | Found custom fields: … |
| `35` | 89 | debug | TheHive - Custom fields: … |
| `45` | 102 | debug | thehive - observables: … |
| `46` | 107 | debug | thehive - ttps: … |
| `50` | 110 | debug | Event after post processing: … |

## `thehive_get_case.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `1` | 44 | debug | Input keywords: … |
| `2` | 45 | debug | Input results: … |
| `3` | 46 | info | Start processing with the instance: … |
| `10` | 53 | debug | Getting this case number: … |
| `15` | 59 | debug | Event before post processing: … |
| `30` | 64 | debug | Found custom fields: … |
| `35` | 74 | debug | TheHive - Custom fields: … |
| `40` | 94 | debug | TheHive - Tasks: … |
| `45` | 99 | debug | thehive - observables: … |
| `46` | 104 | debug | thehive - ttps: … |
| `47` | 106 | debug | Event after post processing: … |

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
| `1` | 64 | info | Starting instance status collection |
| `2` | 93 | info | Successfully indexed instance status. |
| `ERR` | 96 | error | Error during instance status collection: {…} |

## `thehive_search_alerts.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `1` | 56 | debug | Input keywords: … |
| `2` | 57 | debug | Input results: … |
| `3` | 58 | info | Start processing with the instance: … |
| `5` | 78 | debug | Filters are: filterType: … … … … … … … … … … … … … … … … … |
| `15` | 131 | debug | Query is: … |
| `25` | 138 | debug | Getting this alert: … |
| `26` | 141 | debug | Get alert ID " … … |
| `30` | 146 | debug | Event before post processing: … |
| `31` | 151 | debug | Found custom fields: … |
| `35` | 161 | debug | TheHive - Custom fields: … |
| `45` | 174 | debug | thehive - observables: … |
| `46` | 179 | debug | thehive - ttps: … |
| `50` | 182 | debug | Event after post processing: … |

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
| `1` | 92 | info | Starting tasks collection for interval [from {…} to {…}] using {…} |
| `2` | 111 | info | Successfully indexed {…} tasks. |
| `ERR` | 114 | error | Error during tasks collection: {…} |

## `thehive_timeline.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `1` | 92 | info | Starting timeline collection for interval [from {…} to {…}] |
| `2` | 110 | info | Successfully indexed {…} timeline events. |
| `ERR` | 113 | error | Error during timeline collection: {…} |

*356 call sites.*

<!-- INVENTAIRE:FIN -->
