from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any, Callable

from src.application.dto import CommunicationConfig, DeviceSnapshot, HealthStatus
from src.utils.logger import get_logger


@dataclass
class DeviceBuildResult:
    """Concrete device instances plus the backend source used for each one."""

    devices: dict[str, Any]
    sources: dict[str, str]
    details: dict[str, dict[str, Any]]


@dataclass(frozen=True)
class _DeviceSpec:
    name: str
    external_module_candidates: tuple[str, ...]
    env_module_var: str
    env_path_var: str
    config_class_name: str
    device_class_name: str
    external_builder: Callable[[Any, CommunicationConfig], Any]
    legacy_builder: Callable[[CommunicationConfig], Any]


class DevicePackageRegistry:
    """Builds runtime devices from external packages with legacy fallback."""

    def __init__(self):
        self.logger = get_logger(__name__)
        self._specs = (
            _DeviceSpec(
                name="Balance",
                external_module_candidates=("tmh_device_balance",),
                env_module_var="TMH_DEVICE_BALANCE_MODULE",
                env_path_var="TMH_DEVICE_BALANCE_PATH",
                config_class_name="BalanceDeviceConfig",
                device_class_name="BalanceClient",
                external_builder=self._build_external_balance,
                legacy_builder=self._build_legacy_balance,
            ),
            _DeviceSpec(
                name="Temp",
                external_module_candidates=("tmh_device_temp",),
                env_module_var="TMH_DEVICE_TEMP_MODULE",
                env_path_var="TMH_DEVICE_TEMP_PATH",
                config_class_name="TempDeviceConfig",
                device_class_name="TempControllerClient",
                external_builder=self._build_external_temp,
                legacy_builder=self._build_legacy_temp,
            ),
            _DeviceSpec(
                name="MFC",
                external_module_candidates=("tmh_device_mfc",),
                env_module_var="TMH_DEVICE_MFC_MODULE",
                env_path_var="TMH_DEVICE_MFC_PATH",
                config_class_name="MfcDeviceConfig",
                device_class_name="MfcDevice",
                external_builder=self._build_external_mfc,
                legacy_builder=self._build_legacy_mfc,
            ),
        )

    def build_devices(self, config: CommunicationConfig) -> DeviceBuildResult:
        devices: dict[str, Any] = {}
        sources: dict[str, str] = {}
        details: dict[str, dict[str, Any]] = {}

        for spec in self._specs:
            try:
                device, detail = self._build_external_device(spec, config)
                source = "external-package"
            except Exception as exc:
                self.logger.warning(
                    f"{spec.name} 外部设备包不可用，回退本地实现: {exc}"
                )
                device = spec.legacy_builder(config)
                source = "legacy-local"
                detail = {
                    "backend": source,
                    "module": type(device).__module__,
                    "class_name": type(device).__name__,
                }

            devices[spec.name] = device
            sources[spec.name] = source
            details[spec.name] = detail
            self.logger.info(
                f"{spec.name} 设备装配完成，来源: {source} ({detail.get('module', 'unknown')})"
            )

        return DeviceBuildResult(devices=devices, sources=sources, details=details)

    def _build_external_device(self, spec: _DeviceSpec, config: CommunicationConfig):
        module = self._import_first_available(spec)
        config_cls = getattr(module, spec.config_class_name, None)
        device_cls = getattr(module, spec.device_class_name, None)
        if config_cls is None or device_cls is None:
            raise ImportError(
                f"模块 {module.__name__} 缺少 {spec.config_class_name}/{spec.device_class_name}"
            )
        return (
            spec.external_builder((config_cls, device_cls), config),
            {
                "backend": "external-package",
                "module": module.__name__,
                "module_file": getattr(module, "__file__", ""),
                "class_name": spec.device_class_name,
            },
        )

    def _build_external_balance(self, external_types, config: CommunicationConfig):
        config_cls, device_cls = external_types
        serial_cfg = config.balance.serial
        package_device = device_cls(
            config_cls(
                port=serial_cfg.port,
                baudrate=serial_cfg.baudrate,
                bytesize=serial_cfg.bytesize,
                parity=serial_cfg.parity,
                stopbits=serial_cfg.stopbits,
                timeout=serial_cfg.timeout,
                read_interval=config.performance.data_collection_interval,
            )
        )
        return ExternalBalanceDeviceAdapter(package_device, serial_cfg)

    def _build_external_temp(self, external_types, config: CommunicationConfig):
        config_cls, device_cls = external_types
        serial_cfg = config.temperature.serial
        package_device = device_cls(
            config_cls(
                port=serial_cfg.port,
                baudrate=serial_cfg.baudrate,
                bytesize=serial_cfg.bytesize,
                parity=serial_cfg.parity,
                stopbits=serial_cfg.stopbits,
                timeout=serial_cfg.timeout,
                slave_address=config.temperature.slave_address,
                start_reg=config.temperature.start_reg,
                reg_count=config.temperature.reg_count,
                scale=config.temperature.scale,
                signed_registers=config.temperature.signed_registers,
                temp_channels=list(config.temperature.temp_channels),
                poll_interval=config.performance.data_collection_interval,
            )
        )
        return ExternalTempDeviceAdapter(
            package_device,
            serial_cfg,
            slave_address=config.temperature.slave_address,
        )

    def _build_external_mfc(self, external_types, config: CommunicationConfig):
        config_cls, device_cls = external_types
        serial_cfg = config.mfc.serial
        package_device = device_cls(
            config_cls(
                port=serial_cfg.port,
                baudrate=serial_cfg.baudrate,
                bytesize=serial_cfg.bytesize,
                parity=serial_cfg.parity,
                stopbits=serial_cfg.stopbits,
                timeout=serial_cfg.timeout,
                slave_addresses=dict(config.mfc.slave_addresses),
                flow_scaling=dict(config.mfc.flow_scaling),
                gas_safety_limits=dict(config.mfc.gas_safety_limits),
                poll_interval=config.performance.data_collection_interval,
            )
        )
        return ExternalMfcDeviceAdapter(
            package_device,
            serial_cfg,
            slave_addresses=dict(config.mfc.slave_addresses),
        )

    def _build_legacy_balance(self, config: CommunicationConfig):
        from src.device_clients.balance_client import BalanceClient

        return BalanceClient(_communication_config_to_legacy_raw(config))

    def _build_legacy_temp(self, config: CommunicationConfig):
        from src.device_clients.temp_client import TempClient

        return TempClient(_communication_config_to_legacy_raw(config))

    def _build_legacy_mfc(self, config: CommunicationConfig):
        from src.device_clients.multi_mfc_client import MultiMFCClient

        return MultiMFCClient(_communication_config_to_legacy_raw(config))

    def _import_first_available(self, spec: _DeviceSpec):
        module_candidates = self._resolve_module_candidates(spec)
        extra_path = self._resolve_extra_import_path(spec)
        last_error = None
        path_inserted = False
        try:
            if extra_path is not None:
                sys.path.insert(0, str(extra_path))
                path_inserted = True
                self.logger.info(f"{spec.name} 设备包增加开发路径: {extra_path}")
            for module_name in module_candidates:
                try:
                    return import_module(module_name)
                except Exception as exc:
                    last_error = exc
        finally:
            if path_inserted:
                try:
                    sys.path.remove(str(extra_path))
                except ValueError:
                    pass
        if last_error is None:
            raise ImportError("没有可用的模块候选")
        raise last_error

    def _resolve_module_candidates(self, spec: _DeviceSpec) -> tuple[str, ...]:
        env_module = os.environ.get(spec.env_module_var, "").strip()
        if not env_module:
            return spec.external_module_candidates
        return (env_module, *spec.external_module_candidates)

    def _resolve_extra_import_path(self, spec: _DeviceSpec) -> Path | None:
        raw_path = os.environ.get(spec.env_path_var, "").strip()
        if not raw_path:
            return None
        path = Path(raw_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"{spec.env_path_var} 指向的路径不存在: {path}")
        return path


