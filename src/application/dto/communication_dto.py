from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SerialPortConfig:
    """Serial communication settings shared by hardware adapters."""

    port: str
    baudrate: int
    bytesize: int
    parity: str
    stopbits: int
    timeout: float


@dataclass
class SamplingConfig:
    """Experiment sampling cadence settings."""

    interval_s: float = 1.0


@dataclass
class PerformanceConfig:
    """Low-level device polling and heartbeat settings."""

    data_collection_interval: float = 0.2
    experiment_data_interval: float = 1.0
    heartbeat_timeout: float = 5.0


@dataclass
class MfcCommunicationConfig:
    """Configuration needed by the multi-device MFC bus package."""

    serial: SerialPortConfig
    slave_addresses: dict[str, int] = field(default_factory=dict)
    flow_scaling: dict[str, float] = field(default_factory=dict)


@dataclass
class TemperatureCommunicationConfig:
    """Configuration needed by the temperature controller package."""

    serial: SerialPortConfig
    slave_address: int = 0
    start_reg: int = 0
    reg_count: int = 9
    temp_channels: list[str] = field(default_factory=list)
    scale: float = 0.1
    signed_registers: bool = False


@dataclass
class BalanceCommunicationConfig:
    """Configuration needed by the balance package."""

    serial: SerialPortConfig


@dataclass
class CommunicationConfig:
    """Top-level communication configuration injected into the app runtime."""

    mfc: MfcCommunicationConfig
    temperature: TemperatureCommunicationConfig
    balance: BalanceCommunicationConfig
    sampling: SamplingConfig = field(default_factory=SamplingConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
