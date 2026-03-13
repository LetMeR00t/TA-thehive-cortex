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

def initialize_globals(log_content_input="[]"):
    global log_context
    global log_id
    log_context = log_content_input
    log_id = 0

def next_log_id():
    global log_id
    log_id += 1
    str_log_id = str(log_id)
    return "0"*(6-len(str_log_id))+str(log_id)