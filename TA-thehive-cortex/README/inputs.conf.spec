[thehive_alerts_cases://<name>]
instance_id = Indicate which instance to use (Set the "id" provided under "Instances"). You can use "<default>" to set automatically the ID to the default set parameter in the configuration page.
type = Indicates which kind of data you want to recover
additional_information = Indicates if you want to recover additional data from the standard logs
extra_data = Indicates which extra data you want to get from alerts or cases
date = Indicates if you want to recover your logs based on the last created or updated date. If you select both, it will process first the last created and then the last updated
max_size_value = Indicates what is the maximum size/length for the values (will be truncated after this value)
fields_removal = Indicates a list of fields, separated by a comma, representing the path in the dictionnary (such as 'field1.subfield1') that should be removed from the original event

[thehive_audit://<name>]
instance_id = Indicate which instance to use (Set the "id" provided under "Instances"). You can use "<default>" to set automatically the ID to the default set parameter in the configuration page.
max_size_value = Indicates what is the maximum size/length for the values (will be truncated after this value)
fields_removal = Indicates a list of fields, separated by a comma, representing the path in the dictionnary (such as 'field1.subfield1') that should be removed from the original event

[thehive_observables://<name>]
instance_id = Indicate which instance to use (Set the "id" provided under "Instances"). You can use "<default>" to set automatically the ID to the default set parameter in the configuration page.
date = Indicates if you want to recover your logs based on the last created or updated date. If you select both, it will process first the last created and then the last updated
max_size_value = Indicates what is the maximum size/length for the values (will be truncated after this value)
fields_removal = Indicates a list of fields, separated by a comma, representing the path in the dictionnary (such as 'field1.subfield1') that should be removed from the original event

[backfill_alerts_cases://<name>]
instance_id = Indicate which instance to use (Set the "id" provided under "Instances"). You can use "<default>" to set automatically the ID to the default set parameter in the configuration page.
type = Indicates which kind of data you want to recover
additional_information = Indicates if you want to recover additional data from the standard logs
extra_data = Indicates which extra data you want to get from alerts or cases
date = Indicates if you want to recover your logs based on the last created or updated date. If you select both, it will process first the last created and then the last updated
max_size_value = Indicates what is the maximum size/length for the values (will be truncated after this value)
fields_removal = Indicates a list of fields, separated by a comma, representing the path in the dictionnary (such as 'field1.subfield1') that should be removed from the original event
backfill_start = Indicates which timestamp in seconds should be used as the start date for the first call
backfill_end = Indicates which timestamp in seconds should be used as the end date (no more log collection will be performed after this date is reached)

[backfill_audit://<name>]
instance_id = Indicate which instance to use (Set the "id" provided under "Instances"). You can use "<default>" to set automatically the ID to the default set parameter in the configuration page.
max_size_value = Indicates what is the maximum size/length for the values (will be truncated after this value)
fields_removal = Indicates a list of fields, separated by a comma, representing the path in the dictionnary (such as 'field1.subfield1') that should be removed from the original event
backfill_start = Indicates which timestamp in seconds should be used as the start date for the first call
backfill_end = Indicates which timestamp in seconds should be used as the end date (no more log collection will be performed after this date is reached)

[backfill_observables://<name>]
instance_id = Indicate which instance to use (Set the "id" provided under "Instances"). You can use "<default>" to set automatically the ID to the default set parameter in the configuration page.
date = Indicates if you want to recover your logs based on the last created or updated date. If you select both, it will process first the last created and then the last updated
max_size_value = Indicates what is the maximum size/length for the values (will be truncated after this value)
fields_removal = Indicates a list of fields, separated by a comma, representing the path in the dictionnary (such as 'field1.subfield1') that should be removed from the original event
backfill_start = Indicates which timestamp in seconds should be used as the start date for the first call
backfill_end = Indicates which timestamp in seconds should be used as the end date (no more log collection will be performed after this date is reached)