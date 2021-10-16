# Copyright 2016 Splunk, Inc.
# SPDX-FileCopyrightText: 2020 2020
#
# SPDX-License-Identifier: Apache-2.0

"""
This module provides some common used patterns.
"""

__all__ = ["Singleton"]


class Singleton(type):
    """
    Singleton meta class

    Usage:

       >>> class Test(object):
       >>>     __metaclass__ = Singleton
       >>>
       >>>     def __init__(self):
       >>>         pass
    """

    def __init__(cls, name, bases, attrs):
        super(Singleton, cls).__init__(name, bases, attrs)
        cls._instance = None

    def __call__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instance
