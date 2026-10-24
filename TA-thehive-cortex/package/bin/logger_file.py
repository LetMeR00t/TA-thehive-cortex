# encoding = utf-8
# Author: Alexandre Demeyer <letmer00t@gmail.com>
#
# Copyright: LGPLv3 (https://www.gnu.org/licenses/lgpl-3.0.txt)
# Feel free to use the code, but please share the changes you've made

"""The add-on's log line format: `[<seq>][<command>-<id>] exec_id=... - msg`.

Split out of `common` (#24); `common` imports it back because the
generated `alert_actions_base.py` reads `from common import LoggerFile`.
"""

# Standard library imports
import logging

# Local application/library specific imports
import globals


class LoggerFile(object):

    def __init__(self, logger=None, command_id="", exec_id=""):
        self._logger = logger
        self.command_id = str(command_id)
        self.exec_id = str(exec_id)

    @property
    def logger(self):
        return self._logger

    def _log(self, type="info", id="?", message=""):
        log_context_val = getattr(globals, "log_context", "[]")
        if log_context_val == "[]":
            log_context = ""
        else:
            log_context = log_context_val
        if type == "debug" and self.logger.getEffectiveLevel() != logging.DEBUG:
            pass
        else:
            try:
                log_id_str = globals.next_log_id()
            except AttributeError:
                log_id_str = "000000"

            exec_prefix = f" exec_id={self.exec_id} -" if self.exec_id else ""

            getattr(self.logger, type)(
                log_context
                + "["
                + log_id_str
                + "]["
                + self.command_id
                + "-"
                + str(id)
                + "]"
                + exec_prefix
                + " "
                + str(message)
            )

    def info(self, id="?", message=""):
        self._log("info", id=id, message=message)

    def warn(self, id="?", message=""):
        self._log("warn", id=str(id) + "-WARNING", message=message)

    # Support potential issues
    def warning(self, id="?", message=""):
        self.warn(id=id, message=message)

    def error(self, id="?", message=""):
        self._log("error", id=str(id) + "-ERROR", message=message)

    def debug(self, id="?", message=""):
        self._log("debug", id=id, message=message)
