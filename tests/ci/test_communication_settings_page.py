import json

from PySide6.QtWidgets import QApplication, QMessageBox

from src.application.services.communication_service import CommunicationService
from src.infrastructure.repositories.comm_config_repository import CommConfigRepository
from src.ui.pages.communication_settings_page import CommunicationSettings


class FixedPortDiscovery:
    def __init__(self, ports):
        self._ports = ports

    def list_ports(self):
        return list(self._ports)


def _settings(temp_port="COM10"):
    return {
        "COM_RS485_MFC": {
            "port": "COM4",
            "baudrate": 9600,
            "bytesize": 8,
            "parity": "E",
            "stopbits": 1,
            "timeout": 0.5,
        },
        "COM_RS485_TEMP": {
            "port": temp_port,
            "baudrate": 9600,
            "bytesize": 8,
            "parity": "N",
            "stopbits": 1,
            "timeout": 1.0,
            "slave_address": 0,
            "start_reg": 0,
            "reg_count": 9,
            "TEMP_CHANNELS": ["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9"],
            "scale": 0.1,
            "signed_registers": False,
        },
        "COM_RS232_Balance": {
            "port": "COM5",
            "baudrate": 1200,
            "bytesize": 8,
            "parity": "N",
            "stopbits": 1,
            "timeout": 1.0,
        },
        "SAMPLING": {"interval_s": 1.0},
        "PERFORMANCE_CONFIG": {
            "data_collection_interval": 0.2,
            "experiment_data_interval": 1.0,
            "heartbeat_timeout": 5.0,
        },
        "SLAVE_ADDRESS_MFC": {"H2": 1, "N2": 2, "CO2": 3, "CO": 4},
        "SLAVE_ADDRESS_TEMP": {"TEMP": 0},
        "FLOW_SCALING": {"H2": 0.1, "N2": 1.0, "CO2": 0.1, "CO": 0.1},
        "GAS_SAFETY_LIMITS": {"H2": 5.0, "CO": 5.0},
    }


def test_save_uses_visible_port_when_original_port_is_unavailable(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    cfg = tmp_path / "comm_config.json"
    cfg.write_text(json.dumps(_settings(), ensure_ascii=False), encoding="utf-8")
    repository = CommConfigRepository(config_file=str(cfg))
    service = CommunicationService(
        repository=repository,
        port_discovery=FixedPortDiscovery(["COM1", "COM2", "COM4", "COM5"]),
    )
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)

    page = CommunicationSettings(communication_service=service)
    temp_port_widget = page._widgets[("COM_RS485_TEMP", "port")]

    assert temp_port_widget.currentText() == "COM1"
    page._on_save()

    saved = json.loads(cfg.read_text(encoding="utf-8"))
    assert saved["COM_RS485_TEMP"]["port"] == "COM1"
    app.processEvents()
