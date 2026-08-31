"""The single clock used for every experiment elapsed-time measurement.

``ExperimentState.experiment_start_time`` and ``stage_start_time`` are written
by the controller and read back by the sampling layer, so both sides must use
the same clock family. A monotonic clock is required: the wall clock can jump
when the lab PC syncs time, which would silently cut a reduction stage short or
extend it.

Importing this instead of calling ``time.monotonic()`` directly keeps that
contract in one place — mixing the two produced persisted experiment durations
of roughly 496708:11:36 instead of 00:00:01.
"""
import time

# Deliberately a module-level name rather than a call: both sides compare and
# invoke the same object, so a divergence is a test failure, not a field bug.
EXPERIMENT_CLOCK = time.monotonic

__all__ = ["EXPERIMENT_CLOCK"]
