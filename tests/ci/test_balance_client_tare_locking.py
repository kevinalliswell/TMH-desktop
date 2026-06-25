from __future__ import annotations

import threading

from src.device_clients.balance_client import BalanceClient


class FakeSerial:
    timeout = 0.5
    in_waiting = 0

    def __init__(self):
        self.writes: list[bytes] = []
        self.reset_input_calls = 0
        self.reset_output_calls = 0
        self._reads = [b"A00\r\n+00000.0 G S\r\n"]

    def reset_input_buffer(self) -> None:
        self.reset_input_calls += 1

    def reset_output_buffer(self) -> None:
        self.reset_output_calls += 1

    def write(self, data: bytes) -> int:
        self.writes.append(data)
        self.in_waiting = len(self._reads[0])
        return len(data)

    def read(self, size: int) -> bytes:
        data = self._reads.pop(0)
        self.in_waiting = 0
        return data


def test_tare_command_serial_io_uses_balance_lock(monkeypatch) -> None:
    config = {
        "COM_RS232_Balance": {
            "port": "COM-TEST",
            "baudrate": 1200,
            "bytesize": 8,
            "parity": "N",
            "stopbits": 1,
            "timeout": 1.0,
        },
        "PERFORMANCE_CONFIG": {"data_collection_interval": 0.2},
    }
    monkeypatch.setattr(BalanceClient, "check_serial_port", lambda self: True)
    monkeypatch.setattr("time.sleep", lambda _seconds: None)

    client = BalanceClient(config)
    fake_serial = FakeSerial()
    entered_command = threading.Event()
    release_lock = threading.Event()

    class SerialContext:
        def __enter__(self):
            entered_command.set()
            return fake_serial

        def __exit__(self, exc_type, exc, tb):
            return False

    client.serial_port_context = lambda: SerialContext()

    client.lock.acquire()
    worker = threading.Thread(target=client.send_tare_command)
    worker.start()

    assert entered_command.wait(0.05) is False

    client.lock.release()
    worker.join(timeout=1.0)

    assert not worker.is_alive()
    assert fake_serial.writes == [client._rs232.TARE_CMD]
    assert client.get_latest_weight() == 0.0
