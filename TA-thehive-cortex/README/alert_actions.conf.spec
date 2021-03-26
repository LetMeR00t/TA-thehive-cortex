
[cortex_run_a_new_job]
python.version = python3
param._cam = <json> Active response parameters.
param.cortex_instance_id = <string> Cortex Instance ID. It's a required parameter.
param.data_field_name = <string> Data field name. It's a required parameter. It's default value is data.
param.datatype_field_name = <string> Datatype field name. It's a required parameter. It's default value is datatype.
param.analyzers = <string> Analyzers. It's a required parameter.
param.tlp = <list> TLP:. It's a required parameter. It's default value is 3.
param.pap = <list> PAP:. It's a required parameter. It's default value is 3.

[thehive_create_a_new_alert]
python.version = python3
param.thehive_instance_id = <string> TheHive instance ID. It's a required parameter.
param.case_template = <string> Case Template.
param.type = <string> Type.  It's default value is alert.
param.source = <string> Source.  It's default value is splunk.
param.unique_id_field = <string> Unique ID field.
param.timestamp_field = <string> Timestamp field.
param.title = <string> Title. It's a required parameter. It's default value is $name$.
param.description = <string> Description.  It's default value is Create an alert entry in TheHive with all fields attached as observable.
param.tags = <string> Tags.
param.scope = <list> Scope. It's a required parameter. It's default value is 0.
param.severity = <list> Severity. It's a required parameter. It's default value is 3.
param.tlp_ = <list> TLP:. It's a required parameter. It's default value is 3.
param.pap_ = <list> PAP:. It's a required parameter. It's default value is 3.
param._cam = <json> Active response parameters.

