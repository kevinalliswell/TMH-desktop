from __future__ import annotations

from typing import Dict, Optional


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

    def parse_read_all(self, response: bytes, *, scale: float = 0.1) -> Dict[str, Optional[float]]:
        # Expected: [addr, func, byte_count, data..., crc_lo, crc_hi]
        if len(response) < 3:
            return {}
        byte_count = response[2]
        data = response[3 : 3 + byte_count]
        temps: Dict[str, Optional[float]] = {}
        for i in range(0, min(len(data), 18), 2):
            raw = int.from_bytes(data[i : i + 2], byteorder="big", signed=False)
            temps[f"T{(i // 2) + 1}"] = raw * scale
        return temps

