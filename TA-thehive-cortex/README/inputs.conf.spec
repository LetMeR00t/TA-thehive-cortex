[thehive_alerts_cases://<name>]
instance_id = Indicate which instance to use (Set the "id" provided under "Instances"). You can use "<default>" to set automatically the ID to the default set parameter in the configuration page.
type = Indicates which kind of data you want to recover
additional_information = Indicates if you want to recover additional data from the standard logs
date = Indicates if you want to recover your logs based on the last created or updated date
max_size_value = Indicates what is the maximum size/length for the values (will be truncated after this value)
fields_removal = Indicates a list of fields, separated by a comma, representing the path in the dictionnary (such as 'field1.subfield1') that should be removed from the original event

[thehive_audit://<name>]
instance_id = Indicate which instance to use (Set the "id" provided under "Instances"). You can use "<default>" to set automatically the ID to the default set parameter in the configuration page.
max_size_value = Indicates what is the maximum size/length for the values (will be truncated after this value)
fields_removal = Indicates a list of fields, separated by a comma, representing the path in the dictionnary (such as 'field1.subfield1') that should be removed from the original event

[thehive_observables://<name>]
instance_id = Indicate which instance to use (Set the "id" provided under "Instances"). You can use "<default>" to set automatically the ID to the default set parameter in the configuration page.
date = Indicates if you want to recover your logs based on the last created or updated date
max_size_value = Indicates what is the maximum size/length for the values (will be truncated after this value)
fields_removal = Indicates a list of fields, separated by a comma, representing the path in the dictionnary (such as 'field1.subfield1') that should be removed from the original event