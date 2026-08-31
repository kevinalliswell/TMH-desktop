from __future__ import annotations

from src.device_clients.device_manager import DeviceManager
from src.infrastructure.repositories.comm_config_repository import CommConfigRepository


class _Device:
    def __init__(self, data=None):
        self.data = data or {"timestamp": 1.0}
        self.stopped = False

    def get_data(self):
        return self.data

    def stop(self):
        self.stopped = True


def test_device_manager_uses_repository_defaults_for_invalid_config(tmp_path):
    config_path = tmp_path / "comm_config.json"
    config_path.write_text("{invalid", encoding="utf-8")

    manager = DeviceManager(str(config_path))
    repository = CommConfigRepository(str(config_path))

    assert manager.config == repository.default_settings
    assert manager._get_default_config() == repository.default_settings
    assert manager.config["SLAVE_ADDRESS_MFC"] == {
        "H2": 1,
        "N2": 2,
        "CO2": 3,
        "CO": 4,
    }
    assert manager.config["COM_RS232_Balance"]["port"] == "COM3"
    assert manager.config["SAMPLING"]["interval_s"] == 1.0


def test_device_registry_normalizes_names_without_mirrored_state(tmp_path):
    manager = DeviceManager(str(tmp_path / "comm_config.json"))
    mfc = _Device()

    manager.register_device("mfc", mfc)

    assert manager.list_devices() == ["MFC"]
    assert manager.get_device("MFC") is mfc
    assert manager.get_device("mfc") is mfc
    assert manager.multi_mfc is mfc
    assert "multi_mfc" not in manager.__dict__

    manager.unregister_device("MFC")

    assert manager.get_device("mfc") is None
    assert mfc.stopped is True


def test_get_all_status_uses_registry_snapshot_during_mutation(tmp_path):
    manager = DeviceManager(str(tmp_path / "comm_config.json"))
    balance = _Device({"weight": 1.0})

    class _MutatingDevice(_Device):
        def get_data(self):
            manager.unregister_device("balance")
            return super().get_data()

    manager.register_device("temp", _MutatingDevice({"T1": 25.0}))
    manager.register_device("balance", balance)

    status = manager.get_all_status()

    assert set(status) == {"Temp", "Balance"}
    assert status["Temp"]["data"] == {"T1": 25.0}
    assert status["Balance"]["data"] == {"weight": 1.0}
