# encoding = utf-8
# Author: Alexandre Demeyer <letmer00t@gmail.com>
#
# Copyright: LGPLv3 (https://www.gnu.org/licenses/lgpl-3.0.txt)
# Feel free to use the code, but please share the changes you've made

__author__ = "Alexandre Demeyer"
__license__ = "LGPLv3"
__version__ = "4.0.0"
__maintainer__ = "Alexandre Demeyer"
__email__ = "letmer00t@gmail.com"

import ta_thehive_cortex_declare

# Standard library imports
import sys

# Local application/library specific imports
from alert_actions_base import ModularAlertBase
import modalert_cortex_run_a_new_job_helper

class AlertActionWorkercortex_run_a_new_job(ModularAlertBase):

    def __init__(self, ta_name, alert_name):
        super(AlertActionWorkercortex_run_a_new_job, self).__init__(ta_name, alert_name)

    def validate_params(self):

        # ⚠️ cortex_max_jobs/cortex_sort_jobs and thehive_max_cases/
        # thehive_sort_cases/thehive_max_alerts/thehive_sort_alerts used to be
        # required here. None of the six is read by this action's own code
        # path (submitting one job): they size and sort the JOB/CASE/ALERT
        # LISTING dashboards, and `common.Settings` already falls back to a
        # working default (100, "-createdAt", ...) when a global setting is
        # absent -- see `getCortexJobsMax` and friends. Blocking job creation
        # on a dashboard-only setting a user never touched was a false
        # mandatory; see Gitea #32.
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
