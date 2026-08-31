"""The controller and DataHandler must share one clock family.

PR #55 moved the controller's experiment/stage timing to ``time.monotonic()`` so
an NTP correction could not cut a reduction stage short. DataHandler kept
subtracting that value from a ``time.time()`` sample timestamp, so every
persisted ``experiment_duration`` became the wall-clock/monotonic offset —
around ``496708:11:36`` instead of ``00:00:01``.

Both per-PR test suites passed: the persistence tests fabricate the state
machine with a wall-clock start time, so they were self-consistent and blind to
the mismatch. This test asserts the cross-module contract itself.
"""
import time
from types import SimpleNamespace

from src.controllers.experiment_controller import ExperimentController
from src.device_clients.data_handler import DataHandler
from src.domain.experiment.clock import EXPERIMENT_CLOCK


def test_both_sides_take_the_clock_from_the_domain_layer():
    """A shared clock is the actual contract; neither side may drift alone."""
    assert ExperimentController._clock is EXPERIMENT_CLOCK
    assert DataHandler._elapsed_clock is EXPERIMENT_CLOCK
    assert EXPERIMENT_CLOCK is time.monotonic


def _handler_with_start(monotonic_start):
    handler = DataHandler.__new__(DataHandler)
    handler._sm = SimpleNamespace(
        get_state=lambda: SimpleNamespace(experiment_start_time=monotonic_start)
    )
    return handler


def test_duration_is_measured_against_the_monotonic_start():
    started = time.monotonic() - 61
    assert _handler_with_start(started)._format_experiment_duration() == "00:01:01"


def test_duration_is_blank_before_an_experiment_starts():
    assert _handler_with_start(0.0)._format_experiment_duration() == ""


def test_duration_does_not_explode_when_start_is_monotonic():
    """The regression: a wall-clock subtraction yields ~496708 hours."""
    duration = _handler_with_start(time.monotonic())._format_experiment_duration()

    hours = int(duration.split(":")[0])
    assert hours == 0, f"实验时长被算成 {duration}，说明两侧时钟不一致"


def test_duration_never_goes_negative():
    future_start = time.monotonic() + 30
    assert _handler_with_start(future_start)._format_experiment_duration() == "00:00:00"