class ExternalBalanceDeviceAdapter:
    """Compatibility adapter exposing external balance packages to DeviceManager."""

    def __init__(self, device, serial_config):
        self.device = device
        self.port_config = _serial_config_to_dict(serial_config)
        self.model = getattr(device, "model", type(device).__name__)
        self._running = False

    @property
    def serial_port_available(self) -> bool:
        return self.health().is_connected

    def start(self) -> None:
        self.device.start()
        self._running = True

    def stop(self) -> None:
        self.device.stop()
        self._running = False

    def is_alive(self) -> bool:
        return self.health().is_running or self._running

    def health(self) -> HealthStatus:
        if hasattr(self.device, "health"):
            return self.device.health()
        return HealthStatus(is_connected=False, is_running=self._running)

    def get_latest_data(self):
        data = getattr(self.device, "get_latest_data", lambda: None)()
        if data:
            return data
        snapshot = getattr(self.device, "read_snapshot", lambda: None)()
        return _snapshot_to_weight_data(snapshot)

    def get_data(self):
        return self.get_latest_data()

    def send_tare_command(self) -> bool:
        tare_fn = getattr(self.device, "tare", None)
        if tare_fn is None:
            return False
        return bool(tare_fn())


class ExternalTempDeviceAdapter:
    """Compatibility adapter exposing external temp packages to DeviceManager."""

    def __init__(self, device, serial_config, slave_address: int):
        self.device = device
        self.port_config = _serial_config_to_dict(serial_config)
        self.model = getattr(device, "model", type(device).__name__)
        self.slave_address = slave_address
        self._running = False

    @property
    def serial_port_available(self) -> bool:
        return self.health().is_connected

    def start(self) -> None:
        self.device.start()
        self._running = True

    def stop(self) -> None:
        self.device.stop()
        self._running = False

    def is_alive(self) -> bool:
        return self.health().is_running or self._running

    def health(self) -> HealthStatus:
        if hasattr(self.device, "health"):
            return self.device.health()
        return HealthStatus(is_connected=False, is_running=self._running)

    def get_latest_data(self):
        data = getattr(self.device, "get_latest_data", lambda: None)()
        if data:
            return data
        snapshot = getattr(self.device, "read_snapshot", lambda: None)()
        return _snapshot_to_temperature_data(snapshot)

    def get_data(self):
        return self.get_latest_data()


