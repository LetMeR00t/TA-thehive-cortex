# Copyright 2016 Splunk, Inc.
# SPDX-FileCopyrightText: 2020 2020
#
# SPDX-License-Identifier: Apache-2.0

"""
The Splunk Software Development Kit for Solutions.
"""

from . import (
    acl,
    compression,
    conf_manager,
    credentials,
    file_monitor,
    hec_config,
    ip_math,
    log,
    metadata,
    net_utils,
    orphan_process_monitor,
    pattern,
    server_info,
    splunk_rest_client,
    splunkenv,
    time_parser,
    timer_queue,
    user_access,
    utils,
)

__all__ = [
    "acl",
    "compression",
    "conf_manager",
    "credentials",
    "file_monitor",
    "hec_config",
    "ip_math",
    "log",
    "metadata",
    "net_utils",
    "orphan_process_monitor",
    "pattern",
    "server_info",
    "splunk_rest_client",
    "splunkenv",
    "time_parser",
    "timer_queue",
    "user_access",
    "utils",
]

__version__ = "4.1.0"
