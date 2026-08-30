#!/usr/bin/env python3
"""Field commissioning comm self-test for TMH devices (MFC / Temp / Balance).

Reuses the project's tmh_comm protocols so it exercises the exact wire frames the
application uses. Useful for diagnosing real hardware before/while running the app
(e.g. confirming a COM port, finding a Modbus slave address, or checking the balance
stream). Defaults are read from configs/comm_config.json; any value can be overridden.

Examples:
  # Test every device using the saved comm_config.json ports/params:
  python scripts/comm_selftest.py --device all

  # Test the MFC bus on a specific port:
  python scripts/comm_selftest.py --device mfc --port COM3

  # Scan Modbus addresses 0..16 for the temperature controller:
  python scripts/comm_selftest.py --device temp --port COM3 --scan

  # Listen to the balance stream:
  python scripts/comm_selftest.py --device balance --port COM3 --baud 1200
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
# Allow running straight from a source checkout without installing tmh_comm.
sys.path.insert(0, os.path.join(_ROOT, "packages", "tmh_comm", "src"))

import serial  # noqa: E402  (after sys.path tweak)
from tmh_comm.protocols.mfc_cpl import MfcCplProtocol  # noqa: E402
from tmh_comm.protocols.temp_rtu import TempRtuProtocol, _crc16_modbus  # noqa: E402
from tmh_comm.protocols.balance_rs232 import BalanceRs232Protocol  # noqa: E402

_PARITY = {"N": serial.PARITY_NONE, "E": serial.PARITY_EVEN, "O": serial.PARITY_ODD}
MFC_PV_ADDR = 1206
MFC_SV_ADDR = 1401


def _hex(b: bytes) -> str:
    return b.hex(" ")


def load_config() -> dict:
    path = os.path.join(_ROOT, "configs", "comm_config.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        print(f"[warn] could not read {path}: {exc}")
        return {}


def open_serial(port: str, baud: int, parity: str, timeout: float = 0.4,
                retries: int = 3) -> serial.Serial:
    """Open the port, retrying briefly to ride out transient USB-adapter glitches
    (some CH34x adapters intermittently fail with 'device not functioning')."""
    last_exc = None
    for attempt in range(retries):
        try:
            return serial.Serial(
                port=port, baudrate=baud, bytesize=serial.EIGHTBITS,
                parity=_PARITY.get(parity.upper(), serial.PARITY_NONE),
                stopbits=serial.STOPBITS_ONE, timeout=timeout,
            )
        except serial.SerialException as exc:
            last_exc = exc
            if attempt < retries - 1:
                time.sleep(0.5)
    raise last_exc


def _read_until(ser: serial.Serial, terminator: bytes, min_len: int, timeout: float) -> bytes:
    start = time.time()
    buf = b""
    while time.time() - start < timeout:
        n = ser.in_waiting
        if n:
            buf += ser.read(n)
            if (terminator and terminator in buf) or len(buf) >= min_len:
                break
        time.sleep(0.01)
    return buf


# --------------------------------------------------------------------------- MFC
def test_mfc(port: str, baud: int, parity: str, addresses: dict, scaling: dict) -> bool:
    cpl = MfcCplProtocol()
    print(f"\n=== MFC @ {port} {baud} 8{parity}1 ===")
    ok_any = False
    with open_serial(port, baud, parity) as ser:
        for gas, slave in addresses.items():
            results = {}
            for label, reg in (("PV", MFC_PV_ADDR), ("SV", MFC_SV_ADDR)):
                cmd = cpl.build_read(register_addr=reg, num_bytes=2, slave_address=slave)
                ser.reset_input_buffer(); ser.reset_output_buffer()
                ser.write(cmd)
                time.sleep(0.05)
                resp = _read_until(ser, b"\r\n", 64, 1.0)
                val = cpl.parse_response(resp, expected_slave=slave) if resp else None
                scaled = round(val * scaling.get(gas, 0.1), 2) if val is not None else None
                results[label] = scaled
                time.sleep(0.05)
            status = "OK" if results.get("PV") is not None else "NO RESPONSE"
            if results.get("PV") is not None:
                ok_any = True
            print(f"  {gas:>3} (addr {slave}): PV={results.get('PV')}  SV={results.get('SV')} L/min   [{status}]")
    print(f"  => MFC {'PASS' if ok_any else 'FAIL'}")
    return ok_any


# -------------------------------------------------------------------------- Temp
def _temp_probe(ser: serial.Serial, rtu: TempRtuProtocol, addr: int):
    cmd = rtu.build_read_all(slave_address=addr)
    ser.reset_input_buffer(); ser.reset_output_buffer()
    ser.write(cmd)
    time.sleep(0.08)
    resp = _read_until(ser, b"", 23, 0.4)
    if len(resp) >= 5 and resp[0] == addr and _crc16_modbus(resp[:-2]) == resp[-2:]:
        if resp[1] == 0x03 and len(resp) >= 3 and resp[2] == 0x12:
            return "data", resp
        if resp[1] & 0x80:
            return "error", resp
    return "", resp


def test_temp(port: str, baud: int, parity: str, address: int, scale: float, scan: bool) -> bool:
    rtu = TempRtuProtocol()
    print(f"\n=== Temp @ {port} {baud} 8{parity}1 ===")
    addrs = list(range(0, 17)) if scan else [address]
    found = False
    with open_serial(port, baud, parity) as ser:
        for addr in addrs:
            kind, resp = _temp_probe(ser, rtu, addr)
            if kind == "data":
                temps = rtu.parse_read_all(resp, scale=scale)
                print(f"  addr {addr:>2}: OK  {temps}")
                found = True
            elif kind == "error":
                print(f"  addr {addr:>2}: device present (Modbus exception)")
                found = True
            elif scan:
                pass  # silent during scan
            else:
                print(f"  addr {addr:>2}: NO RESPONSE  raw={_hex(resp)}")
    print(f"  => Temp {'PASS' if found else 'FAIL'}")
    return found


# ----------------------------------------------------------------------- Balance
def test_balance(port: str, baud: int, parity: str, listen_s: float = 3.0) -> bool:
    proto = BalanceRs232Protocol()
    print(f"\n=== Balance @ {port} {baud} 8{parity}1  (listening {listen_s:.0f}s) ===")
    weights = []
    with open_serial(port, baud, parity, timeout=0.3) as ser:
        ser.reset_input_buffer()
        start = time.time()
        buf = b""
        while time.time() - start < listen_s:
            n = ser.in_waiting
            if n:
                buf += ser.read(n)
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    text = line.decode("ascii", errors="replace").strip()
                    w = proto.parse_line(text)
                    if w is not None:
                        weights.append(w)
            time.sleep(0.02)
    if weights:
        print(f"  OK  parsed {len(weights)} stable readings, last weight = {weights[-1]} g")
    else:
        print("  FAIL  no stable weight lines parsed (check baud/parity/wiring)")
    print(f"  => Balance {'PASS' if weights else 'FAIL'}")
    return bool(weights)


def main() -> int:
    cfg = load_config()
    mfc_c = cfg.get("COM_RS485_MFC", {})
    temp_c = cfg.get("COM_RS485_TEMP", {})
    bal_c = cfg.get("COM_RS232_Balance", {})

    p = argparse.ArgumentParser(description="TMH device communication self-test.")
    p.add_argument("--device", choices=["mfc", "temp", "balance", "all"], default="all")
    p.add_argument("--port", help="Override serial port (e.g. COM3).")
    p.add_argument("--baud", type=int, help="Override baud rate.")
    p.add_argument("--parity", choices=["N", "E", "O"], help="Override parity.")
    p.add_argument("--address", type=int, help="Temp Modbus slave address (single test).")
    p.add_argument("--scan", action="store_true", help="Temp: scan addresses 0..16.")
    args = p.parse_args()

    results = {}
    try:
        if args.device in ("mfc", "all"):
            results["MFC"] = test_mfc(
                port=args.port or mfc_c.get("port", "COM1"),
                baud=args.baud or int(mfc_c.get("baudrate", 9600)),
                parity=args.parity or mfc_c.get("parity", "E"),
                addresses=cfg.get("SLAVE_ADDRESS_MFC", {"H2": 1, "N2": 2, "CO2": 3, "CO": 4}),
                scaling=cfg.get("FLOW_SCALING", {"H2": 0.1, "N2": 1.0, "CO2": 0.1, "CO": 0.1}),
            )
        if args.device in ("temp", "all"):
            results["Temp"] = test_temp(
                port=args.port or temp_c.get("port", "COM2"),
                baud=args.baud or int(temp_c.get("baudrate", 9600)),
                parity=args.parity or temp_c.get("parity", "N"),
                address=args.address if args.address is not None else int(temp_c.get("slave_address", 0)),
                scale=float(temp_c.get("scale", 0.1)),
                scan=args.scan,
            )
        if args.device in ("balance", "all"):
            results["Balance"] = test_balance(
                port=args.port or bal_c.get("port", "COM3"),
                baud=args.baud or int(bal_c.get("baudrate", 1200)),
                parity=args.parity or bal_c.get("parity", "N"),
            )
    except serial.SerialException as exc:
        print(f"\n[ERROR] serial: {exc}")
        return 2

    print("\n===== SUMMARY =====")
    for name, ok in results.items():
        print(f"  {name:>8}: {'PASS' if ok else 'FAIL'}")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
