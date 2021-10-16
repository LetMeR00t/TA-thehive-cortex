# SPDX-FileCopyrightText: 2020 2020
#
# SPDX-License-Identifier: Apache-2.0

from solnlib.log import Logs


def get_logger(name):
    return Logs().get_logger(name)
