import sqlite3
from pathlib import Path

from src.device_clients.data_handler import DataHandler
from src.device_clients.device_manager import DeviceManager


class StaticTempDevice:
    model = "TEMP-CTRL"
    port_config = {"port": "FAKE-TEMP", "baudrate": 9600}
    slave_address = 1

    def get_data(self):
        return {
            "T1": 900.0,
            "T2": 901.2,
            "T3": 899.8,
            "T4": 900.5,
            "T5": 900.1,
            "T6": 899.9,
            "T7": 900.3,
            "T8": 900.4,
            "T9": 899.7,
        }


class StaticBalanceDevice:
    model = "BALANCE-1200"
    port_config = {"port": "FAKE-BAL", "baudrate": 1200}

    def get_data(self):
        return {"weight": 123.456}


class StaticMFCDevice:
    model = "MQV0020BS"
    port_config = {"port": "FAKE-MFC", "baudrate": 9600}
    slave_addresses = {"N2": 2, "CO": 4}
    current_flows = {"N2": 1.23, "CO": 0.45}
    setpoints = {"N2": 1.50, "CO": 0.50}

    def get_data(self):
        return {"N2": self.current_flows["N2"], "CO": self.current_flows["CO"]}


def _build_status_snapshot():
    manager = DeviceManager()
    manager.register_device("Temp", StaticTempDevice())
    manager.register_device("Balance", StaticBalanceDevice())
    manager.register_device("MFC", StaticMFCDevice())
    return manager.get_status_legacy()


def test_device_manager_builds_standard_frames():
    status = _build_status_snapshot()
    frames = status["frames"]

    assert frames["temperature"].payload["temperatures"]["T1"] == 900.0
    assert frames["weight"].payload["weight"] == 123.456
    assert frames["flows"]["N2"].payload["pv"] == 1.23
    assert frames["flows"]["CO"].payload["sv"] == 0.50


def test_data_handler_persists_standard_frames(tmp_path):
    status = _build_status_snapshot()
    db_path = tmp_path / "device_data.db"
    handler = DataHandler(str(db_path), save_interval=1, experiment_db=object())

    handler._save_data_batch_internal([status])

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM temperature_data")
        assert cursor.fetchone()[0] == 1

        cursor.execute("SELECT COUNT(*) FROM weight_data")
        assert cursor.fetchone()[0] == 1

        cursor.execute("SELECT COUNT(*) FROM flow_data")
        assert cursor.fetchone()[0] == 2

