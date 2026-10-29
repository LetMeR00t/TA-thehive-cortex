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
| `TH111` | TheHive answered, and refused the credentials of the instance's **authentication mode** (named in the message). | `password` mode is HTTP Basic, read by TheHive as `user:password[:otp]` and cut at every `:` — a password containing `:` can never pass, nor can an account with multi-factor authentication. Use an API key (`api_key` mode). In `api_key` mode: the key is unknown, revoked, or its account is locked. |
| `TH110` | The connection itself failed. | Network, DNS or firewall between the Splunk search head and TheHive. |
| `C7` | A Cortex instance was configured with a password. | Cortex only accepts an API key. Change the authentication type. |
| `C9` | Cortex authentication type is not one of the expected values. | Same as `TH20`, on the Cortex side. |
| `C15` | The Cortex API key is empty. | Re-enter it in the account; an empty key cannot connect. |
| `C25` | Cortex answered 404. | The URL is reachable but is not a Cortex API root. Check the path. |
| `C26` | The connection to Cortex failed; the `Cause:` part names how. | An `SSLError` cause: the server certificate is not trusted, set the instance's **CA Certificate Path**. Otherwise Cortex is down, not ready, or behind a load balancer with no backend. |
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
| `THC-123` | An observable's `sighted_at` is not a valid epoch, in seconds or milliseconds; the observable is created without a sighting date. | Same shape as `THC-87`/`THC-88`, but on the `sighted_at` sub-key of an observable rather than the row-level timestamp. Check the field feeding it against what the search actually produces. |
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
| `CSJ-30` | The `wait` field of `cortexjobs` is not a number of seconds. | Falls back to 0, i.e. no waiting — the behaviour of every version before v5.0.0. Check the field in the SPL. |
| `CSJ-33` | The artifacts of a job could not be read. | ⚠️ The report is kept: they are two separate calls. Only `cortex_job_artifacts` is missing from that row. Usually a transient Cortex error. |
| `CSJ-34` | Cortex refused the job search; the line carries the query and Cortex's own answer. | `SearchError` on a field: that field is not searchable on this Cortex version. Otherwise check the `datatypes`/`analyzers` values and the `sort_jobs` field name. |

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
| `133` | The TTPs were **REFUSED**: the account lacks `manageProcedure`. | ⚠️ The alert or case **was created** — only its TTPs are missing, and the action no longer fails for it. Grant `manageProcedure` to the profile of that account, on that organisation. It is a TheHive permission; the add-on cannot fix it. |
| `134` | Attaching the TTPs raised an error of another kind. | Same consequence: the object exists, its TTPs do not. The raw error is in the message. |
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
| `MI-ERR` | A collection failed, for the alerts/cases, audit and observables inputs. | Nothing is lost: the input's watermark stays where it was and the next run collects the same window again. Read the attached error if it repeats. |
| `KV` | The KV store is **disabled** on this instance (`server.conf [kvstore] disabled = true`, found on some heavy forwarders), so the live inputs keep their watermarks in the input's checkpoint directory, on this instance only. | Collection continues. On a search head cluster the watermarks are then not shared between members. |
| `KVWAIT` | The KV store is enabled but **not ready** (starting after a restart, or failed), so this run did not collect. | Nothing is lost: the watermark waits and the next run catches up. A few lines right after a restart are normal; if it repeats, check the KV store status (`splunk show kvstore-status`). |
| `KVOPEN` | The watermark store (KV store collection or checkpoint directory) could not be opened, so this run did not collect. | Nothing is lost: the next run catches up. If it repeats, read the error type and check the KV store or the checkpoint directory's permissions. |
| `CKPT` | A window was collected and written, but its watermark could not be saved. | The next run collects that window again, so a few events can be indexed twice; summaries de-duplicate on the audit/object id. Check the KV store if it repeats. |
| `MA-ERR` `MA-WRN` | Error and warning of the alert action framework itself. | These come from the base class, before the add-on's own code runs. |
| `TH117` | The instance status could not be fetched. | The status input cannot reach TheHive. |
| `TH183` | The timeline of a case could not be fetched. | Often a case deleted between listing and fetching. |
| `TH127` | A collected object came without one of its dates (`_createdAt`, or the date the input sorts on, e.g. `_updatedAt` on an object never updated). It **was** indexed: `_time` is taken from the next available date (that date, else `_createdAt`, else `_updatedAt`, else now). The message names the missing date and the fields that were present -- names only. | Nothing to recover. If it repeats for objects that should carry the date, report the object type and field list to the maintainer. Before this code existed, such an object made the run fail with `KeyError` and lose its whole time window. |
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
| `MI-ERR-DATES` | 95 | error | … |
| `70` | 140 | info | {…} events (type: {…}, date: {…}) were recovered. |
| `MI-ERR-COLLECT` | 142 | error | Error: {…} |

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
| `S1` | 149 | debug | Python version detected: … |
| `S2` | 168 | debug | Logging mode set to … |
| `S3` | 186 | debug | Accounts retrieved: {…} |
| `S3_SKIP` | 195 | debug | Skipping unusable stored value for account {…} |
| `S3_ERROR` | 200 | error | Failed to access storage_passwords: {…} |
| `S4` | 203 | debug | Passwords retrieved for accounts: {…} |
| `S5` | 220 | debug | New instance detected, getting … |
| `S13` | 253 | warn | Be aware that a client certificate for instance " … … … |
| `S13b` | 275 | warn | Be aware that a CA certificate for instance " … … … |
| `S14` | 326 | debug | New instance parsed, adding key " … … … |
| `S15` | 342 | debug | Getting these additional parameters: … |