class ExternalMfcDeviceAdapter:
    """Compatibility adapter exposing external MFC packages to DeviceManager."""

    def __init__(self, device, serial_config, slave_addresses: dict[str, int]):
        self.device = device
        self.port_config = _serial_config_to_dict(serial_config)
        self.model = getattr(device, "model", type(device).__name__)
        self.slave_addresses = slave_addresses
        self._running = False

    @property
    def serial_port_available(self) -> bool:
        return self.health().is_connected

    def start(self) -> None:
        self.device.start()
        self._running = True

    def stop(self) -> None:
        self.device.stop()
        self._running = False

    def is_alive(self) -> bool:
        return self.health().is_running or self._running

    def health(self) -> HealthStatus:
        if hasattr(self.device, "health"):
            return self.device.health()
        return HealthStatus(is_connected=False, is_running=self._running)

    @property
    def current_flows(self) -> dict[str, float | None]:
        return {
            gas_name: (data.get("PV") if data else None)
            for gas_name, data in self._all_channel_data().items()
        }

    @property
    def setpoints(self) -> dict[str, float | None]:
        return {
            gas_name: (data.get("SV") if data else None)
            for gas_name, data in self._all_channel_data().items()
        }

    def get_latest_data(self, gas_type: str | None = None):
        all_data = self._all_channel_data()
        if gas_type:
            return all_data.get(gas_type)
        return next((data for data in all_data.values() if data), None)

    def get_data(self, gas_type: str | None = None):
        return self.get_latest_data(gas_type)

    def set_sp_value(self, gas_name: str, flow_value: float) -> bool:
        set_flow = getattr(self.device, "set_flow", None)
        if set_flow is None:
            return False
        return bool(set_flow(gas_name, flow_value))

    def _all_channel_data(self) -> dict[str, dict[str, Any] | None]:
        latest_data_fn = getattr(self.device, "get_latest_data", None)
        if latest_data_fn is not None:
            try:
                data = latest_data_fn(None)
            except TypeError:
                data = latest_data_fn()
            normalized = _normalize_mfc_data(data)
            if normalized:
                return normalized

        snapshot = getattr(self.device, "read_snapshot", lambda: None)()
        normalized = _snapshot_to_mfc_data(snapshot)
        if normalized:
            return normalized

        return {gas_name: None for gas_name in self.slave_addresses}


