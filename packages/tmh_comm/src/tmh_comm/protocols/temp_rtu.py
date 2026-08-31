from __future__ import annotations

from typing import Dict, Optional


FAULT_REGISTER_VALUES = frozenset({0xFFFF})


def decode_temperature_register(
    raw_value: int,
    *,
    scale: float = 0.1,
    signed: bool = True,
) -> Optional[float]:
    """Decode one 16-bit temperature register, preserving device faults."""
    if raw_value in FAULT_REGISTER_VALUES:
        return None
    value = raw_value
    if signed and raw_value & 0x8000:
        value = raw_value - 0x10000
    return value * scale


def _crc16_modbus(data: bytes) -> bytes:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 0x0001:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return crc.to_bytes(2, byteorder="little")


class TempRtuProtocol:
    """
    Modbus RTU over RS485 for temperature controller.
    Read 9 registers starting at 0x0000.
    """

    def build_read_all(self, *, slave_address: int) -> bytes:
        base = bytes([slave_address, 0x03, 0x00, 0x00, 0x00, 0x09])
        return base + _crc16_modbus(base)

    def parse_read_all(
        self,
        response: bytes,
        *,
        scale: float = 0.1,
        signed_registers: bool = True,
    ) -> Dict[str, Optional[float]]:
        # Expected: [addr, func, byte_count, data..., crc_lo, crc_hi]
        if len(response) < 3:
            return {}
        byte_count = response[2]
        data = response[3 : 3 + byte_count]
        temps: Dict[str, Optional[float]] = {}
        for i in range(0, min(len(data), 18), 2):
            raw = int.from_bytes(data[i : i + 2], byteorder="big", signed=False)
            point = f"T{(i // 2) + 1}"
            temps[point] = decode_temperature_register(
                raw,
                scale=scale,
                signed=signed_registers,
            )
        return temps

    def extract_read_all(self, buf: bytes, *, slave_address: int) -> Optional[bytes]:
        """Locate a CRC-valid 'read holding registers' (func 0x03) response frame for
        the given slave inside ``buf``.

        Skips any leading echo of the request or line noise (some half-duplex RS485
        adapters echo what was transmitted, which would otherwise be mis-parsed as a
        zero-length response). Returns the framed bytes ``[addr,0x03,bc,data,crc]`` or
        ``None`` if no valid frame is present.
        """
        func = 0x03
        for i in range(0, max(0, len(buf) - 4)):
            if buf[i] != slave_address or buf[i + 1] != func:
                continue
            byte_count = buf[i + 2]
            if byte_count == 0:
                continue  # e.g. an echoed request has 0x00 here
            end = i + 3 + byte_count + 2  # data + CRC16
            if end > len(buf):
                continue
            frame = buf[i:end]
            if _crc16_modbus(frame[:-2]) == frame[-2:]:
                return frame
        return None
