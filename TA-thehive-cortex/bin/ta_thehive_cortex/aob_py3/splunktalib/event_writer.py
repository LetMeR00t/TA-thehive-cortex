# SPDX-FileCopyrightText: 2020 Splunk Inc.
#
# SPDX-License-Identifier: Apache-2.0

from future import standard_library

standard_library.install_aliases()
from six import string_types
from builtins import object
import queue
import multiprocessing
import threading
import sys
from collections import Iterable
from splunktalib.common import log


class EventWriter(object):
    def __init__(self, process_safe=False):
        if process_safe:
            self._mgr = multiprocessing.Manager()
            self._event_queue = self._mgr.Queue(1000)
        else:
            self._event_queue = queue.Queue(1000)
        self._event_writer = threading.Thread(target=self._do_write_events)
        self._event_writer.daemon = True
        self._started = False
        self._exception = False

    def start(self):
        if self._started:
            return
        self._started = True

        self._event_writer.start()
        log.logger.info("Event writer started.")

    def tear_down(self):
        if not self._started:
            return
        self._started = False

        self._event_queue.put(None)
        self._event_writer.join()
        log.logger.info("Event writer stopped.")

    def isopen(self):
        return self._started and (not self._exception)

    def write_events(self, events):
        if not self.isopen():
            return False
        if events is None:
            return True
        self._event_queue.put(events)
        return True

    def _do_write_events(self):
        event_queue = self._event_queue
        write = sys.stdout.write
        got_shutdown_signal = False

        while 1:
            try:
                event = event_queue.get(timeout=3)
                if event is not None:
                    if isinstance(event, string_types):
                        write(event.encode("utf-8"))
                    elif isinstance(event, Iterable):
                        for evt in event:
                            write(evt.encode("utf-8"))
                else:
                    log.logger.info("Event writer got tear down signal")
                    got_shutdown_signal = True
            except queue.Empty:
                # We need drain the queue before shutdown
                # timeout means empty for now
                if got_shutdown_signal:
                    log.logger.info("Event writer is going to exit...")
                    break
                else:
                    continue
            except Exception:
                log.logger.exception(
                    "EventWriter encounter exception which may"
                    "cause data loss, queue leftsize={"
                    "}".format(event_queue.qsize())
                )
                self._exception = True
                break

        log.logger.info(
            "Event writer stopped, queue leftsize={}".format(event_queue.qsize())
        )


class EventWriterWithCheckpoint(EventWriter):
    def _do_write_events(self):
        event_queue = self._event_queue
        write = sys.stdout.write
        got_shutdown_signal = False

        while 1:
            try:
                event = event_queue.get(timeout=3)
                if event is not None:
                    # event is a tuple which consists of events and checkpoint
                    # information: (events, checkpoint_tuple)
                    # checkpoint_tuple includes the checkpoint manager obj, key
                    # and value of checkpoint: (ckpt_mgr_obj, key, state)
                    events = event[0]
                    ckpt_tuple = event[1]
                    if isinstance(events, string_types):
                        write(events.encode("utf-8"))
                    elif isinstance(events, Iterable):
                        for evt in events:
                            write(evt.encode("utf-8"))

                    # Update checkpoint after events are sent to stdout to avoid
                    # data loss.
                    if ckpt_tuple and ckpt_tuple[2]:
                        ckpt_tuple[0].update_state(ckpt_tuple[1], ckpt_tuple[2])

                    # Close the checkpoint obj to flush the data in cache to
                    # disk to aviod data duplication if it is teared down
                    if not self._started:
                        ckpt_tuple[0].close()
                else:
                    log.logger.info("Event writer got tear down signal")
                    got_shutdown_signal = True

            except queue.Empty:
                # We need drain the queue before shutdown
                # timeout means empty for now
                if got_shutdown_signal:
                    log.logger.info("Event writer is going to exit...")
                    break
                else:
                    continue
            except Exception:
                log.logger.exception(
                    "EventWriter encounter exception which may"
                    "cause data loss, queue leftsize={"
                    "}".format(event_queue.qsize())
                )
                self._exception = True
                break

        log.logger.info(
            "Event writer stopped, queue leftsize={}".format(event_queue.qsize())
        )
