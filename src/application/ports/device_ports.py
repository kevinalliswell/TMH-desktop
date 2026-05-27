from __future__ import annotations

from typing import Any, Protocol

from src.application.dto.device_snapshot import DeviceSnapshot, HealthStatus, SnapshotBundle


class LifecyclePort(Protocol):
    """Lifecycle and health contract shared by runtime-managed adapters."""

    def start(self) -> None:
        ...

    def stop(self) -> None:
        ...

    def health(self) -> HealthStatus:
        ...


class MfcPort(LifecyclePort, Protocol):
    """Contract for the RS485 MFC bus abstraction."""

    def read_snapshot(self) -> DeviceSnapshot:
        ...

    def set_flow(self, gas_name: str, flow_lpm: float) -> bool:
        ...

    def read_all_flows(self) -> dict[str, dict[str, Any]]:
        ...


class BalancePort(LifecyclePort, Protocol):
    """Contract for the RS232 balance abstraction."""

    def read_snapshot(self) -> DeviceSnapshot:
        ...

    def get_weight(self) -> float | None:
        ...

    def tare(self) -> bool:
        ...


class TemperaturePort(LifecyclePort, Protocol):
    """Contract for the RS485 temperature controller abstraction."""

    def read_snapshot(self) -> DeviceSnapshot:
        ...

    def read_temperatures(self) -> dict[str, float | None]:
        ...

    def get_temperature(self, channel: str) -> float | None:
        ...


class DeviceHubPort(Protocol):
    """Aggregates device adapters into app-facing control and read APIs."""

    def start_all(self) -> None:
        ...

    def stop_all(self) -> None:
        ...

    def get_snapshots(self) -> SnapshotBundle:
        ...

    def get_comm_status(self) -> HealthStatus:
        ...

    def get_connection_status(self) -> tuple[bool, str, str]:
        ...

    def get_all_status(self) -> dict[str, dict[str, Any]]:
        ...

    def set_flow(self, gas_name: str, flow_lpm: float) -> bool:
        ...

    def tare_balance(self) -> bool:
        ...


class SnapshotCollectorPort(Protocol):
    """Supplies normalized snapshot bundles to storage and UI layers."""

    def start(self) -> None:
        ...

    def stop(self) -> None:
        ...

    def latest_snapshot_bundle(self) -> SnapshotBundle:
        ...
