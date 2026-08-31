"""Shutdown safety: no orphan-thread port races, no window closing on a refused stop.

Three defects found reviewing the integration branch:

1. ``BaseDevice.stop()`` closed the serial port even when the join timed out,
   so the GUI thread could close a handle the device thread was still reading —
   pyserial's Windows backend then frees an OVERLAPPED structure the kernel
   still owns, which is a hard crash with no Python traceback.
2. ``AppRuntime.restart()`` rebuilt devices on the same COM ports without
   checking whether the previous generation had actually released them.
3. ``MainWindow.closeEvent`` discarded ``runtime.stop()``'s boolean, so a
   refused shutdown still closed the window while gas kept flowing.
"""
import threading
import time

import pytest

from src.device_clients.base_device import BaseDevice


class _FakeSerial:
    def __init__(self):
        self.is_open = True
        self.closed = False

    def close(self):
        self.closed = True
        self.is_open = False


class _StubDevice(BaseDevice):
    """A BaseDevice whose loop we control, with config loading stubbed out."""

    STOP_JOIN_TIMEOUT = 0.2

    def __init__(self, *, hangs: bool):
        self._hangs = hangs
        self._released = threading.Event()
        threading.Thread.__init__(self, daemon=True)
        self.device_type = "Stub"
        self.comm_type = "COM_STUB"
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self._port_lock = threading.RLock()
        self.serial_port = _FakeSerial()
        self.connection_healthy = True
        self.reconnect_attempt = 3
        self.last_reconnect_time = 0
        self.reconnect_delays = [1, 2, 5, 10, 30]
        import logging

        self.logger = logging.getLogger("stub-device")

    def run(self):
        if self._hangs:
            self._released.wait()  # ignores stop_event on purpose
        else:
            self.stop_event.wait()

    def _read_device_data(self):  # pragma: no cover - abstract stub
        return None

    def release(self):
        self._released.set()


def test_stop_closes_the_port_when_the_thread_exits():
    device = _StubDevice(hangs=False)
    port = device.serial_port
    device.start()

    assert device.stop() is True
    assert port.closed is True
    assert device.serial_port is None


def test_stop_leaves_the_port_alone_when_the_thread_is_still_running():
    device = _StubDevice(hangs=True)
    port = device.serial_port
    device.start()

    try:
        assert device.stop() is False, "未退出的线程必须报告停止失败"
        assert port.closed is False, "线程仍在读写时绝不能关闭串口句柄"
        assert device.serial_port is port
    finally:
        device.release()
        device.join(timeout=2.0)


def test_reconnect_holds_the_port_lock_across_close_and_open():
    """A reader holding the port lock must block a concurrent reconnect."""
    device = _StubDevice(hangs=False)
    swapped = threading.Event()

    def _reconnect():
        device.last_reconnect_time = 0
        device.reconnect_delays = [0]
        device.reconnect_attempt = 0
        device.open_serial_port = lambda: True
        device.smart_reconnect()
        swapped.set()

    with device._port_lock:
        worker = threading.Thread(target=_reconnect, daemon=True)
        worker.start()
        # While the "reader" holds the lock the reconnect cannot swap the port.
        assert swapped.wait(timeout=0.3) is False
        assert device.serial_port is not None

    assert swapped.wait(timeout=2.0) is True
    worker.join(timeout=2.0)


def test_open_does_not_reset_the_reconnect_backoff():
    """Backoff must escalate while a slave stays silent on an openable port."""
    device = _StubDevice(hangs=False)
    device.serial_port = None
    device.port_config = {"port": "COM-STUB"}

    import serial

    original = serial.Serial
    serial.Serial = lambda **kwargs: _FakeSerial()
    try:
        device.reconnect_attempt = 4
        assert device.open_serial_port() is True
        assert device.reconnect_attempt == 4, "端口能打开不代表通信成功，退避不得重置"

        device.note_successful_exchange()
        assert device.reconnect_attempt == 0
    finally:
        serial.Serial = original


# --- runtime / window level -------------------------------------------------


class _Runtime:
    """Minimal AppRuntime stand-in exercising the restart guard."""

    def __init__(self, devices_released):
        from src.services.app_runtime import AppRuntime

        self.stop = lambda: True
        self._devices_released = devices_released
        self.started = False
        self.start = self._start
        self.restart = AppRuntime.restart.__get__(self)
        import logging

        self.logger = logging.getLogger("stub-runtime")

    def _start(self):
        self.started = True
        self._started = True


def test_restart_refuses_to_rebuild_while_ports_are_still_held():
    runtime = _Runtime(devices_released=False)

    assert runtime.restart() is False
    assert runtime.started is False, "孤儿线程仍占端口时不得重建设备"


def test_restart_proceeds_once_ports_are_released():
    runtime = _Runtime(devices_released=True)

    assert runtime.restart() is True
    assert runtime.started is True
