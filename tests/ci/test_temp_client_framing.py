from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace

from src.device_clients.temp_client import TempClient
from tmh_comm.protocols.temp_rtu import TempRtuProtocol, _crc16_modbus


class _SplitSerial:
    def __init__(self, chunks: list[bytes]):
        self._chunks = list(chunks)
        self._buffer = b""

    @property
    def in_waiting(self):
        if not self._buffer and self._chunks:
            self._buffer = self._chunks.pop(0)
        return len(self._buffer)

    def reset_input_buffer(self):
        self._buffer = b""

    def reset_output_buffer(self):
        pass

    def write(self, data):
        return len(data)

    def read(self, size):
        data, self._buffer = self._buffer[:size], self._buffer[size:]
        return data


def _temperature_frame(slave_address: int = 0) -> bytes:
    registers = [360, 0, 450, 0, 291, 0, 258, 256, 249]
    body = bytes([slave_address, 0x03, len(registers) * 2])
    for register in registers:
        body += register.to_bytes(2, "big")
    return body + _crc16_modbus(body)


def test_temperature_client_accumulates_split_rtu_response():
    protocol = TempRtuProtocol()
    frame = _temperature_frame()
    serial = _SplitSerial([frame[:5], frame[5:13], frame[13:]])
    client = object.__new__(TempClient)
    client.logger = SimpleNamespace(
        debug=lambda *_args: None,
        warning=lambda *_args: None,
        error=lambda *_args: None,
    )
    client.COMMAND_TIMEOUT = 0.2
    client.RETRY_DELAY = 0.0
    client.slave_address = 0
    client._rtu = protocol
    client.serial_port_context = lambda: nullcontext(serial)
    command = protocol.build_read_all(slave_address=0)

    response = client._send_command(command, retries=1)

    assert protocol.extract_read_all(response, slave_address=0) == frame
