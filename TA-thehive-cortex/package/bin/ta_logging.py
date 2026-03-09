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

# Standard library imports
import logging
import logging.handlers
import os
import sys

# Third-party imports
import splunk.Intersplunk

def setup_logging(name):
    ta_name = "TA-thehive-cortex"
    
    # Robust path detection
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Assuming the script is in etc/apps/TA-thehive-cortex/bin
    # We want etc/../../../var/log/splunk
    base_log_path = os.path.abspath(os.path.join(current_dir, "..", "..", "..", "..", "var", "log", "splunk"))
    
    if not os.path.exists(base_log_path):
        # Fallback to current directory if the expected Splunk structure is not found
        base_log_path = current_dir

    logger_name = ta_name + "_" + name
    logger = logging.getLogger(logger_name)    
    
    LOGGING_FILE_NAME = ta_name + "_" + name + ".log"
    LOGGING_FORMAT = "%(asctime)s %(levelname)-s\t%(module)s:%(lineno)d - %(message)s"
    
    # Set the path to the log file
    log_file_path = os.path.join(base_log_path, LOGGING_FILE_NAME)
    
    # Check if handler already exists to prevent duplicate logs
    if not any(isinstance(h, logging.handlers.RotatingFileHandler) and os.path.abspath(h.baseFilename) == os.path.abspath(log_file_path) for h in logger.handlers):
        try:
            splunk_log_handler = logging.handlers.RotatingFileHandler(log_file_path, mode='a', maxBytes=25000000, backupCount=5) 
            splunk_log_handler.setFormatter(logging.Formatter(LOGGING_FORMAT))
            logger.addHandler(splunk_log_handler)
        except Exception as e:
            # If we cannot write to the log file, at least try to write to stderr
            print(f"CRITICAL: Cannot initialize log handler for {log_file_path}: {str(e)}", file=sys.stderr)
        
    logger.propagate = False
    logger.setLevel(logging.DEBUG)
    return logger
