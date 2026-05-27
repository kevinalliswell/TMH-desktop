from __future__ import annotations

from dataclasses import dataclass, field
import time

from azbil_mfc import COMM_8E1, COMM_8N2, MODE_CONTROL, RS485Bus
from azbil_mfc.client import MQVDevice
from azbil_mfc.registers import RAMAddress

from src.application.dto import DeviceSnapshot, HealthStatus


@dataclass(frozen=True)
class MfcDeviceConfig:
    port: str
    baudrate: int
    bytesize: int
    parity: str
    stopbits: int
    timeout: float
    slave_addresses: dict[str, int] = field(default_factory=dict)
    flow_scaling: dict[str, float] = field(default_factory=dict)
    poll_interval: float | None = None


class MfcDevice:
    """Compatibility wrapper for the reusable Azbil MFC package."""

    def __init__(self, config: MfcDeviceConfig):
        self.config = config
        self.model = "azbil_mfc"
        self._bus: RS485Bus | None = None
        self._devices: dict[str, MQVDevice] = {}
        self._last_data: dict[str, dict[str, float | None]] = {}
        self._last_error = ""
        self._last_update_ts: float | None = None

    def start(self) -> None:
        if self._bus is not None and self._bus.is_open:
            return

        bus = RS485Bus(
            port=self.config.port,
            baudrate=self.config.baudrate,
            comm_format=self._resolve_comm_format(),
            timeout=self.config.timeout,
        )
        bus.open()
        self._bus = bus
        self._devices = {
            gas_name: MQVDevice(bus, address=address)
            for gas_name, address in self.config.slave_addresses.items()
        }
        self._last_error = ""

    def stop(self) -> None:
        if self._bus is not None:
            self._bus.close()
        self._bus = None
        self._devices = {}

    def health(self) -> HealthStatus:
        is_connected = self._bus is not None and self._bus.is_open
        return HealthStatus(
            is_connected=is_connected,
            is_running=is_connected,
            last_update_ts=self._last_update_ts,
            error_message="" if is_connected else self._last_error,
        )

    def read_snapshot(self) -> DeviceSnapshot:
        if self._bus is None or not self._bus.is_open or not self._devices:
            return self._disconnected_snapshot(self._last_error or "MFC bus is not connected")

        try:
            channel_payload = {}
            for gas_name, device in self._devices.items():
                sp, pv = device.read_pv_sp()
                channel_payload[gas_name] = {
                    "pv": self._apply_scaling(gas_name, pv),
                    "sv": self._apply_scaling(gas_name, sp),
                }

            snapshot = DeviceSnapshot(
                device_name="MFC",
                device_type="flow",
                timestamp=time.time(),
                payload={"channels": channel_payload},
                is_connected=True,
                is_running=True,
            )
            self._last_data = {
                gas_name: {
                    "timestamp": snapshot.timestamp,
                    "PV": values.get("pv"),
                    "SV": values.get("sv"),
                }
                for gas_name, values in channel_payload.items()
            }
            self._last_update_ts = snapshot.timestamp
            self._last_error = ""
            return snapshot
        except Exception as exc:
            self._last_error = str(exc)
            return self._disconnected_snapshot(str(exc))

    def get_latest_data(self, gas_name: str | None = None):
        if not self._last_data:
            snapshot = self.read_snapshot()
            channels = snapshot.payload.get("channels") or {}
            self._last_data = {
                name: {
                    "timestamp": snapshot.timestamp,
                    "PV": values.get("pv"),
                    "SV": values.get("sv"),
                }
                for name, values in channels.items()
            }

        if gas_name is None:
            return dict(self._last_data)
        return self._last_data.get(gas_name)

    def set_flow(self, gas_name: str, flow_value: float) -> bool:
        if self._bus is None or not self._bus.is_open:
            return False

        address = self.config.slave_addresses.get(gas_name)
        device = self._devices.get(gas_name)
        if address is None or device is None:
            return False

        try:
            raw_value = self._to_raw_value(gas_name, flow_value)
            self._bus.write_registers(address, RAMAddress.OPERATION_MODE, [MODE_CONTROL])
            self._bus.write_registers(address, RAMAddress.SP_CURRENT, [raw_value])
            now = time.time()
            channel_data = self._last_data.setdefault(gas_name, {})
            channel_data.update(
                {
                    "timestamp": now,
                    "PV": channel_data.get("PV"),
                    "SV": flow_value,
                }
            )
            self._last_update_ts = now
            return True
        except Exception as exc:
            self._last_error = str(exc)
            return False

    def _apply_scaling(self, gas_name: str, raw_value: int | float) -> float:
        scaling = self.config.flow_scaling.get(gas_name, 0.1)
        return round(float(raw_value) * scaling, 2)

    def _to_raw_value(self, gas_name: str, flow_value: float) -> int:
        scaling = self.config.flow_scaling.get(gas_name, 0.1)
        if scaling == 0:
            raise ValueError(f"Invalid flow scaling for {gas_name}: {scaling}")
        return int(float(flow_value) / scaling * 10)

    def _resolve_comm_format(self) -> int:
        parity = (self.config.parity or "").upper()
        if parity == "E" and int(self.config.stopbits) == 1:
            return COMM_8E1
        return COMM_8N2

    def _disconnected_snapshot(self, error_message: str) -> DeviceSnapshot:
        return DeviceSnapshot(
            device_name="MFC",
            device_type="flow",
            timestamp=self._last_update_ts,
            payload={
                "channels": {
                    gas_name: {
                        "pv": values.get("PV"),
                        "sv": values.get("SV"),
                    }
                    for gas_name, values in self._last_data.items()
                }
            },
            is_connected=False,
            is_running=False,
            error_message=error_message,
        )
