#!/usr/bin/env python3
"""Read-only Modbus register scanner for the temperature controller.

This tool only sends read functions 0x03 (holding registers) or 0x04 (input
registers). It never writes registers, so it is safe for field discovery before
implementing temperature program download.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
sys.path.insert(0, str(_ROOT / "packages" / "tmh_comm" / "src"))

import serial  # noqa: E402
from tmh_comm.protocols.temp_rtu import _crc16_modbus  # noqa: E402

_PARITY = {"N": serial.PARITY_NONE, "E": serial.PARITY_EVEN, "O": serial.PARITY_ODD}
_KNOWN_TEMP_REGS = {
    0x0000: "PV1",
    0x0001: "SV1",
    0x0002: "PV2",
    0x0003: "SV2",
    0x0004: "PV3",
    0x0005: "SV3",
    0x0006: "T7",
    0x0007: "T8",
    0x0008: "T9",
}


@dataclass(frozen=True)
class RegisterValue:
    address: int
    raw_unsigned: int
    raw_signed: int
    scaled_unsigned: float
    scaled_signed: float
    note: str


def _hex_bytes(data: bytes) -> str:
    return data.hex(" ")


def _parse_int(text: str) -> int:
    return int(text, 0)


def _parse_range(text: str) -> tuple[int, int]:
    if ":" not in text:
        start = _parse_int(text)
        return start, start + 1
    start_text, end_text = text.split(":", 1)
    start = _parse_int(start_text)
    end = _parse_int(end_text)
    if end <= start:
        raise argparse.ArgumentTypeError(f"invalid range {text!r}: end must be greater than start")
    return start, end


def _load_config() -> dict:
    path = _ROOT / "configs" / "comm_config.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[warn] could not read {path}: {exc}")
        return {}


def _open_serial(port: str, baud: int, parity: str, timeout: float) -> serial.Serial:
    return serial.Serial(
        port=port,
        baudrate=baud,
        bytesize=serial.EIGHTBITS,
        parity=_PARITY.get(parity.upper(), serial.PARITY_NONE),
        stopbits=serial.STOPBITS_ONE,
        timeout=timeout,
    )


def _build_read_registers(slave: int, function_code: int, start: int, count: int) -> bytes:
    base = bytes([
        slave,
        function_code,
        (start >> 8) & 0xFF,
        start & 0xFF,
        (count >> 8) & 0xFF,
        count & 0xFF,
    ])
    return base + _crc16_modbus(base)


def _read_response(
    ser: serial.Serial,
    slave: int,
    function_code: int,
    count: int,
    timeout: float,
) -> tuple[str, bytes]:
    expected_data_len = count * 2
    deadline = time.time() + timeout
    buf = b""
    while time.time() < deadline:
        waiting = ser.in_waiting
        if waiting:
            buf += ser.read(waiting)
            parsed = _extract_response(buf, slave, function_code, expected_data_len)
            if parsed is not None:
                return parsed
        time.sleep(0.005)
    parsed = _extract_response(buf, slave, function_code, expected_data_len)
    if parsed is not None:
        return parsed
    return "timeout", buf


def _extract_response(
    buf: bytes,
    slave: int,
    function_code: int,
    expected_data_len: int,
) -> tuple[str, bytes] | None:
    for offset in range(0, max(0, len(buf) - 4)):
        if buf[offset] != slave:
            continue

        func = buf[offset + 1]
        if func == function_code:
            byte_count = buf[offset + 2]
            if byte_count != expected_data_len:
                continue
            end = offset + 3 + byte_count + 2
            if end > len(buf):
                continue
            frame = buf[offset:end]
            if _crc16_modbus(frame[:-2]) == frame[-2:]:
                return "ok", frame

        if func == (function_code | 0x80):
            end = offset + 5
            if end > len(buf):
                continue
            frame = buf[offset:end]
            if _crc16_modbus(frame[:-2]) == frame[-2:]:
                return f"exception_{frame[2]:02x}", frame
    return None


def _decode_values(start: int, frame: bytes, scale: float) -> list[RegisterValue]:
    byte_count = frame[2]
    data = frame[3: 3 + byte_count]
    values = []
    for index in range(0, len(data), 2):
        address = start + index // 2
        raw_unsigned = int.from_bytes(data[index:index + 2], byteorder="big", signed=False)
        raw_signed = raw_unsigned - 0x10000 if raw_unsigned & 0x8000 else raw_unsigned
        scaled_unsigned = raw_unsigned * scale
        scaled_signed = raw_signed * scale
        note = _KNOWN_TEMP_REGS.get(address, "")
        if not note:
            note = _classify_value(raw_unsigned, raw_signed, scaled_unsigned, scaled_signed)
        values.append(RegisterValue(address, raw_unsigned, raw_signed, scaled_unsigned, scaled_signed, note))
    return values


def _classify_value(raw_unsigned: int, raw_signed: int, scaled_unsigned: float, scaled_signed: float) -> str:
    if raw_unsigned == 0:
        return "zero"
    notes = []
    if -100.0 <= scaled_signed <= 1200.0:
        notes.append("scaled_signed_temp_like")
    if 0.0 <= scaled_unsigned <= 1200.0:
        notes.append("scaled_unsigned_temp_like")
    if 0 <= raw_unsigned <= 9999:
        notes.append("small_raw")
    return ",".join(notes) if notes else ""


def _chunks(start: int, end: int, chunk_size: int) -> Iterable[tuple[int, int]]:
    current = start
    while current < end:
        count = min(chunk_size, end - current)
        yield current, count
        current += count


def _scan_range(
    ser: serial.Serial,
    *,
    slave: int,
    function_code: int,
    start: int,
    end: int,
    chunk_size: int,
    timeout: float,
    scale: float,
    delay: float,
    include_zero: bool,
) -> list[RegisterValue]:
    found: list[RegisterValue] = []
    total = max(0, end - start)
    completed = 0
    for addr, count in _chunks(start, end, chunk_size):
        cmd = _build_read_registers(slave, function_code, addr, count)
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        ser.write(cmd)
        status, frame = _read_response(ser, slave, function_code, count, timeout)
        completed += count

        if status == "ok":
            values = _decode_values(addr, frame, scale)
            visible = [value for value in values if include_zero or value.raw_unsigned != 0 or value.note in _KNOWN_TEMP_REGS.values()]
            found.extend(visible)
            if visible:
                print(f"0x{addr:04X}-0x{addr + count - 1:04X}: OK, visible={len(visible)}")
        elif status.startswith("exception"):
            print(f"0x{addr:04X}-0x{addr + count - 1:04X}: {status}")
        else:
            if frame:
                print(f"0x{addr:04X}-0x{addr + count - 1:04X}: timeout/no frame raw={_hex_bytes(frame)}")

        if completed % max(chunk_size * 16, 1) == 0:
            print(f"  progress: {completed}/{total} registers in current range")
        time.sleep(delay)
    return found


def _write_csv(path: Path, rows: list[RegisterValue]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["address_hex", "address_dec", "raw_unsigned", "raw_signed", "scaled_unsigned", "scaled_signed", "note"])
        for row in rows:
            writer.writerow([
                f"0x{row.address:04X}",
                row.address,
                row.raw_unsigned,
                row.raw_signed,
                f"{row.scaled_unsigned:.3f}",
                f"{row.scaled_signed:.3f}",
                row.note,
            ])


def main() -> int:
    cfg = _load_config()
    temp_cfg = cfg.get("COM_RS485_TEMP", {})
    default_ranges = ["0x0000:0x0100"]

    parser = argparse.ArgumentParser(description="Read-only Modbus register scanner for temperature controller.")
    parser.add_argument("--port", default=temp_cfg.get("port", "COM2"))
    parser.add_argument("--baud", type=int, default=int(temp_cfg.get("baudrate", 9600)))
    parser.add_argument("--parity", choices=["N", "E", "O"], default=temp_cfg.get("parity", "N"))
    parser.add_argument("--slave", type=int, default=int(temp_cfg.get("slave_address", 0)))
    parser.add_argument("--scale", type=float, default=float(temp_cfg.get("scale", 0.1)))
    parser.add_argument(
        "--function",
        choices=["03", "04"],
        default="03",
        help="Read function: 03=holding registers, 04=input registers.",
    )
    parser.add_argument("--range", dest="ranges", action="append", type=_parse_range, help="Register range, e.g. 0x0000:0x0100. Can be repeated.")
    parser.add_argument("--chunk", type=int, default=8, help="Registers per request.")
    parser.add_argument("--timeout", type=float, default=0.35)
    parser.add_argument("--delay", type=float, default=0.03)
    parser.add_argument("--include-zero", action="store_true", help="Include zero-valued registers in CSV.")
    parser.add_argument("--output", help="CSV output path. Defaults to logs/temp_register_scan_<timestamp>.csv")
    args = parser.parse_args()

    ranges = args.ranges or [_parse_range(text) for text in default_ranges]
    output = Path(args.output) if args.output else _ROOT / "logs" / f"temp_register_scan_{datetime.now():%Y%m%d_%H%M%S}.csv"

    function_code = int(args.function, 16)

    print(f"Read-only scan: function 0x{function_code:02X} only; no register writes will be sent.")
    print(f"Temp controller @ {args.port} {args.baud} 8{args.parity}1 slave={args.slave}")
    print(f"Ranges: {', '.join(f'0x{s:04X}:0x{e:04X}' for s, e in ranges)}  chunk={args.chunk}")

    all_rows: list[RegisterValue] = []
    try:
        with _open_serial(args.port, args.baud, args.parity, args.timeout) as ser:
            for start, end in ranges:
                print(f"\n=== scanning 0x{start:04X}:0x{end:04X} ===")
                all_rows.extend(
                    _scan_range(
                        ser,
                        slave=args.slave,
                        function_code=function_code,
                        start=start,
                        end=end,
                        chunk_size=args.chunk,
                        timeout=args.timeout,
                        scale=args.scale,
                        delay=args.delay,
                        include_zero=args.include_zero,
                    )
                )
    except serial.SerialException as exc:
        print(f"[ERROR] serial: {exc}")
        return 2

    _write_csv(output, all_rows)
    nonzero = [row for row in all_rows if row.raw_unsigned != 0]
    print("\n===== SUMMARY =====")
    print(f"visible rows: {len(all_rows)}, non-zero rows: {len(nonzero)}")
    print(f"csv: {output}")
    if nonzero:
        print("first non-zero rows:")
        for row in nonzero[:30]:
            print(
                f"  0x{row.address:04X} ({row.address:5d}) raw={row.raw_unsigned:5d} "
                f"signed={row.raw_signed:6d} scaled={row.scaled_signed:8.1f} note={row.note}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
