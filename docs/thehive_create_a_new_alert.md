# Send alerts to TheHive
## introduction
This TA provides an adaptative response/alert action. It takes the result of a search and creates an alert on [TheHive](https://thehive-project.org)
The overall process is as follows:
- search for events & collect observables and custom fields.
- rename splunk fields to match the field names listed in the lookup table thehive_datatypes.csv. If you haven't created it before the first alert, 
it will be initialised with the default datatypes (see [example file](../TA-thehive-cortex/README/thehive_datatypes.csv.sample))
- save your search as an alert.
- set the alert action "thehive_create_a_new_alert": it will create an alert into TheHive.
- you can pass additional info, TLP per observables, custom fields, modify title, description, etc. directly from the results of your search.

## basic example
### simple search results
You may build a search returning some values with fields that are mapped (in lookup/thehive_datatypes.csv) to following default datatypes and optionally one field to group rows (Unique ID).  
By default, the lookup thehive_datatypes.csv contains a mapping for thehive datatypes but you can add your list (see configuration instructions).

For example
    
    | makeresults 
    | eval ip="1.1.1.1", domain="one.one.one.one", comment="dummy alert"
    | fields ip, domain, comment


### create the alert action "TheHive - Create a new alert"
Fill in form fields. If value is not provided, default will be provided if needed.
Provide field names as they are in the results of the search: for example, use mytitle to define alert title from results of the search. The search must return a field 'mytitle' of type string.
Don't use $row.mytitle$ or $mytitle$. Simply field name.

* Alert overall description
    - TheHive instance: one of the instances defined in the kv_store
    - Case Template: A case template to use for imported alerts.
    - Type: The alert type. Defaults to "alert".
    - Source: The alert source. Defaults to "splunk".
    - Unique ID field: A field name that contains a unique identifier specific to the source event. You may use the field value to group artifacts from several rows under the same alert. The value for the field "unique" have to be the same on those rows.
    - Timestamp: A field name that contains a valid timestamp (epoch10 or epoch13 formats are supported). if not provided, default to now() 
    - Title: The title to use for created alerts. You can specify a field name to take the title from the row (see below)
    - Description: The description to send with the alert. You can specify a field name to take the description from the row (see below)
    - Tags: Use single comma-separated string without quotes for multiple tags (ex. "badIP,spam").
    - Scope: you can choose to (option 1) include **only listed** fields in thehive_datatypes.csv or (option 2) include **all fields** (default datatype is 'other')
    - Severity: Change the severity (Low/Medium/High) of the created alert. Default is High
    - TLP: Change the TLP of the created alert. Default is TLP:AMBER
    - PAP: Change the PAP of the created alert. Default is PAP:AMBER

## manage fields to become observable, enrich the alert with inline fields
### Here some precisions
- Values may be empty for some fields; they will be dropped gracefully.
- Only one combination (dataType, data, tags) is kept for the same alert (or having same "Unique ID").
- You may add any other columns, they will be passed as simple elements (other) if you select option "include **all fields** (default datatype is 'other')"
- You can add other observables by listing them in the lookup table first and having corresponding field name(s) in your search.
- You can add custom fields (internal reference) by listing them in the lookup table first and having corresponding field name(s) in your search.

### use fields to provide values for the alert.
In the alert form, you can specify a field name instead of a static string for following parameters:
- Unique ID field: if you provide a field name, the result rows will be grouped under each unique value of this field. For example, if 5 rows have the value "alert1" in field **my_unique** and 3 rows have "alert2", then by mentioning in the form for parameter "unique" the field name "my_unique", the script will create 2 alerts in TH, one with observables from the first 5 rows (deduplicated) and a second with observables from the 3 other rows.
- timestamp: you can provide a field containing a valid timestamp value (epoch10 or epoch13) for example _time
- description: the description of the alert can be taken from the value of a field. Provide field name as it is in results
- title: title of the alert can be taken from the value of a field. Provide field name as it is in results

*IMPORTANT* fields used to set timestamp, description or title are removed from results set and not pushed to TheHive as artifact or custom fields.
If you need to use a field as title and artifact, please create an alias in your search and use one field for the title and another for the aleert artifact. 

### custom TLP per observable
If you want to set az different TLP level than the one set for the alert, append to the field name
    - :R for TLP:RED
    - :A for TLP:AMBER
    - :G for TLP:GREEN
    - :W for TLP:WHITE
    
```
For example if you rename src field as "src:R", then this observable will be set with TLP:RED whatever is the TLP level for the alert.
```
### inline tag(s)
1 additional field can be used inline:
- th_inline_tags: if field **th_inline_tags** exists, then the list of tags (comma-separated string) is added to the observables taken from that row.  
- A final tips to add specific tags to a field is to rename the field to append a text after a ":". For example, to add tag "C2 server" to an ip used this syntax (this option is not possible if you use custom TLP level).

    | rename ip as "ip:C2 server"

In conclusion, the tags attached to each observable are field name, specific tags (using :), inline_tags and tags from the alert form
 
## advanced search results with additional tags

1. add to your search a field th_inline_msg. Tags defined in that field will be attached to each artifact
2. rename the field to include a tag section using the syntax "a dataType:some tag". the field name will be split on first ":" and the second part added to the list of tags

You can try the following dummy search to illustrate this behaviour.

        index=_* | streamstats count as rc |where rc < 4
        |eval "ip:APTxx"="1.1.1."+rc 
        |eval domain="www.malicious.com" 
        |eval th_inline_tags="C2,Campaign1234,PAP:AMBER"
        |eval src=10.11.12.13 |rename src as "src:R"
        |eval playbook = "playbook title"
        |eval hash:md5="f3eef6f636a08768cc4a55f81c29f347"
        |table "ip:APTxx" hash:md5 domain "src:R" playbook th_inline_tags

