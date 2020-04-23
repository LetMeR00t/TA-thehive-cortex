![](images/logo.png)

# TA_cortex
This TA allows to **add interaction features** between [Cortex (TheHive project)](https://thehive-project.org/) and Splunk. It allows to retrieve all tasks in Cortex and to execute new tasks from Splunk, from a search or from a predefined dashboard.
All data types work with the exception of "file" because Splunk does not allow to send a file easily.

**Note**:
It's working using Python3 with the official cortex4api library included.
**A support was added to use Python2**. This is not an official library, it's a syntactically-revised version.
In other words, **it's working for Splunk 7.2 and higher versions**.

# What is Cortex ?
If you need more information about TheHive/Cortex project, please [follow this link](https://thehive-project.org/).
You can find the related [Github here](https://github.com/TheHive-Project/Cortex).

# Installation
## Requirements
This application contains all the python libraries to work autonomously.

**However**, a predefined dashboard of the application requires the installation of this application : [Status Indicator - Custom Visualization](https://splunkbase.splunk.com/app/3119/)

You should create a specific user and organization in your Cortex instance to interact with Splunk.

## Configure
Once you've downloaded this application, you must configure your Cortex instance :

1) Go to the Cortex application
2) You need to specify the host/port of your Cortex instance and specify an API key (the user/organization will be determined automatically by Cortex)

![](images/configure.png)

**Note**: You can active a "debug" logging mode to have more information in searches/logs. 

# Use Cases
TODO

# Usage
TODO

# Credits
This app was inspired by [this Splunk app](https://splunkbase.splunk.com/app/4380/)

# Licence
This app TA_cortex is licensed under the GNU Lesser General Public License v3.0.

