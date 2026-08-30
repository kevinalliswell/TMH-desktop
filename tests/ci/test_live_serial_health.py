"""Regression tests for live serial health and cached-data freshness."""

from __future__ import annotations

import time

import serial

from src.device_clients.base_device import BaseDevice
from src.device_clients.device_manager import DeviceManager


class _ProbeDevice(BaseDevice):
    def __init__(self) -> None:
        super().__init__(
            {
                "PROBE_COM": {
                    "port": "FAKE",
                    "baudrate": 9600,
                    "bytesize": 8,
                    "parity": "N",
                    "stopbits": 1,
                }
            },
            "Probe",
            "PROBE_COM",
        )

    def _read_device_data(self):
        return None


class _FakePort:
    def __init__(self) -> None:
        self.is_open = True

    def close(self) -> None:
        self.is_open = False


def test_serial_availability_turns_true_after_reconnect(monkeypatch):
    port = _FakePort()
    outcomes = iter([serial.SerialException("offline"), port])

    def open_from_sequence(**_kwargs):
        outcome = next(outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr("src.device_clients.base_device.serial.Serial", open_from_sequence)
    device = _ProbeDevice()

    assert device.serial_port_available is False
    assert device.smart_reconnect() is True
    assert device.connection_healthy is True
    assert device.serial_port_available is True


def test_serial_availability_turns_false_when_port_closes(monkeypatch):
    port = _FakePort()
    monkeypatch.setattr(
        "src.device_clients.base_device.serial.Serial",
        lambda **_kwargs: port,
    )
    device = _ProbeDevice()
    assert device.serial_port_available is True

    device.close_serial_port()

    assert device.connection_healthy is False
    assert device.serial_port_available is False


class _CachedDevice:
    serial_port_available = True
    read_interval = 0.1

    def __init__(self, health_age: float, data_age: float) -> None:
        now = time.time()
        self.last_successful_read = now - health_age
        self._last_valid_data = {"timestamp": now - data_age, "weight": 12.3}

    def is_alive(self) -> bool:
        return True

    def get_latest_data(self):
        return self._last_valid_data


def _status_for(device) -> tuple[bool, str, str]:
    manager = DeviceManager()
    manager.register_device("Balance", device)
    return manager.get_connection_status()


def test_connection_status_rejects_stale_cached_data():
    # The serial loop is healthy, but no new stable measurement has replaced
    # the cached payload within the freshness window.
    is_connected, device_names, error_msg = _status_for(_CachedDevice(0.1, 30.0))

    assert is_connected is False
    assert device_names == ""
    assert "通信超时或无新数据" in error_msg


def test_connection_status_accepts_fresh_cached_data():
    is_connected, device_names, error_msg = _status_for(_CachedDevice(0.1, 0.1))

    assert is_connected is True
    assert "电子天平" in device_names
    assert error_msg == ""
