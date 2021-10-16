# Copyright 2016 Splunk, Inc.
# SPDX-FileCopyrightText: 2020 2020
#
# SPDX-License-Identifier: Apache-2.0

"""
Orphan process monitor.
"""

import os
import threading
import time

__all__ = ["OrphanProcessChecker", "OrphanProcessMonitor"]


class OrphanProcessChecker(object):
    """Orphan process checker.

    Only work for Linux platform. On Windows platform, is_orphan
    is always False and there is no need to do this monitoring on
    Windows.

    :param callback: (optional) Callback for orphan process.
    :type callback: ``function``
    """

    def __init__(self, callback=None):
        if os.name == "nt":
            self._ppid = 0
        else:
            self._ppid = os.getppid()
        self._callback = callback

    def is_orphan(self):
        """Check process is orphan.

        For windows platform just return False.

        :returns: True for orphan process else False
        :rtype: ``bool``
        """

        if os.name == "nt":
            return False
        return self._ppid != os.getppid()

    def check_orphan(self):
        """Check if the process becomes orphan.

        If the process becomes orphan then call callback function
        to handle properly.

        :returns: True for orphan process else False
        :rtype: ``bool``
        """

        res = self.is_orphan()
        if res and self._callback:
            self._callback()
        return res


class OrphanProcessMonitor(object):
    """Orpan process monitor.

    Check if process become orphan in background thread per
    iterval and call callback if process become orphan.

    :param callback: Callback for orphan process monitor.
    :type callback: ``function``
    :param interval: (optional) Interval to monitor.
    :type interval: ``integer``
    """

    def __init__(self, callback, interval=1):
        self._checker = OrphanProcessChecker(callback)
        self._thr = threading.Thread(target=self._do_monitor)
        self._thr.daemon = True
        self._started = False
        self._interval = interval

    def start(self):
        """
        Start orphan process monitor.
        """

        if self._started:
            return
        self._started = True

        self._thr.start()

    def stop(self):
        """
        Stop orphan process monitor.
        """

        joinable = self._started
        self._started = False
        if joinable:
            self._thr.join(timeout=1)

    def _do_monitor(self):
        while self._started:
            if self._checker.check_orphan():
                break

            for _ in range(self._interval):
                if not self._started:
                    break
                time.sleep(1)
