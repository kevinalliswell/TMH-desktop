from __future__ import annotations

from typing import Optional


def _cpl_checksum(input_str: str) -> str:
    byte_str = input_str.encode("utf-8")
    sum_value = sum(byte_str)
    sum_value = (-(sum_value & 0xFF) & 0xFF)
    return f"{sum_value:02X}"


class MfcCplProtocol:
    """
    Modbus-CPL over RS485 (MFC).
    Command example:
      Read:  <STX>0100XRS,1001W,2<ETX>9A\\r\\n
      Write: <STX>0100XWS,1001W,2,65<ETX>FE\\r\\n
    """

    STX = chr(0x02)
    ETX = chr(0x03)

    def build_read(self, *, register_addr: int, num_bytes: int, slave_address: int) -> bytes:
        device_add_str = f"{slave_address:02X}"
        data_add_str = str(register_addr).upper()
        num_bytes_str = str(num_bytes).upper()
        rs_command_str = f"{self.STX}{device_add_str:02}00XRS,{data_add_str}W,{num_bytes_str}{self.ETX}"
        checksum = _cpl_checksum(rs_command_str)
        command = f"{rs_command_str}{checksum:02}" + "\r\n"
        return command.encode()

    def build_write(self, *, register_addr: int, data_list: list[int], slave_address: int) -> bytes:
        device_add_str = f"{slave_address:02X}"
        data_add_str = str(register_addr).upper()
        data_str = ",".join(str(d).upper() for d in data_list)
        ws_command_str = f"{self.STX}{device_add_str:02}00XWS,{data_add_str}W,{data_str}{self.ETX}"
        checksum = _cpl_checksum(ws_command_str)
        command = f"{ws_command_str}{checksum:02}" + "\r\n"
        return command.encode()

    def parse_response(self, response: bytes) -> Optional[float]:
        try:
            cleaned_data = response.strip(b"\x02\x03\r").decode("utf-8")
            parts = cleaned_data.split(",")
            if len(parts) >= 2:
                data_part = parts[1]
                return float(data_part) / 10
            return None
        except Exception:
            return None

