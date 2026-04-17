from __future__ import annotations

import copy
from typing import Any

from src.infrastructure.repositories import CommConfigRepository, SerialPortDiscovery
from src.utils.logger import get_logger


class CommunicationService:
    """Application service for communication settings and device config drafts."""

    def __init__(self, repository=None, port_discovery=None):
        self.logger = get_logger(__name__)
        self.repository = repository or CommConfigRepository()
        self.port_discovery = port_discovery or SerialPortDiscovery()
        self._settings = self.repository.load_raw()

    @property
    def settings(self) -> dict[str, Any]:
        """Mutable draft settings used by the UI."""
        return self._settings

    @property
    def default_settings(self) -> dict[str, Any]:
        return self.repository.default_settings

    def reload(self) -> dict[str, Any]:
        self._settings = self.repository.load_raw()
        return self._settings

    def save(self) -> None:
        self.repository.save_raw(self._settings)

    def reset_to_defaults(self) -> dict[str, Any]:
        self._settings = copy.deepcopy(self.default_settings)
        return self._settings

    def get_settings(self) -> dict[str, Any]:
        return self._settings

    def get_available_ports(self) -> list[str]:
        return self.port_discovery.list_ports()

    def update_serial_setting(self, device: str, key: str, value: Any) -> None:
        if device not in self._settings:
            raise KeyError(f"设备 {device} 不存在于配置中")
        self._settings[device][key] = value

    def update_mfc_slave_address(self, gas: str, address: int) -> None:
        self._settings.setdefault("SLAVE_ADDRESS_MFC", {})
        self._settings["SLAVE_ADDRESS_MFC"][gas] = address

    def update_temp_slave_address(self, address: int) -> None:
        temp_config = self.get_temp_config()
        temp_config["slave_address"] = address
        self._settings.setdefault("SLAVE_ADDRESS_TEMP", {})
        self._settings["SLAVE_ADDRESS_TEMP"]["TEMP"] = address

    def update_flow_scaling(self, gas: str, scale: float) -> None:
        self._settings.setdefault("FLOW_SCALING", {})
        self._settings["FLOW_SCALING"][gas] = scale

    def update_sampling_interval(self, interval: int) -> None:
        sampling_config = self.get_sampling_config()
        sampling_config["interval_s"] = float(interval)

    def get_mfc_config(self) -> dict[str, Any]:
        return self._settings.get("COM_RS485_MFC", {})

    def get_temp_config(self) -> dict[str, Any]:
        return self._settings.get("COM_RS485_TEMP", {})

    def get_balance_config(self) -> dict[str, Any]:
        return self._settings.get("COM_RS232_Balance", {})

    def get_sampling_config(self) -> dict[str, Any]:
        return self._settings.get("SAMPLING", {})

    def get_mfc_slave_addresses(self) -> dict[str, int]:
        return self._settings.get("SLAVE_ADDRESS_MFC", {})

    def get_flow_scaling(self) -> dict[str, float]:
        return self._settings.get("FLOW_SCALING", {})

    def get_temp_channels(self) -> list[str]:
        return self.get_temp_config().get("TEMP_CHANNELS", [])

