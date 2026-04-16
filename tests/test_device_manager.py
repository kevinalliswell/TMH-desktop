import pytest
from src.device_clients.device_manager import DeviceManager
from src.device_clients.base_device import BaseDevice


class DummyDevice(BaseDevice):
    """一个假的设备，用于测试"""

    def __init__(self, name, config=None):
        super().__init__(name, config or {})
        self._status = {}

    def start(self):
        self._running = True
        self._status["running"] = True

    def stop(self):
        self._running = False
        self._status["running"] = False

    def send_command(self, cmd, payload=None):
        self._status["last_cmd"] = (cmd, payload)

    def get_status(self):
        return {"running": self._running, **self._status}


@pytest.fixture
def device_manager():
    dm = DeviceManager()
    dev1 = DummyDevice("dev1")
    dev2 = DummyDevice("dev2")
    dm.register_device("dev1", dev1)
    dm.register_device("dev2", dev2)
    return dm


def test_register_and_list(device_manager):
    devices = device_manager.list_devices()
    assert "dev1" in devices and "dev2" in devices


def test_start_stop_device(device_manager):
    device_manager.start_device("dev1")
    assert device_manager.get_status("dev1")["running"] is True

    device_manager.stop_device("dev1")
    assert device_manager.get_status("dev1")["running"] is False


def test_start_stop_all_devices(device_manager):
    device_manager.start_all_devices()
    assert all(s["running"] for s in device_manager.get_all_status().values())

    device_manager.stop_all_devices()
    assert all(not s["running"] for s in device_manager.get_all_status().values())


def test_send_command(device_manager):
    device_manager.start_device("dev1")
    device_manager.send_command("dev1", "TEST_CMD", {"x": 1})
    status = device_manager.get_status("dev1")
    assert status["last_cmd"] == ("TEST_CMD", {"x": 1})


def test_get_status_error_handling(device_manager):
    status = device_manager.get_status("not_exist")
    assert "error" in status
    assert "未找到设备" in status["error"]

