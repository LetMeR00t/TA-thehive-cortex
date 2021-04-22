
# encoding = utf-8
# Always put this line at the beginning of this file
import ta_thehive_cortex_declare

import os
import sys

from alert_actions_base import ModularAlertBase
import modalert_thehive_create_a_new_alert_helper


class AlertActionWorkerthehive_create_a_new_alert(ModularAlertBase):

    def __init__(self, ta_name, alert_name):
        super(AlertActionWorkerthehive_create_a_new_alert, self).__init__(ta_name, alert_name)

    def validate_params(self):
        if not self.get_global_setting("cortex_max_jobs"):
            self.log_error('cortex_max_jobs is a mandatory setup parameter, but its value is None.')
            return False

        if not self.get_global_setting("cortex_sort_jobs"):
            self.log_error('cortex_sort_jobs is a mandatory setup parameter, but its value is None.')
            return False

        if not self.get_global_setting("thehive_max_cases"):
            self.log_error('thehive_max_cases is a mandatory setup parameter, but its value is None.')
            return False

        if not self.get_global_setting("thehive_sort_cases"):
            self.log_error('thehive_sort_cases is a mandatory setup parameter, but its value is None.')
            return False

        if not self.get_global_setting("thehive_max_alerts"):
            self.log_error('thehive_max_alerts is a mandatory setup parameter, but its value is None.')
            return False

        if not self.get_global_setting("thehive_sort_alerts"):
            self.log_error('thehive_sort_alerts is a mandatory setup parameter, but its value is None.')
            return False
        
        if not self.get_param("thehive_instance_id"):
            self.log_error('thehive_instance_id is a mandatory parameter, but its value is None.')
            return False

        if not self.get_param("title"):
            self.log_error('title is a mandatory parameter, but its value is None.')
            return False

        if not self.get_param("scope"):
            self.log_error('scope is a mandatory parameter, but its value is None.')
            return False

        if not self.get_param("severity"):
            self.log_error('severity is a mandatory parameter, but its value is None.')
            return False

        if not self.get_param("tlp_"):
            self.log_error('tlp_ is a mandatory parameter, but its value is None.')
            return False

        if not self.get_param("pap_"):
            self.log_error('pap_ is a mandatory parameter, but its value is None.')
            return False
        return True

    def process_event(self, *args, **kwargs):
        status = 0
        try:
            if not self.validate_params():
                return 3
            status = modalert_thehive_create_a_new_alert_helper.process_event(self, *args, **kwargs)
        except (AttributeError, TypeError) as ae:
            self.log_error("Error: {}. Please double check spelling and also verify that a compatible version of Splunk_SA_CIM is installed.".format(str(ae)))
            return 4
        except Exception as e:
            msg = "Unexpected error: {}."
            if e:
                self.log_error(msg.format(str(e)))
            else:
                import traceback
                self.log_error(msg.format(traceback.format_exc()))
            return 5
        return status


if __name__ == "__main__":
    exitcode = AlertActionWorkerthehive_create_a_new_alert("TA-thehive-cortex", "thehive_create_a_new_alert").run(sys.argv)
    sys.exit(exitcode)
