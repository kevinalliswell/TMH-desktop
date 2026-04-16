from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import time


@dataclass
class StandardFrame:
    device_type: str
    model: str
    protocol: str
    bus: str
    payload: Dict[str, Any]
    timestamp: float = field(default_factory=lambda: time.time())
    meta: Dict[str, Any] = field(default_factory=dict)


def build_mfc_frame(
    *,
    model: str,
    gas_type: str,
    pv: Optional[float],
    sv: Optional[float],
    meta: Optional[Dict[str, Any]] = None,
) -> StandardFrame:
    payload = {
        "gas_type": gas_type,
        "pv": pv,
        "sv": sv,
        "unit": "L/min",
    }
    return StandardFrame(
        device_type="mfc",
        model=model,
        protocol="modbus-cpl",
        bus="RS485",
        payload=payload,
        meta=meta or {},
    )


def build_temp_frame(
    *,
    model: str,
    temperatures: Dict[str, Optional[float]],
    meta: Optional[Dict[str, Any]] = None,
) -> StandardFrame:
    payload = {
        "temperatures": temperatures,
        "unit": "C",
    }
    return StandardFrame(
        device_type="temp",
        model=model,
        protocol="modbus-rtu",
        bus="RS485",
        payload=payload,
        meta=meta or {},
    )


def build_balance_frame(
    *,
    model: str,
    weight: Optional[float],
    meta: Optional[Dict[str, Any]] = None,
) -> StandardFrame:
    payload = {
        "weight": weight,
        "unit": "g",
    }
    return StandardFrame(
        device_type="balance",
        model=model,
        protocol="rs232-ascii",
        bus="RS232",
        payload=payload,
        meta=meta or {},
    )

