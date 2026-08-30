"""Regression tests for MFC setpoint acknowledgement and readback checks."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from src.device_clients.multi_mfc_client import MultiMFCClient
from tmh_comm.protocols.mfc_cpl import MfcCplProtocol, _cpl_checksum


def _frame(body: str) -> bytes:
    framed = f"{MfcCplProtocol.STX}{body}{MfcCplProtocol.ETX}"
    return f"{framed}{_cpl_checksum(framed)}\r\n".encode()


class _FakeSerial:
    def __init__(self, responses: list[bytes]) -> None:
        self.is_open = True
        self._responses = iter(responses)
        self._buffer = b""
        self.writes: list[bytes] = []

    @property
    def in_waiting(self) -> int:
        return len(self._buffer)

    def reset_input_buffer(self) -> None:
        self._buffer = b""

    def reset_output_buffer(self) -> None:
        pass

    def write(self, data: bytes) -> int:
        self.writes.append(data)
        self._buffer = next(self._responses, b"")
        return len(data)

    def read(self, size: int) -> bytes:
        data, self._buffer = self._buffer[:size], self._buffer[size:]
        return data


def _config() -> dict:
    return {
        "COM_RS485_MFC": {
            "port": "FAKE-MFC",
            "baudrate": 9600,
            "bytesize": 8,
            "parity": "E",
            "stopbits": 1,
        },
        "SLAVE_ADDRESS_MFC": {"H2": 1},
        "FLOW_SCALING": {"H2": 0.1},
    }


@pytest.fixture
def client_factory(monkeypatch) -> Iterator:
    monkeypatch.setattr(MultiMFCClient, "check_serial_port", lambda self: True)
    monkeypatch.setattr(MultiMFCClient, "_init_serial_connection", lambda self: True)
    clients: list[MultiMFCClient] = []

    def make(responses: list[bytes]) -> MultiMFCClient:
        client = MultiMFCClient(_config())
        client.serial_port = _FakeSerial(responses)
        client.serial_port_available = True
        client._start_command_processor()
        clients.append(client)
        return client

    yield make

    for client in clients:
        client._stop_command_processor()


def test_setpoint_accepts_ok_acknowledgement(client_factory):
    client = client_factory([_frame("0100XOK")])

    assert client.set_sp_value("H2", 2.5, verify=False) is True
    assert client._latest_data["H2"]["SV"] == 2.5


def test_setpoint_rejects_ng_acknowledgement_without_changing_cache(client_factory):
    client = client_factory([_frame("0100XNG")])
    client._latest_data["H2"] = {"SV": 1.0, "PV": 0.8}

    assert client.set_sp_value("H2", 2.5, verify=False) is False
    assert client._latest_data["H2"]["SV"] == 1.0


def test_setpoint_rejects_adapter_command_echo(client_factory):
    protocol = MfcCplProtocol()
    echoed_write = protocol.build_write(
        register_addr=MultiMFCClient.SV_ADDR,
        data_list=[250],
        slave_address=1,
    )
    client = client_factory([echoed_write])

    assert client.set_sp_value("H2", 2.5, verify=False) is False
    assert client._latest_data["H2"] is None


def test_setpoint_verify_reads_back_sv_before_updating_cache(client_factory):
    client = client_factory([_frame("0100XOK"), _frame("0100X20,250")])

    assert client.set_sp_value("H2", 2.5, verify=True) is True
    assert client._latest_data["H2"]["SV"] == 2.5
    assert len(client.serial_port.writes) == 2
    assert b"XRS,1401W,2" in client.serial_port.writes[1]


def test_setpoint_verify_rejects_mismatch_and_preserves_previous_cache(client_factory):
    client = client_factory([_frame("0100XOK"), _frame("0100X20,100")])
    client._latest_data["H2"] = {"SV": 1.0, "PV": 0.8}

    assert client.set_sp_value("H2", 2.5, verify=True) is False
    assert client._latest_data["H2"]["SV"] == 1.0
