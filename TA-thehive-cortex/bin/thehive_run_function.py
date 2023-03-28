# encoding = utf-8
# Always put this line at the beginning of this file
import ta_thehive_cortex_declare

import sys

from alert_actions_base import ModularAlertBase
import modalert_thehive_run_function_helper

class AlertActionWorkerthehive_run_function(ModularAlertBase):

    def __init__(self, ta_name, alert_name):
        super(AlertActionWorkerthehive_run_function, self).__init__(ta_name, alert_name)

    def validate_params(self):

        if not self.get_param("thehive_instance_id"):
            self.log_error('thehive_instance_id is a mandatory parameter, but its value is None.')
            return False

        if not self.get_param("name"):
            self.log_error('function name is a mandatory parameter, but its value is None.')
            return False
        return True

    def process_event(self, *args, **kwargs):
        status = 0
        try:
            if not self.validate_params():
                return 3
            status = modalert_thehive_run_function_helper.process_event(self, *args, **kwargs)
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
    exitcode = AlertActionWorkerthehive_run_function("TA-thehive-cortex", "thehive_run_function").run(sys.argv)
    sys.exit(exitcode)
