from __future__ import annotations

from collections.abc import Iterator
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

    def _iter_valid_frames(self, response: bytes) -> Iterator[str]:
        """Yield checksum-valid CPL frame bodies found anywhere in ``response``."""
        if not isinstance(response, bytes):
            return

        cursor = 0
        while cursor < len(response):
            stx = response.find(b"\x02", cursor)
            if stx == -1:
                return
            etx = response.find(b"\x03", stx + 1)
            if etx == -1:
                return

            checksum_bytes = response[etx + 1:etx + 3]
            try:
                framed = response[stx:etx + 1].decode("ascii", errors="strict")
                body = response[stx + 1:etx].decode("ascii", errors="strict")
                checksum = checksum_bytes.decode("ascii", errors="strict").upper()
            except UnicodeDecodeError:
                cursor = stx + 1
                continue

            if len(checksum) == 2 and checksum == _cpl_checksum(framed):
                yield body
                cursor = etx + 1
            else:
                # Advance one byte after the bad STX so a nested valid frame
                # remains discoverable when line noise contains framing bytes.
                cursor = stx + 1

    @staticmethod
    def _slave_from_body(body: str) -> Optional[int]:
        try:
            return int(body[:2], 16)
        except (TypeError, ValueError):
            return None

    def parse_write_ack(
        self,
        response: bytes,
        *,
        expected_slave: Optional[int] = None,
    ) -> Optional[bool]:
        """Return the device acknowledgement carried by a CPL write reply.

        ``True`` represents ``OK``, ``False`` represents ``NG``, and ``None``
        means the bytes are not a write acknowledgement (for example, a
        half-duplex adapter echoing the original ``XWS`` command).
        """
        for raw_body in self._iter_valid_frames(response):
            body = raw_body.strip().upper()
            if expected_slave is not None and self._slave_from_body(body) != expected_slave:
                continue
            if not body or "XWS" in body:
                continue

            status = body.rsplit("X", 1)[-1].split(",", 1)[0].strip()
            if status == "OK":
                return True
            if status == "NG":
                return False
        return None

    def parse_response(self, response: bytes, *, expected_slave: int) -> Optional[float]:
        """Return the first valid read value for ``expected_slave`` in a buffer.

        Echoed requests, corrupt frames, and replies from other slaves are
        skipped so a delayed response cannot be attributed to the next gas.
        """
        for raw_body in self._iter_valid_frames(response):
            body = raw_body.strip().upper()
            if self._slave_from_body(body) != expected_slave:
                continue
            if "XRS" in body or "XWS" in body:
                continue
            parts = body.split(",")
            if len(parts) < 2:
                continue
            try:
                return float(parts[1].strip()) / 10
            except ValueError:
                continue
        return None
