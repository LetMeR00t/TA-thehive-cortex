# encoding = utf-8
# Author: Alexandre Demeyer <letmer00t@gmail.com>
#
# Copyright: LGPLv3 (https://www.gnu.org/licenses/lgpl-3.0.txt)
# Feel free to use the code, but please share the changes you've made

__author__ = "Alexandre Demeyer"
__license__ = "LGPLv3"
__version__ = "4.1.0"
__maintainer__ = "Alexandre Demeyer"
__email__ = "letmer00t@gmail.com"

import ta_thehive_cortex_declare

# Standard library imports
import sys

# Local application/library specific imports
from alert_actions_base import ModularAlertBase
import modalert_thehive_add_observables_helper

class AlertActionWorkerthehive_add_observables(ModularAlertBase):

    def __init__(self, ta_name, alert_name):
        super(AlertActionWorkerthehive_add_observables, self).__init__(ta_name, alert_name)

    def validate_params(self):

        self.log_info(f"Received configuration: {str(self.configuration)}")

        if not self.get_param("thehive_instance_id"):
            self.log_error('thehive_instance_id is a mandatory parameter, but its value is None.')
            return False

        if not self.get_param("id_field"):
            self.log_error('id_field is a mandatory parameter, but its value is None.')
            return False

        return True

    def process_event(self, *args, **kwargs):
        status = 0
        try:
            if not self.validate_params():
                return 3
            status = modalert_thehive_add_observables_helper.process_event(self, *args, **kwargs)
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
    exitcode = AlertActionWorkerthehive_add_observables("TA-thehive-cortex", "thehive_add_observables").run(sys.argv)
    sys.exit(exitcode)
