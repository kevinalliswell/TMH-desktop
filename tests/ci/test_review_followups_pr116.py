"""Follow-ups from the review of the integration-blocker fixes.

Three gaps the first pass left:

1. The port lock covered open/close/reconnect but not the yielded I/O, and
   BalanceClient guarded its reads and tare with a *different* lock — so a
   reconnect could still swap the handle mid-tare.
2. reduction_start_uncertain was returned alongside the shifted numbers, and
   the report copied them regardless: a knowingly offset result was still
   published as a GB/T figure.
3. Surfacing invalid auxiliary readings as None made the analysis path drop the
   whole row, discarding valid mass data and hiding the invalid CO sample from
   the uncertainty check itself.
"""
import threading
from datetime import datetime, timedelta

import pytest

from src.device_clients.base_device import BaseDevice
from src.services.gb13241_calculator import ReductionCalculator
from src.ui.pages.history_query_page import HistoryQuery


# --- 1. one lock for the port and for device I/O ----------------------------


class _LockOnlyDevice(BaseDevice):
    """Just the locking wiring BaseDevice.__init__ installs, no config/IO."""

    def __init__(self):
        threading.Thread.__init__(self, daemon=True)
        self.device_type = "LockOnly"
        self.stop_event = threading.Event()
        self._port_lock = threading.RLock()
        self.lock = self._port_lock
        self.serial_port = object()
        self.connection_healthy = True
        self.reconnect_attempt = 0
        self.last_reconnect_time = 0
        self.reconnect_delays = [0]
        import logging

        self.logger = logging.getLogger("lock-only-device")

    def _read_device_data(self):  # pragma: no cover - not exercised
        return None


def test_holding_the_device_io_lock_blocks_a_concurrent_reconnect():
    """BalanceClient does its reads and tare under self.lock while the run loop
    calls smart_reconnect(). If those are different locks, reconnect can close
    or replace the handle mid-operation — the exact race this PR removes."""
    device = _LockOnlyDevice()
    device.open_serial_port = lambda: True
    reconnected = threading.Event()

    def _reconnect():
        device.smart_reconnect()
        reconnected.set()

    # Simulate the balance tare / read path, which holds self.lock across I/O.
    with device.lock:
        worker = threading.Thread(target=_reconnect, daemon=True)
        worker.start()
        assert reconnected.wait(timeout=0.3) is False, (
            "持有设备 I/O 锁期间重连仍然发生，串口句柄竞争未被消除"
        )

    assert reconnected.wait(timeout=2.0) is True
    worker.join(timeout=2.0)


def test_base_device_wires_the_two_locks_together(tmp_path):
    """Assert on the real __init__ rather than a hand-built stand-in."""
    import inspect

    source = inspect.getsource(BaseDevice.__init__)
    assert "self.lock = self._port_lock" in source
    assert "threading.RLock()" in source, "必须可重入：I/O 持锁后还会调用 open_serial_port"


# --- 2. uncertain origin suppresses every time-indexed result ----------------


def _series(co_flows):
    started = datetime(2026, 8, 1, 10, 0, 0)
    return [
        {
            "timestamp": started + timedelta(minutes=i),
            "weight": 500.0 - i * 0.5,
            "co_flow": co,
        }
        for i, co in enumerate(co_flows)
    ]


TIME_INDEXED_KEYS = (
    "oxygen_loss_at_30min",
    "oxygen_loss_at_60min",
    "oxygen_loss_at_90min",
    "reduction_degree_at_30min_percent",
    "reduction_degree_at_60min_percent",
    "reduction_degree_at_90min_percent",
    "reduction_index",
    "time_to_40_percent_reduction_min",
    "time_to_50_percent_reduction_min",
    "time_to_70_percent_reduction_min",
    "experiment_duration",
)


def test_uncertain_start_suppresses_every_time_indexed_metric():
    analysis = ReductionCalculator().analyze_experiment_data(
        _series([None] + [4.5] * 120),
        total_iron_content=60.0,
        feo_content=1.0,
    )

    assert analysis["reduction_start_uncertain"] is True
    for key in TIME_INDEXED_KEYS:
        assert analysis[key] is None, f"{key} 依赖起点，起点不确定时不得出具"


def test_endpoint_metrics_survive_an_uncertain_start():
    """Mass endpoints do not depend on the time origin and stay available."""
    analysis = ReductionCalculator().analyze_experiment_data(
        _series([None] + [4.5] * 120),
        total_iron_content=60.0,
        feo_content=1.0,
    )

    assert analysis["initial_weight"] is not None
    assert analysis["final_weight"] is not None
    assert analysis["total_weight_loss"] is not None
    assert analysis["final_reduction_degree"] is not None


def test_certain_start_publishes_time_indexed_metrics():
    analysis = ReductionCalculator().analyze_experiment_data(
        _series([0.0] + [4.5] * 120),
        total_iron_content=60.0,
        feo_content=1.0,
    )

    assert analysis["reduction_start_uncertain"] is False
    assert analysis["reduction_degree_at_30min_percent"] is not None
    assert analysis["experiment_duration"] is not None


# --- 3. invalid auxiliary readings must not drop the row --------------------


@pytest.mark.parametrize(
    "value,expected",
    [(900.0, 900.0), ("900.5", 900.5), (None, None), ("abc", None), (float("nan"), None)],
)
def test_auxiliary_readings_parse_to_a_number_or_none(value, expected):
    assert HistoryQuery._finite_or_none(value) == expected or (
        expected is None and HistoryQuery._finite_or_none(value) is None
    )


def test_invalid_auxiliary_reading_never_raises():
    """The old code called float() inside the weight try-block, so an invalid
    temperature or CO reading discarded the row's valid mass measurement."""
    for bad in (None, "", "n/a", object()):
        assert HistoryQuery._finite_or_none(bad) is None