## `cortex.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `C5` | 75 | debug | Connection to Splunk done |
| `C6` | 77 | debug | Settings recovered |
| `C7` | 102 | error | Cortex instance will be initialized with a password (not an API key) - This i… |
| `C8` | 105 | debug | Cortex instance will be initialized with an API Key (not a password) |
| `C9` | 108 | error | WRONG_AUTHENTICATION_TYPE - Authentication type is not one of the expected va… |
| `C15` | 121 | error | API Key is null, this is the only way to connect to a Cortex instance |
| `C19` | 124 | debug | Cortex object will be instanciated with url '{…}' |
| `C20` | 126 | debug | Cortex object instanciated |
| `C21` | 131 | debug | Cortex API connection to (URL=" … … |
| `C25` | 133 | error | RESOURCE NOT FOUND - Cortex service is unavailable, is the configuration corr… |
| `C26` | 137 | error | SERVICE UNAVAILABLE - Cortex service is unavailable, is the configuration cor… |
| `C27` | 140 | error | AUTHENTICATION ERROR - Credentials are invalid |
| `C30` | 148 | debug | Getting jobs: … |
| `C35` | 163 | warn | UNKNOWN DATA TYPE - This data type ( … … |
| `C40` | 188 | error | ANALYZER NOT FOUND - This analyzer ( … … |
| `C41` | 190 | debug | Analyzers recovered: … |
| `C42` | 193 | debug | Job instance created |
| `C45` | 205 | debug | JOB sent: … |
| `C46` | 209 | error | … … … |
| `CJ1` | 226 | warn | UNKNOWN DATA TYPE - This data type ( … … |
| `CJ5` | 233 | debug | [ … … … … |
| `CJ6` | 234 | debug | [ … … … … |
| `CJ7` | 235 | debug | [ … … … … |
| `CJ8` | 236 | debug | [ … … … |

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
| `15` | 74 | debug | Job details: … |
| `31` | 84 | info | Job " … … … … … … |
| `16` | 89 | debug | Report details: " … … … |
| `20` | 106 | debug | Event before post processing: … |
| `32` | 113 | info | Job " … … … … |
| `33` | 134 | warn | ARTIFACTS_UNREACHABLE - artifacts of job " … … … |
| `25` | 153 | debug | Event after post processing: … |
| `1` | 171 | debug | Input keywords: … |
| `2` | 172 | debug | Input results: … |
| `30` | 190 | warn | WAIT_NOT_A_NUMBER - wait=" … … |
| `10` | 194 | info | Query is: … |
| `34` | 203 | error | … |

## `dict_utils.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `U1` | 23 | debug | Utils class initiated |
| `U5` | 42 | debug | Event before processing (remove_unwanted_keys_from_dict): {…} |
| `U10` | 49 | debug | Event after processing (remove_unwanted_keys_from_dict): {…} |

## `settings_accessors.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `S26` | 74 | debug | Configuration … … … … … |
| `S27` | 84 | debug | Configuration … … … … |
| `S28` | 99 | debug | Configuration retrieved for the filename ' … … … |
| `S29` | 120 | debug | This account ( … … |
| `S30` | 141 | error | … |
| `S32` | 147 | debug | This instance ID ( … … … |
| `S31` | 169 | error | … |
| `S35` | 177 | debug | This instance ID ( … … … |
| `S40` | 194 | debug | this instance id ( … … … … … |
| `S41` | 204 | warn | Can't recover the setting " … … … … |
| `S45` | 225 | debug | Getting this parameter : thehive_default_instance= … |
| `S46` | 238 | debug | Getting this parameter : thehive_max_cases= … |
| `S50` | 251 | debug | Getting this parameter: thehive_sort_cases= … |
| `S51` | 263 | debug | Getting this parameter: thehive_max_alerts= … |
| `S52` | 276 | debug | Getting this parameter: thehive_sort_alerts= … |
| `S53` | 289 | debug | Getting this parameter: thehive_ttp_catalog_name= … |
| `S54` | 302 | debug | Getting this parameter: thehive_creation_attachment_prefix= … |
| `S57` | 316 | debug | Getting this parameter: thehive_cortex_http_timeout= … |
| `S58` | 329 | debug | Getting this parameter: thehive_creation_max_retry= … |
| `S55` | 342 | debug | Getting this parameter: … |
| `S68` | 360 | debug | Getting this parameter: cortex_job_max_wait= … |
| `S56` | 373 | debug | Getting this parameter: … |
| `S60` | 381 | debug | Found parameter " … … … |
| `S66` | 388 | error | … |
| `S67` | 391 | debug | Parameter " … … … … |

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
| `145` | 103 | warn | Uncompressing Splunk search results file located at {…}... |
| `148` | 133 | error | Error during uncompressing process: {…} |
| `146` | 176 | error | Attachment format isn't supported, given: {…} |

## `ta_thehive_cortex/collection_window.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `SKIP` | 129 | info | input={…} not collected here: {…} |
| `WIN` | 139 | info | input={…} pull={…} window={…}-{…} behind_s={…} … |
| `CKPT` | 148 | error | input={…} pull={…} watermark not saved, the next run collects this window aga… |
| `DONE` | 150 | info | input={…} pull={…} events={…} watermark={…} |
| `KVWAIT` | 158 | warn | input={…} not collected this run: {…}; the watermark waits and the next run c… |
| `KVOPEN` | 163 | warn | input={…} not collected this run: the {…} watermark store could not be opened… |
| `KV` | 166 | warn | input={…} {…}: watermarks kept in the checkpoint directory of this instance o… |

## `ta_thehive_cortex/datatypes.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `THC-7` | 57 | error | no Splunk client carried by the TheHive instance: the datatype lookup cannot … |
| `THC-8` | 68 | error | KV store collection '{…}' is not reachable: {…} |
| `THC-9` | 93 | warn | {} exists but could not be read; the collection will be seeded from TheHive o… |
| `THC-14` | 101 | info | seeding '{}' with {} row(s) migrated from {} |
| `THC-4` | 132 | error | the datatype collection could not be read ({}), refresh aborted to avoid losi… |
| `THC-17` | 149 | error | the migrated rows could not be written to '{}': {} |
| `THC-2` | 166 | debug | Datatypes recovered from TheHive: … |
| `THC-5` | 190 | error | FATAL {} new datatype(s) could not be written to '{}': {} |
| `THC-6` | 197 | error | Could not recover datatypes from TheHive API: … |
| `THC-12` | 265 | warn | API refresh failed ({…}). Falling back to the rows already in the collection. |
| `THC-16` | 273 | error | collection '{…}' is empty, malformed or not readable: {…} |
| `THC-13` | 280 | error | API refresh failed and collection '{…}' holds no datatype. |
| `THC-15` | 289 | debug | dataType_dict built from '{}' ({} datatype(s)) |

## `ta_thehive_cortex/field_mapping.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `THC-91` | 120 | debug | composite fieldvalue detected: {…} |
| `THC-92` | 124 | debug | field: {} enriched with the information {} set to |
| `THC-93` | 135 | warn | composite key '{…}' was NOT mapped: '{…}' is not a known datatype. The raw va… |
| `THC-95` | 149 | debug | key is an observable: {} |
| `THC-96` | 159 | debug | key is a custom field: {}, with type {} |
| `THC-117` | 168 | warn | custom field '{…}' was NOT mapped: type '{…}' is not handled, or value '{…}' … |
| `THC-122` | 237 | error | ttp '{…}' is not in the MITRE catalogue '{…}'; the TTP is dropped rather than… |
| `THC-108` | 250 | debug | ttp was parsed correctly and added to the alert: {} |
| `THC-109` | 255 | debug | ttp already exist, ignoring duplicates: {} |
| `THC-105` | 267 | debug | key is added as another observable (scope is False): {} |
| `THC-106` | 283 | warn | key is used by TheHive as an internal field (scope is False): {}. Key ignored… |
| `THC-90` | 311 | debug | field to process: {…} |

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
| `THAO-20` | 99 | warning | Invalid target type '{…}', defaulting to 'alert' |
| `THAO-25` | 137 | warning | Invalid sighted date value '{…}', defaulting to now(). |
| `THAO-30` | 155 | info | No observables found in current row, skipping. |
| `THAO-35` | 162 | error | Invalid target ID format: '{…}'. Must match ^~[0-9]+$. Skipping this ID. |
| `THAO-40` | 187 | info | Adding observable to {…} {…}: Type={…}, Data={…}, TLP={…}, PAP={…}, IOC={…}, … |
| `THAO-50` | 194 | info | Successfully added observable to {…} {…} |
| `THAO-60` | 199 | warning | Observable already exists in {…} {…} (Status={…}). Skipping. |
| `THAO-70` | 205 | error | Failed to add observable to {…} {…}: {…}{…} |

## `ta_thehive_cortex/modalert_thehive_add_timeline_event_helper.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `THTE-20` | 51 | warning | No case ID resolved for result, skipping. |
| `THTE-30` | 86 | warning | Invalid date format for {…}: {…} |
| `THTE-ERR` | 101 | error | Failed to create timeline event for case {…}: {…} |

## `ta_thehive_cortex/modalert_thehive_common.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `THC-61` | 60 | debug | Row before pre-processing: … |
| `THC-62` | 77 | debug | Row after pre-processing: … |
| `THC-63` | 108 | debug | original sourceRef: {} was cut as it was a string too long (max 128 char). |
| `THC-64` | 116 | debug | sourceRef: {} |
| `THC-86` | 189 | warn | timestamp_field '{…}' missing; falling back to current time |
| `THC-85` | 202 | debug | alert timestamp: {} |
| `THC-87` | 212 | warn | timestamp_field '{…}' holds a non-numeric value ('{…}'); falling back to curr… |
| `THC-80` | 219 | debug | new Timestamp from row: {} |
| `THC-88` | 225 | warn | timestamp_field '{…}' is neither a 10 nor a 13 digit epoch ('{…}'); falling b… |
| `THC-115` | 276 | debug | observables found for an alert: … |
| `THC-116` | 281 | debug | No observable found in current row (sourceRef={…}). |
| `THC-77` | 317 | debug | Append results to description as markdown table |

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
| `140` | 168 | info | Processing attachment of the Splunk search results to the alert... |
| `151` | 187 | error | The search results could not be prepared for attachment: {…} |
| `149` | 198 | via helper | passed as `uploading` to upload_attachment |
| `150` | 198 | via helper | passed as `failed` to upload_attachment |
| `155` | 198 | via helper | passed as `attached` to upload_attachment |
| `160` | 198 | via helper | passed as `not_attached` to upload_attachment |

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
| `132` | 143 | error | TheHive observable update on recent case creation has failed. url={}, data={}… |
| `131` | 157 | info | TheHive case {} was successfully updated with the observable {} on url={} |
| `136` | 170 | warning | Observable already exists in case {} (Status={}). Skipping. url={}, data={} |
| `137` | 178 | error | TheHive observable update on recent case creation has failed. url={}, data={}… |
| `140` | 206 | info | Processing attachment of the Splunk search results to the case... |
| `151` | 225 | error | The search results could not be prepared for attachment: {…} |
| `149` | 236 | via helper | passed as `uploading` to upload_attachment |
| `150` | 236 | via helper | passed as `failed` to upload_attachment |
| `170` | 236 | via helper | passed as `attached` to upload_attachment |
| `180` | 236 | via helper | passed as `not_attached` to upload_attachment |

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

## `ta_thehive_cortex/observable_builder.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `THC-111` | 46 | debug | Processing observable data: {} ({}) |
| `THC-113` | 51 | warn | Observable '{0}' doesn't have any value set (no field '{0}' or '{0}:value' wa… |
| `THC-123` | 76 | warning | Unreadable sighted_at for {…}: '{…}' is not an epoch in seconds or millisecon… |
| `THC-112` | 92 | debug | Multi-value split for {…}: '{…}' -> {…} |

## `ta_thehive_cortex/post_creation.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `133` | 46 | error | TTPS_REFUSED - object {…} was created, but its TTPs were REFUSED: the account… |
| `134` | 57 | error | TTPS_FAILED - object {…} was created, but its TTPs could not be attached: {…}… |
| `138` | 68 | info | Object {…} was successfully updated with the TTPs on url={…} |
| `139` | 73 | error | TTPs update on recent creation has failed. url={…}, {…}, content={…}, ttp={…} |

## `ta_thehive_cortex/timeline_events.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `TH180` | 45 | info | Retrieving cases for timeline extraction... |
| `TH181` | 49 | info | Got {…} cases to check for timeline events. |
| `TH182` | 83 | debug | Fetching timeline for case {…} ({…}) |
| `TH183` | 89 | error | Failed to fetch timeline for case {…}: {…} |
| `TH186` | 104 | debug | Skipping timeline event {…} because kind {…} is not in {…} |
| `TH184` | 140 | info | Processed timeline events for {…} entries so far... |
| `TH200` | 167 | info | Creating custom timeline event for case {…}... |
| `TH201` | 183 | info | Custom timeline event created successfully for case {…} |
| `TH202` | 189 | error | FAILED_TO_CREATE_TIMELINE_EVENT - Error: {…} |

## `ta_thehive_cortex/ttp_catalogue.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `THC-120` | 59 | warn | the MITRE catalogue '{…}' could not be read ({…}); pattern ids are forwarded … |
| `THC-121` | 72 | debug | MITRE catalogue '{…}': {…} pattern id(s) loaded |

## `ta_thehive_cortex/value_codecs.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `THC-118` | 204 | warn | custom field '{…}' has type '{…}', which this add-on does not map; forwarding… |

## `thehive.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `TH1` | 48 | error | MISSING_INSTANCE_ID - No instance ID was given to the script |
| `TH5` | 71 | debug | Connection to Splunk done |
| `TH6` | 73 | debug | Settings recovered |
| `TH10` | 94 | error | Your alert is using the <default> instance ID setting which is empty in your … |
| `TH11` | 113 | debug | Secret present: {…} |
| `TH15` | 137 | debug | TheHive instance will be initialized with a password (not an API key) |
| `TH16` | 155 | debug | TheHive instance will be initialized with an API Key (not a password) |
| `TH20` | 172 | error | WRONG_AUTHENTICATION_TYPE - Authentication type is not one of the expected va… |
| `TH25` | 216 | debug | Settings recovered |
| `TH30` | 225 | error | Your alert is using the <default> instance ID setting which is empty in your … |
| `TH35` | 255 | debug | TheHive instance will be initialized with a password (not an API key) |
| `TH40` | 273 | debug | TheHive instance will be initialized with an API Key (not a password) |
| `TH50` | 290 | error | WRONG_AUTHENTICATION_TYPE - Authentication type is not one of the expected va… |
| `TH2` | 379 | debug | Version is: … |
| `TH119` | 384 | debug | Verification of CA cert path: {…}. Exists? {…} |
| `TH31` | 417 | error | THE_HIVE_AUTHENTICATION - Password AND API Key are null values |
| `TH41` | 423 | debug | TheHive instance is initialized, try a request to {} |
| `TH45` | 434 | error | THE_HIVE_AUTHENTICATION_RESPONSE - Server didn't respond with a valid respons… |
| `TH46` | 441 | debug | Payload content - Header names: … |
| `TH47` | 446 | debug | Payload content - URL: … |
| `TH51` | 451 | debug | TheHive API connection to (URL=" … … |
| `TH60` | 458 | debug | TheHive API connection to (URL=" … … … … |
| `TH85` | 499 | warn | THE_HIVE_CERTIFICATE_FAILED - It seems that the certificate verification fail… |
| `TH90` | 509 | warn | THE_HIVE_HANDHSHAKE_FAILURE - It seems that the SSL handshake failed. A possi… |
| `TH95` | 516 | warn | THE_HIVE_PROXY_AUTHENTICATION_ERROR - It seems that the connection to the pro… |
| `TH100` | 525 | warn | THE_HIVE_PROXY_ERROR - It seems that the connection to the proxy has failed. … |
| `TH111` | 534 | error | … |
| `TH109` | 542 | error | THEHIVE_HTML_RESPONSE_ERROR - The server at {…} returned an HTML page instead… |
| `TH110` | 547 | error | THEHIVE_CONNECTION_ERROR - Error: … … |
| `TH127` | 568 | warn | {…} without {…}: _time taken from the next available date. Fields present: {…} |
| `TH112` | 591 | info | Resolving internal ID for case number {…}... |
| `TH113` | 596 | info | Case number {…} resolved to {…} |
| `TH114` | 599 | warning | No case found with number {…} |
| `TH118` | 602 | error | Error resolving case number {…}: {…} |
| `TH115` | 614 | info | Retrieving instance status... |
| `TH116` | 617 | info | Got instance status successfully |
| `TH117` | 623 | error | FAILED_TO_GET_INSTANCE_STATUS - Error: {…} |
| `TH120` | 644 | info | Retrieving alerts count... |
| `TH121` | 646 | info | Got {…} alerts. Estimated time for processing all events: less than {…} secon… |
| `TH125` | 724 | debug | Event after processing (check_and_reduce_values_size): {…} |
| `TH126` | 731 | info | {…} events have been processed... |
| `TH122` | 742 | debug | thehive - observables: … |
| `TH123` | 748 | debug | thehive - attachments: … |
| `TH124` | 756 | debug | thehive - ttps: … |
| `TH130` | 772 | info | Retrieving cases count... |
| `TH131` | 774 | info | Got {…} cases. Estimated time for processing all events: less than {…} seconds |
| `TH133` | 824 | debug | thehive - observables: … |
| `TH134` | 835 | debug | thehive - attachments: … |
| `TH135` | 846 | debug | thehive - pages: … |
| `TH136` | 857 | debug | thehive - ttps: … |
| `TH137` | 901 | debug | Event after processing (check_and_reduce_values_size): {…} |
| `TH138` | 908 | info | {…} events have been processed... |
| `TH141` | 920 | info | Tasks recovery detected. Got {…} tasks with filters: {…}. |
| `TH142` | 954 | debug | Event after processing (check_and_reduce_values_size): {…} |
| `TH139` | 961 | debug | TheHive - Tasks: … |
| `TH140` | 980 | info | Retrieving observables count... |
| `TH143` | 982 | info | Got {…} observables. Estimated time for processing all events: less than {…} … |
| `TH145` | 1054 | debug | Event after processing (check_and_reduce_values_size): {…} |
| `TH146` | 1060 | info | {…} events have been processed... |
| `TH170` | 1079 | info | Retrieving audit logs count... |
| `TH171` | 1081 | info | Got {…} audit logs. Estimated time for processing all events: less than {…} s… |
| `TH175` | 1142 | debug | Event after processing (check_and_reduce_values_size): {…} |
| `TH176` | 1148 | info | {…} events have been processed... |
| `TH190` | 1167 | info | Retrieving tasks... |
| `TH191` | 1176 | info | Got {…} tasks. |

## `thehive_alerts_cases.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `MI-ERR` | 130 | error | Error: {…} |

## `thehive_audit.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `MI-ERR` | 92 | error | Error: {…} |

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

## `thehive_observables.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `MI-ERR` | 105 | error | Error: {…} |

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
| `1` | 100 | info | Starting tasks collection for interval [from {…} to {…}] using {…} |
| `2` | 119 | info | Successfully indexed {…} tasks. |
| `ERR` | 123 | error | Error during tasks collection: {…} |

## `thehive_timeline.py`

| id | line | level | message |
| :--- | ---: | :--- | :--- |
| `1` | 100 | info | Starting timeline collection for interval [from {…} to {…}] |
| `2` | 118 | info | Successfully indexed {…} timeline events. |
| `ERR` | 122 | error | Error during timeline collection: {…} |

*376 call sites.*

<!-- INVENTAIRE:FIN -->
