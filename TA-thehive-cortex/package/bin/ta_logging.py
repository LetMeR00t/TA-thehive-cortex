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
    
    # Standard Splunk log path using SPLUNK_HOME
    splunk_home = os.environ.get("SPLUNK_HOME")
    if splunk_home:
        base_log_path = os.path.join(splunk_home, "var", "log", "splunk")
        app_path = os.path.join(splunk_home, "etc", "apps", ta_name)
    else:
        # Fallback to current directory if SPLUNK_HOME is not set
        base_log_path = os.path.dirname(os.path.abspath(__file__))
        app_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    if not os.path.exists(base_log_path):
        try:
            os.makedirs(base_log_path)
        except:
            base_log_path = os.path.dirname(os.path.abspath(__file__))

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
    
    # Retrieve loglevel from configuration
    loglevel = "INFO"
    try:
        conf_file_default = os.path.join(app_path, "default", "thehive_cortex_settings.conf")
        conf_file_local = os.path.join(app_path, "local", "thehive_cortex_settings.conf")
        
        def get_loglevel_from_file(path):
            if os.path.isfile(path):
                with open(path, "r") as f:
                    in_logging_stanza = False
                    for line in f:
                        line = line.strip()
                        if line == "[logging]":
                            in_logging_stanza = True
                        elif line.startswith("["):
                            in_logging_stanza = False
                        elif in_logging_stanza and line.startswith("loglevel ="):
                            return line.split("=")[1].strip()
            return None

        # Local has priority
        level = get_loglevel_from_file(conf_file_local) or get_loglevel_from_file(conf_file_default)
        if level:
            loglevel = level
    except Exception:
        pass

    logger.setLevel(getattr(logging, loglevel.upper(), logging.INFO))
    return logger
