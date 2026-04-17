from __future__ import annotations

from dataclasses import dataclass, field
import time

from azbil_temp_controller import AzbilControllerDevice, AzbilRs485Bus, SerialPortSettings

from src.application.dto import DeviceSnapshot, HealthStatus


@dataclass(frozen=True)
class TempDeviceConfig:
    port: str
    baudrate: int
    bytesize: int
    parity: str
    stopbits: int
    timeout: float
    slave_address: int
    start_reg: int
    reg_count: int
    scale: float
    signed_registers: bool
    temp_channels: list[str] = field(default_factory=list)
    poll_interval: float | None = None
    protocol: str = "modbus_rtu"


class TempControllerClient:
    """Compatibility wrapper for the reusable Azbil temperature package."""

    def __init__(self, config: TempDeviceConfig):
        self.config = config
        self.model = "azbil_temp_controller"
        self._bus: AzbilRs485Bus | None = None
        self._device: AzbilControllerDevice | None = None
        self._last_snapshot: DeviceSnapshot | None = None
        self._last_error = ""
        self._last_update_ts: float | None = None

    def start(self) -> None:
        if self._bus is not None and self._device is not None:
            return

        settings = SerialPortSettings(
            port=self.config.port,
            baudrate=self.config.baudrate,
            bytesize=self.config.bytesize,
            parity=self.config.parity,
            stopbits=self.config.stopbits,
            timeout=self.config.timeout,
        )
        bus = AzbilRs485Bus(settings, protocol=self.config.protocol)
        bus.connect()
        self._bus = bus
        self._device = AzbilControllerDevice(bus=bus, slave_id=self.config.slave_address)
        self._last_error = ""

    def stop(self) -> None:
        if self._bus is not None:
            self._bus.close()
        self._bus = None
        self._device = None

    def health(self) -> HealthStatus:
        is_connected = self._bus is not None and self._device is not None
        return HealthStatus(
            is_connected=is_connected,
            is_running=is_connected,
            last_update_ts=self._last_update_ts,
            error_message="" if is_connected else self._last_error,
        )

    def read_snapshot(self) -> DeviceSnapshot:
        if self._device is None:
            return self._disconnected_snapshot(self._last_error or "Temperature bus is not connected")

        try:
            raw_block = self._device.read_words(
                start_address=self.config.start_reg,
                count=self.config.reg_count,
            )
            channels = self.config.temp_channels or [
                f"T{index}" for index in range(1, self.config.reg_count + 1)
            ]
            payload = {}
            for index, raw_value in enumerate(raw_block.words[: len(channels)]):
                payload[channels[index]] = self._decode_value(raw_value)

            snapshot = DeviceSnapshot(
                device_name="Temp",
                device_type="temperature",
                timestamp=time.time(),
                payload=payload,
                is_connected=True,
                is_running=True,
            )
            self._last_snapshot = snapshot
            self._last_update_ts = snapshot.timestamp
            self._last_error = ""
            return snapshot
        except Exception as exc:
            self._last_error = str(exc)
            return self._last_snapshot or self._disconnected_snapshot(str(exc))

    def get_latest_data(self):
        snapshot = self.read_snapshot()
        if not snapshot.payload:
            return None
        data = dict(snapshot.payload)
        data.setdefault("timestamp", snapshot.timestamp)
        return data

    def _decode_value(self, raw_value: int) -> float:
        value = raw_value
        if self.config.signed_registers and raw_value & 0x8000:
            value = raw_value - 0x10000
        return value * self.config.scale

    def _disconnected_snapshot(self, error_message: str) -> DeviceSnapshot:
        return DeviceSnapshot(
            device_name="Temp",
            device_type="temperature",
            timestamp=self._last_update_ts,
            payload=self._last_snapshot.payload if self._last_snapshot else {},
            is_connected=False,
            is_running=False,
            error_message=error_message,
        )

