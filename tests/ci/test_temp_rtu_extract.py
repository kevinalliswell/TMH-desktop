"""CI tests for TempRtuProtocol.extract_read_all — robust Modbus frame location.

Guards against the real-machine failure mode where a half-duplex RS485 adapter
echoes the request (or emits line noise), which the old naive parser accepted and
turned into an all-None reading.
"""
from tmh_comm.protocols.temp_rtu import TempRtuProtocol, _crc16_modbus

rtu = TempRtuProtocol()
REGS = [360, 0, 450, 0, 291, 0, 258, 256, 249]  # *0.1 -> 36.0, 0, 45.0, ...


def make_frame(addr: int, regs) -> bytes:
    body = bytes([addr, 0x03, len(regs) * 2])
    for r in regs:
        body += int(r).to_bytes(2, "big")
    return body + _crc16_modbus(body)


def test_extract_clean_valid_frame():
    frame = make_frame(0, REGS)
    assert rtu.extract_read_all(frame, slave_address=0) == frame


def test_extract_skips_echoed_request():
    echo = rtu.build_read_all(slave_address=0)  # what a half-duplex adapter echoes
    frame = make_frame(0, REGS)
    extracted = rtu.extract_read_all(echo + frame, slave_address=0)
    assert extracted == frame
    temps = rtu.parse_read_all(extracted, scale=0.1)
    assert temps["T1"] == 36.0 and temps["T3"] == 45.0
    assert round(temps["T9"], 3) == 24.9


def test_extract_skips_leading_noise():
    frame = make_frame(0, REGS)
    assert rtu.extract_read_all(b"\xff\x00\xaa\x55" + frame, slave_address=0) == frame


def test_extract_rejects_bad_crc():
    frame = make_frame(0, REGS)[:-2] + b"\x00\x00"
    assert rtu.extract_read_all(frame, slave_address=0) is None


def test_extract_rejects_wrong_address():
    frame = make_frame(0, REGS)
    assert rtu.extract_read_all(frame, slave_address=1) is None


def test_extract_handles_nonzero_address():
    frame = make_frame(5, REGS)
    assert rtu.extract_read_all(frame, slave_address=5) == frame
