"""Safety net for serial protocol parsing (review issues #56 / #69 / #70).

Three kinds of tests live in the safety-net files:

- Plain tests pin behavior that is CORRECT today so upcoming refactors cannot
  regress it silently.
- Tests named ``*_KNOWN_BUG_<issue>`` pin current WRONG behavior on purpose,
  because today's API cannot express the expected behavior; the fix PR for
  that issue must update them to assert the corrected behavior.
- ``xfail(strict=True)`` tests encode the EXPECTED behavior for an open
  finding. They fail today by design; the fix PR must remove the marker
  (``strict=True`` turns an unexpected pass into a hard failure, so a stale
  marker cannot linger).
"""
import pytest

from src.device_clients.multi_mfc_client import MultiMFCClient
from tmh_comm.protocols.mfc_cpl import MfcCplProtocol, _cpl_checksum
from tmh_comm.protocols.temp_rtu import TempRtuProtocol, _crc16_modbus

cpl = MfcCplProtocol()
rtu = TempRtuProtocol()


def make_temp_frame(addr: int, raw_registers) -> bytes:
    body = bytes([addr, 0x03, len(raw_registers) * 2])
    for raw in raw_registers:
        body += int(raw).to_bytes(2, "big")
    return body + _crc16_modbus(body)


def cpl_reply(slave: int, raw_value: int, checksum: bytes | None = None) -> bytes:
    # Real device frame: <STX>ADDR,VALUE<ETX><checksum>\r\n. The checksum is
    # computed the same way the protocol's build_* commands do (STX..ETX
    # inclusive) so this fixture remains a genuinely valid frame once #69 adds
    # checksum validation; pass an explicit checksum to corrupt it.
    framed = "\x02" + f"{slave:02X},{raw_value}" + "\x03"
    if checksum is None:
        checksum = _cpl_checksum(framed).encode()
    return framed.encode() + checksum + b"\r\n"


# --- temp_rtu.parse_read_all -------------------------------------------------


def test_temp_parse_positive_values_baseline():
    temps = rtu.parse_read_all(make_temp_frame(0, [360, 0, 450]), scale=0.1)
    assert temps["T1"] == 36.0
    assert temps["T2"] == 0.0
    assert temps["T3"] == 45.0


@pytest.mark.xfail(strict=True, reason="#70: registers decoded unsigned, -0.5C (0xFFFB) becomes 6553.1C")
def test_temp_parse_negative_value_expected_signed():
    temps = rtu.parse_read_all(make_temp_frame(0, [0xFFFB]), scale=0.1)
    assert temps["T1"] == pytest.approx(-0.5)


@pytest.mark.xfail(strict=True, reason="#70: burnout code 0xFFFF must surface as a fault, not 6553.5C")
def test_temp_parse_burnout_code_is_not_a_temperature():
    value = rtu.parse_read_all(make_temp_frame(0, [0xFFFF]), scale=0.1)["T1"]
    assert value is None or abs(value) < 1000.0


# --- mfc_cpl.parse_response --------------------------------------------------


def test_cpl_parse_valid_reply_baseline():
    # Guards the 43c58ef framing fix: a fully framed device reply must parse.
    assert cpl.parse_response(cpl_reply(1, 480), expected_slave=1) == 48.0


def test_cpl_parse_echoed_command_returns_none_baseline():
    # A half-duplex adapter echoes the request; it must never parse as a value.
    echo = cpl.build_read(register_addr=1001, num_bytes=2, slave_address=1)
    assert cpl.parse_response(echo, expected_slave=1) is None


def test_cpl_parse_rejects_wrong_slave():
    late_reply_from_slave_1 = cpl_reply(1, 480)
    assert cpl.parse_response(late_reply_from_slave_1, expected_slave=2) is None


def test_cpl_parse_rejects_bad_checksum():
    corrupted = cpl_reply(1, 480, checksum=b"ZZ")
    assert cpl.parse_response(corrupted, expected_slave=1) is None


def test_cpl_parse_skips_echo_before_valid_reply():
    echo = cpl.build_read(register_addr=1001, num_bytes=2, slave_address=1)
    response = echo + cpl_reply(1, 480)

    assert cpl.parse_response(response, expected_slave=1) == 48.0


def test_cpl_parse_skips_late_reply_from_another_slave():
    response = cpl_reply(1, 480) + cpl_reply(2, 520)

    assert cpl.parse_response(response, expected_slave=2) == 52.0


def test_mfc_executor_does_not_complete_on_echo_or_wrong_slave():
    client = object.__new__(MultiMFCClient)
    client._cpl = cpl
    command = cpl.build_read(register_addr=1001, num_bytes=2, slave_address=2)
    invalid_prefix = command + cpl_reply(1, 480)

    assert client._has_matching_response(command, invalid_prefix) is False
    assert client._has_matching_response(
        command,
        invalid_prefix + cpl_reply(2, 520),
    ) is True
