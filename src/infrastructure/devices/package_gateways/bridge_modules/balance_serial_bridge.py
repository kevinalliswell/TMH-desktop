from __future__ import annotations

from dataclasses import dataclass
import time

from balance_serial import BalanceClient as PackageBalanceClient
from balance_serial import PortSettings, create_protocol

from src.application.dto import DeviceSnapshot, HealthStatus


@dataclass(frozen=True)
class BalanceDeviceConfig:
    port: str
    baudrate: int
    bytesize: int
    parity: str
    stopbits: int
    timeout: float
    read_interval: float | None = None
    protocol: str = "gs_cpa"
    auto_continuous_output: bool = True


class BalanceClient:
    """Compatibility wrapper for the reusable balance package."""

    def __init__(self, config: BalanceDeviceConfig):
        self.config = config
        self.model = "balance_serial"
        self._client: PackageBalanceClient | None = None
        self._last_snapshot: DeviceSnapshot | None = None
        self._last_error = ""
        self._last_update_ts: float | None = None

    def start(self) -> None:
        if self._client is not None and self._client.is_open:
            return

        protocol = create_protocol(
            self.config.protocol,
            auto_continuous_output=self.config.auto_continuous_output,
        )
        settings = PortSettings(
            port=self.config.port,
            baudrate=self.config.baudrate,
            bytesize=self.config.bytesize,
            parity=self.config.parity,
            stopbits=self.config.stopbits,
            timeout=self.config.timeout,
        )
        client = PackageBalanceClient(settings, protocol)
        client.open()
        client.initialize_device()
        self._client = client
        self._last_error = ""

    def stop(self) -> None:
        if self._client is None:
            return
        self._client.close()
        self._client = None

    def health(self) -> HealthStatus:
        is_connected = self._client is not None and self._client.is_open
        return HealthStatus(
            is_connected=is_connected,
            is_running=is_connected,
            last_update_ts=self._last_update_ts,
            error_message="" if is_connected else self._last_error,
        )

    def read_snapshot(self) -> DeviceSnapshot:
        if self._client is None or not self._client.is_open:
            return self._disconnected_snapshot(self._last_error or "Balance port is not open")

        try:
            message = self._client.read_reading(stable_only=False)
            if message is None or message.weight is None:
                return self._last_snapshot or self._empty_snapshot()

            snapshot = DeviceSnapshot(
                device_name="Balance",
                device_type="weight",
                timestamp=time.time(),
                payload={"weight": message.weight},
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
        if snapshot.payload.get("weight") is None:
            return None
        return {
            "timestamp": snapshot.timestamp,
            "weight": snapshot.payload.get("weight"),
        }

    def tare(self) -> bool:
        if self._client is None or not self._client.is_open:
            return False
        try:
            self._client.send_tare()
            return True
        except Exception as exc:
            self._last_error = str(exc)
            return False

    def _empty_snapshot(self) -> DeviceSnapshot:
        return DeviceSnapshot(
            device_name="Balance",
            device_type="weight",
            timestamp=self._last_update_ts,
            payload={},
            is_connected=self._client is not None and self._client.is_open,
            is_running=self._client is not None and self._client.is_open,
            error_message=self._last_error,
        )

    def _disconnected_snapshot(self, error_message: str) -> DeviceSnapshot:
        return DeviceSnapshot(
            device_name="Balance",
            device_type="weight",
            timestamp=self._last_update_ts,
            payload=self._last_snapshot.payload if self._last_snapshot else {},
            is_connected=False,
            is_running=False,
            error_message=error_message,
        )