def _communication_config_to_legacy_raw(config: CommunicationConfig) -> dict[str, Any]:
    return {
        "COM_RS485_MFC": {
            "port": config.mfc.serial.port,
            "baudrate": config.mfc.serial.baudrate,
            "bytesize": config.mfc.serial.bytesize,
            "parity": config.mfc.serial.parity,
            "stopbits": config.mfc.serial.stopbits,
            "timeout": config.mfc.serial.timeout,
        },
        "COM_RS485_TEMP": {
            "port": config.temperature.serial.port,
            "baudrate": config.temperature.serial.baudrate,
            "bytesize": config.temperature.serial.bytesize,
            "parity": config.temperature.serial.parity,
            "stopbits": config.temperature.serial.stopbits,
            "timeout": config.temperature.serial.timeout,
            "slave_address": config.temperature.slave_address,
            "start_reg": config.temperature.start_reg,
            "reg_count": config.temperature.reg_count,
            "TEMP_CHANNELS": list(config.temperature.temp_channels),
            "scale": config.temperature.scale,
            "signed_registers": config.temperature.signed_registers,
        },
        "COM_RS232_Balance": {
            "port": config.balance.serial.port,
            "baudrate": config.balance.serial.baudrate,
            "bytesize": config.balance.serial.bytesize,
            "parity": config.balance.serial.parity,
            "stopbits": config.balance.serial.stopbits,
            "timeout": config.balance.serial.timeout,
        },
        "SAMPLING": {"interval_s": config.sampling.interval_s},
        "PERFORMANCE_CONFIG": {
            "data_collection_interval": config.performance.data_collection_interval,
            "experiment_data_interval": config.performance.experiment_data_interval,
            "heartbeat_timeout": config.performance.heartbeat_timeout,
        },
        "SLAVE_ADDRESS_MFC": dict(config.mfc.slave_addresses),
        "SLAVE_ADDRESS_TEMP": {"TEMP": config.temperature.slave_address},
        "FLOW_SCALING": dict(config.mfc.flow_scaling),
        "GAS_SAFETY_LIMITS": dict(config.mfc.gas_safety_limits),
    }


def _serial_config_to_dict(serial_config) -> dict[str, Any]:
    return {
        "port": serial_config.port,
        "baudrate": serial_config.baudrate,
        "bytesize": serial_config.bytesize,
        "parity": serial_config.parity,
        "stopbits": serial_config.stopbits,
        "timeout": serial_config.timeout,
    }


def _snapshot_to_weight_data(snapshot: DeviceSnapshot | None):
    if snapshot is None:
        return None
    payload = snapshot.payload or {}
    if "weight" in payload:
        return {"timestamp": snapshot.timestamp, "weight": payload.get("weight")}
    return None


def _snapshot_to_temperature_data(snapshot: DeviceSnapshot | None):
    if snapshot is None:
        return None
    payload = snapshot.payload or {}
    if payload:
        data = dict(payload)
        data.setdefault("timestamp", snapshot.timestamp)
        return data
    return None


def _snapshot_to_mfc_data(snapshot: DeviceSnapshot | None) -> dict[str, dict[str, Any] | None]:
    if snapshot is None:
        return {}
    channels = (snapshot.payload or {}).get("channels") or {}
    normalized = {}
    for gas_name, channel in channels.items():
        normalized[gas_name] = {
            "timestamp": snapshot.timestamp,
            "PV": channel.get("pv"),
            "SV": channel.get("sv"),
        }
    return normalized


def _normalize_mfc_data(data: Any) -> dict[str, dict[str, Any] | None]:
    if not isinstance(data, dict):
        return {}

    normalized = {}
    for gas_name, value in data.items():
        if not isinstance(value, dict):
            continue
        pv = value.get("PV", value.get("pv"))
        sv = value.get("SV", value.get("sv"))
        timestamp = value.get("timestamp")
        normalized[gas_name] = {
            "timestamp": timestamp,
            "PV": pv,
            "SV": sv,
        }

    if normalized:
        return normalized

    if "pv" in data or "PV" in data or "sv" in data or "SV" in data:
        return {"MFC": {"timestamp": data.get("timestamp"), "PV": data.get("PV", data.get("pv")), "SV": data.get("SV", data.get("sv"))}}

    return {}
