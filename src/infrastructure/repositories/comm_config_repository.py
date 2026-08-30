from __future__ import annotations

import copy
import json
import os
from dataclasses import asdict
from typing import Any

import serial.tools.list_ports

from src.application.dto.communication_dto import (
    BalanceCommunicationConfig,
    CommunicationConfig,
    MfcCommunicationConfig,
    PerformanceConfig,
    SamplingConfig,
    SerialPortConfig,
    TemperatureCommunicationConfig,
)
from src.application.ports.repository_ports import CommConfigRepositoryPort
from src.utils.logger import get_logger
from src.utils.path_manager import PathManager


CONFIG_PATH = PathManager.get_config_path("comm_config.json")


class SerialPortDiscovery:
    """Lists available serial ports without coupling the UI to pyserial."""

    def __init__(self):
        self.logger = get_logger(__name__)

    def list_ports(self) -> list[str]:
        try:
            ports = [port.device for port in serial.tools.list_ports.comports()]
            return ports if ports else ["COM1", "COM2", "COM3"]
        except Exception as exc:
            self.logger.error(f"获取可用串口列表失败: {exc}")
            return ["COM1", "COM2", "COM3"]


class CommConfigRepository(CommConfigRepositoryPort):
    """Loads, validates, and saves communication configuration."""

    def __init__(self, config_file: str = CONFIG_PATH):
        self.logger = get_logger(__name__)
        self.config_file = config_file
        self._defaults = {
            "COM_RS485_MFC": {
                "port": "COM1",
                "baudrate": 9600,
                "bytesize": 8,
                "parity": "E",
                "stopbits": 1,
                "timeout": 0.5,
            },
            "COM_RS485_TEMP": {
                "port": "COM2",
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
                "signed_registers": True,
            },
            "COM_RS232_Balance": {
                "port": "COM3",
                "baudrate": 1200,
                "bytesize": 8,
                "parity": "E",
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

    @property
    def default_settings(self) -> dict[str, Any]:
        return copy.deepcopy(self._defaults)

    def load_raw(self) -> dict[str, Any]:
        """Load validated raw settings for UI/service consumption."""
        try:
            if not os.path.exists(self.config_file):
                self.logger.debug(f"配置文件不存在，创建默认配置: {self.config_file}")
                return self._create_default_config()

            self.logger.debug(f"正在加载配置文件: {self.config_file}")
            with open(self.config_file, "r", encoding="utf-8") as file:
                loaded_settings = json.load(file)
            validated = self._validate_and_complete_settings(loaded_settings)
            self.logger.debug("配置加载完成")
            return validated
        except Exception as exc:
            self.logger.error(f"加载配置文件失败: {exc}")
            return self.default_settings

    def load(self) -> CommunicationConfig:
        return self._raw_to_dto(self.load_raw())

    def save_raw(self, settings: dict[str, Any]) -> None:
        """Persist validated raw settings."""
        validated = self._validate_and_complete_settings(copy.deepcopy(settings))
        PathManager.ensure_file_directory_exists(self.config_file)
        with open(self.config_file, "w", encoding="utf-8") as file:
            json.dump(validated, file, indent=4, ensure_ascii=False)
        self.logger.debug(f"配置已保存到: {self.config_file}")

    def save(self, config: CommunicationConfig) -> None:
        self.save_raw(self._dto_to_raw(config))

    def _create_default_config(self) -> dict[str, Any]:
        PathManager.ensure_directory_exists(os.path.dirname(self.config_file))
        with open(self.config_file, "w", encoding="utf-8") as file:
            json.dump(self.default_settings, file, indent=4, ensure_ascii=False)
        return self.default_settings

    def _validate_and_complete_settings(self, loaded_settings: dict[str, Any]) -> dict[str, Any]:
        try:
            for device, default_config in self._defaults.items():
                if device not in loaded_settings:
                    self.logger.warning(f"缺少设备配置，使用默认值: {device}")
                    loaded_settings[device] = copy.deepcopy(default_config)
                elif device.startswith("COM_"):
                    self._validate_com_settings(loaded_settings[device], default_config, device)
                elif device == "SAMPLING":
                    self._validate_sampling_settings(loaded_settings[device], default_config)

            self._validate_top_level_configs(loaded_settings)
            return loaded_settings
        except Exception as exc:
            self.logger.error(f"验证和补充配置失败: {exc}")
            return self.default_settings

    def _validate_com_settings(
        self,
        device_settings: dict[str, Any],
        default_config: dict[str, Any],
        device_key: str = "",
    ) -> None:
        for param in ["baudrate", "bytesize", "parity", "stopbits", "timeout"]:
            if param not in device_settings:
                self.logger.warning(f"缺少串口参数，使用默认值: {param}")
                device_settings[param] = default_config[param]

        if device_key == "COM_RS232_Balance" and device_settings.get("baudrate") != 1200:
            self.logger.warning(
                f"天平波特率不正确，更正为1200 (当前值: {device_settings.get('baudrate')})"
            )
            device_settings["baudrate"] = 1200

    def _validate_sampling_settings(
        self,
        sampling_settings: dict[str, Any],
        default_config: dict[str, Any],
    ) -> None:
        if "interval_s" not in sampling_settings:
            self.logger.warning("缺少采样间隔配置，使用默认值")
            sampling_settings["interval_s"] = default_config["interval_s"]

    def _validate_top_level_configs(self, settings: dict[str, Any]) -> None:
        if "SLAVE_ADDRESS_MFC" not in settings:
            self.logger.warning("缺少MFC从站地址配置，使用默认值")
            settings["SLAVE_ADDRESS_MFC"] = copy.deepcopy(self._defaults["SLAVE_ADDRESS_MFC"])
        if "SLAVE_ADDRESS_TEMP" not in settings:
            self.logger.warning("缺少温控仪表从站地址配置，使用默认值")
            settings["SLAVE_ADDRESS_TEMP"] = copy.deepcopy(self._defaults["SLAVE_ADDRESS_TEMP"])
        if "FLOW_SCALING" not in settings:
            self.logger.warning("缺少流量缩放配置，使用默认值")
            settings["FLOW_SCALING"] = copy.deepcopy(self._defaults["FLOW_SCALING"])
        if "GAS_SAFETY_LIMITS" not in settings:
            self.logger.warning("缺少可燃气体安全上限配置，使用默认值")
            settings["GAS_SAFETY_LIMITS"] = copy.deepcopy(self._defaults["GAS_SAFETY_LIMITS"])
        if "PERFORMANCE_CONFIG" not in settings:
            self.logger.warning("缺少性能配置，使用默认值")
            settings["PERFORMANCE_CONFIG"] = copy.deepcopy(self._defaults["PERFORMANCE_CONFIG"])

        if "COM_RS485_TEMP" in settings:
            temp_config = settings["COM_RS485_TEMP"]
            default_temp = self._defaults["COM_RS485_TEMP"]
            for param in ["slave_address", "start_reg", "reg_count", "scale", "signed_registers"]:
                if param not in temp_config:
                    self.logger.warning(f"缺少温控仪表参数，使用默认值: {param}")
                    temp_config[param] = default_temp[param]
            if "TEMP_CHANNELS" not in temp_config:
                self.logger.warning("缺少温度通道配置，使用默认值")
                temp_config["TEMP_CHANNELS"] = copy.deepcopy(default_temp["TEMP_CHANNELS"])

    def _raw_to_dto(self, raw: dict[str, Any]) -> CommunicationConfig:
        mfc_raw = raw.get("COM_RS485_MFC", {})
        temp_raw = raw.get("COM_RS485_TEMP", {})
        balance_raw = raw.get("COM_RS232_Balance", {})
        return CommunicationConfig(
            mfc=MfcCommunicationConfig(
                serial=self._serial_from_raw(mfc_raw),
                slave_addresses=copy.deepcopy(raw.get("SLAVE_ADDRESS_MFC", {})),
                flow_scaling=copy.deepcopy(raw.get("FLOW_SCALING", {})),
                gas_safety_limits=copy.deepcopy(raw.get("GAS_SAFETY_LIMITS", {})),
            ),
            temperature=TemperatureCommunicationConfig(
                serial=self._serial_from_raw(temp_raw),
                slave_address=int(temp_raw.get("slave_address", raw.get("SLAVE_ADDRESS_TEMP", {}).get("TEMP", 0))),
                start_reg=int(temp_raw.get("start_reg", 0)),
                reg_count=int(temp_raw.get("reg_count", 9)),
                temp_channels=list(temp_raw.get("TEMP_CHANNELS", [])),
                scale=float(temp_raw.get("scale", 0.1)),
                signed_registers=bool(temp_raw.get("signed_registers", True)),
            ),
            balance=BalanceCommunicationConfig(
                serial=self._serial_from_raw(balance_raw),
            ),
            sampling=SamplingConfig(
                interval_s=float(raw.get("SAMPLING", {}).get("interval_s", 1.0)),
            ),
            performance=PerformanceConfig(
                data_collection_interval=float(raw.get("PERFORMANCE_CONFIG", {}).get("data_collection_interval", 0.2)),
                experiment_data_interval=float(raw.get("PERFORMANCE_CONFIG", {}).get("experiment_data_interval", 1.0)),
                heartbeat_timeout=float(raw.get("PERFORMANCE_CONFIG", {}).get("heartbeat_timeout", 5.0)),
            ),
        )

    def _dto_to_raw(self, config: CommunicationConfig) -> dict[str, Any]:
        raw = self.default_settings
        raw["COM_RS485_MFC"] = self._serial_to_raw(config.mfc.serial)
        raw["COM_RS485_TEMP"] = self._serial_to_raw(config.temperature.serial)
        raw["COM_RS485_TEMP"].update(
            {
                "slave_address": config.temperature.slave_address,
                "start_reg": config.temperature.start_reg,
                "reg_count": config.temperature.reg_count,
                "TEMP_CHANNELS": list(config.temperature.temp_channels),
                "scale": config.temperature.scale,
                "signed_registers": config.temperature.signed_registers,
            }
        )
        raw["COM_RS232_Balance"] = self._serial_to_raw(config.balance.serial)
        raw["SAMPLING"] = asdict(config.sampling)
        raw["PERFORMANCE_CONFIG"] = asdict(config.performance)
        raw["SLAVE_ADDRESS_MFC"] = copy.deepcopy(config.mfc.slave_addresses)
        raw["SLAVE_ADDRESS_TEMP"] = {"TEMP": config.temperature.slave_address}
        raw["FLOW_SCALING"] = copy.deepcopy(config.mfc.flow_scaling)
        raw["GAS_SAFETY_LIMITS"] = copy.deepcopy(config.mfc.gas_safety_limits)
        return raw

    def _serial_from_raw(self, raw: dict[str, Any]) -> SerialPortConfig:
        return SerialPortConfig(
            port=str(raw.get("port", "")),
            baudrate=int(raw.get("baudrate", 9600)),
            bytesize=int(raw.get("bytesize", 8)),
            parity=str(raw.get("parity", "N")),
            stopbits=float(raw.get("stopbits", 1)),
            timeout=float(raw.get("timeout", 1.0)),
        )

    def _serial_to_raw(self, config: SerialPortConfig) -> dict[str, Any]:
        return {
            "port": config.port,
            "baudrate": config.baudrate,
            "bytesize": config.bytesize,
            "parity": config.parity,
            "stopbits": config.stopbits,
            "timeout": config.timeout,
        }
