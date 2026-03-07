
# encoding = utf-8
# Always put this line at the beginning of this file
import ta_thehive_cortex_declare

import os
import sys

from alert_actions_base import ModularAlertBase
import modalert_cortex_run_a_new_job_helper

class AlertActionWorkercortex_run_a_new_job(ModularAlertBase):

    def __init__(self, ta_name, alert_name):
        super(AlertActionWorkercortex_run_a_new_job, self).__init__(ta_name, alert_name)

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

        if not self.get_param("cortex_instance_id"):
            self.log_error('cortex_instance_id is a mandatory parameter, but its value is None.')
            return False

        if not self.get_param("data_field_name"):
            self.log_error('data_field_name is a mandatory parameter, but its value is None.')
            return False

        if not self.get_param("datatype_field_name"):
            self.log_error('datatype_field_name is a mandatory parameter, but its value is None.')
            return False

        if not self.get_param("analyzers"):
            self.log_error('analyzers is a mandatory parameter, but its value is None.')
            return False

        if not self.get_param("tlp"):
            self.log_error('tlp is a mandatory parameter, but its value is None.')
            return False

        if not self.get_param("pap"):
            self.log_error('pap is a mandatory parameter, but its value is None.')
            return False
        return True

    def process_event(self, *args, **kwargs):
        status = 0
        try:
            if not self.validate_params():
                return 3
            status = modalert_cortex_run_a_new_job_helper.process_event(self, *args, **kwargs)
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
    exitcode = AlertActionWorkercortex_run_a_new_job("TA-thehive-cortex", "cortex_run_a_new_job").run(sys.argv)
    sys.exit(exitcode)
