---
name: Report an issue
about: Create a report to help us improve and fix bugs
title: ''
labels: ''
assignees: ''

---

### Request Type
Feature Request

### Work Environment

| Question              | Answer
|---------------------------|--------------------
| OS version (server)       | RedHat 7.9 
| TheHive version / git hash   | Version: 4.0.5-1



### Problem Description
Enhance the integration between TheHive and Splunk Enterprise Security enriching alerts on TheHive with the "Originating Event" from correlation search and with the information about the related "Urgency".
Allow to close Splunk ES Notable Event with the closing of TheHive's case.

### Steps to Reproduce
1. In Splunk ES under CS configure the trigger action in order to create a new alert on theHive starting form the result of the Correlation Search.
2. When a CS shows result in Incident Review the related alert will be open on TheHive
3. Inside the alert's detail on TheHive we do not have the information about the originating event and the related urgency.

### Possible Solutions
Configuring the TA in order to recover the metadata about the Splunk ES CS and sent them to TheHive.
