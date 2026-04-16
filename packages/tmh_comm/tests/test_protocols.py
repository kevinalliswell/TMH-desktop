"""
tmh-comm 通讯包测试脚本

测试覆盖:
- MfcCplProtocol: 命令构建、响应解析、校验和计算
- TempRtuProtocol: 命令构建、响应解析、CRC 计算
- BalanceRs232Protocol: 行解析、稳定标记识别
- StandardFrame: 帧构建、字段验证
"""

import sys
import time
from pathlib import Path

# 添加 src 目录到路径
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from tmh_comm import StandardFrame, build_mfc_frame, build_temp_frame, build_balance_frame
from tmh_comm.protocols import MfcCplProtocol, TempRtuProtocol, BalanceRs232Protocol
from tmh_comm.protocols.mfc_cpl import _cpl_checksum
from tmh_comm.protocols.temp_rtu import _crc16_modbus


class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, name: str):
        self.passed += 1
        print(f"  [PASS] {name}")

    def fail(self, name: str, msg: str):
        self.failed += 1
        self.errors.append((name, msg))
        print(f"  [FAIL] {name}: {msg}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*50}")
        print(f"测试结果: {self.passed}/{total} 通过")
        if self.errors:
            print("\n失败详情:")
            for name, msg in self.errors:
                print(f"  - {name}: {msg}")
        return self.failed == 0


def test_mfc_cpl_protocol(result: TestResult):
    """测试 MFC CPL 协议"""
    print("\n[MfcCplProtocol 测试]")
    proto = MfcCplProtocol()

    # 测试读命令构建
    cmd = proto.build_read(register_addr=1206, num_bytes=2, slave_address=1)
    if b"\x02" in cmd and b"\x03" in cmd and b"XRS" in cmd:
        result.ok("build_read - 命令包含 STX/ETX 和 XRS")
    else:
        result.fail("build_read", f"命令格式异常: {cmd}")

    if cmd.endswith(b"\r\n"):
        result.ok("build_read - 命令以 CRLF 结尾")
    else:
        result.fail("build_read", "命令应以 \\r\\n 结尾")

    # 测试写命令构建
    cmd_write = proto.build_write(register_addr=1001, data_list=[100, 50], slave_address=2)
    if b"XWS" in cmd_write:
        result.ok("build_write - 命令包含 XWS")
    else:
        result.fail("build_write", f"命令格式异常: {cmd_write}")

    # 测试响应解析
    # 模拟响应: STX + data + ETX (checksum 在 ETX 后, strip 会移除 STX/ETX)
    # 响应格式: \x02 STATUS,VALUE \x03 CHECKSUM \r
    mock_response = b"\x02OK,1234\x03"
    value = proto.parse_response(mock_response)
    if value == 123.4:  # 1234 / 10 = 123.4
        result.ok("parse_response - 正确解析数值 (1234 -> 123.4)")
    else:
        result.fail("parse_response", f"期望 123.4, 实际 {value}")

    # 测试空响应
    empty_value = proto.parse_response(b"")
    if empty_value is None:
        result.ok("parse_response - 空响应返回 None")
    else:
        result.fail("parse_response - 空响应", f"期望 None, 实际 {empty_value}")

    # 测试校验和计算
    test_str = "\x0201XRS,1206W,2\x03"
    checksum = _cpl_checksum(test_str)
    if len(checksum) == 2 and checksum.isalnum():
        result.ok("_cpl_checksum - 校验和格式正确 (2位十六进制)")
    else:
        result.fail("_cpl_checksum", f"校验和格式异常: {checksum}")


def test_temp_rtu_protocol(result: TestResult):
    """测试温控 Modbus RTU 协议"""
    print("\n[TempRtuProtocol 测试]")
    proto = TempRtuProtocol()

    # 测试读命令构建
    cmd = proto.build_read_all(slave_address=1)
    expected_base = bytes([0x01, 0x03, 0x00, 0x00, 0x00, 0x09])
    if cmd[:6] == expected_base:
        result.ok("build_read_all - 功能码 0x03, 起始地址 0x0000, 寄存器数 9")
    else:
        result.fail("build_read_all", f"命令基础部分不匹配: {cmd.hex()}")

    if len(cmd) == 8:  # 6 bytes base + 2 bytes CRC
        result.ok("build_read_all - 命令长度正确 (8字节含CRC)")
    else:
        result.fail("build_read_all", f"期望 8 字节, 实际 {len(cmd)}")

    # 验证 CRC
    crc = _crc16_modbus(expected_base)
    if cmd[6:8] == crc:
        result.ok("build_read_all - CRC16 校验正确")
    else:
        result.fail("build_read_all - CRC", f"期望 {crc.hex()}, 实际 {cmd[6:8].hex()}")

    # 测试响应解析
    # 模拟响应: [addr=1, func=0x03, byte_count=18, 9x2 bytes data, CRC]
    mock_data = bytes([0x01, 0x03, 0x12])  # 18 bytes of data
    mock_data += bytes([0x00, 0x64])  # T1 = 100 (10.0°C with scale 0.1)
    mock_data += bytes([0x00, 0xC8])  # T2 = 200 (20.0°C)
    mock_data += bytes([0x01, 0x2C])  # T3 = 300 (30.0°C)
    mock_data += bytes([0x01, 0x90])  # T4 = 400 (40.0°C)
    mock_data += bytes([0x01, 0xF4])  # T5 = 500 (50.0°C)
    mock_data += bytes([0x02, 0x58])  # T6 = 600 (60.0°C)
    mock_data += bytes([0x02, 0xBC])  # T7 = 700 (70.0°C)
    mock_data += bytes([0x03, 0x20])  # T8 = 800 (80.0°C)
    mock_data += bytes([0x03, 0x84])  # T9 = 900 (90.0°C)
    mock_data += bytes([0x00, 0x00])  # CRC (placeholder)

    temps = proto.parse_read_all(mock_data, scale=0.1)
    if len(temps) == 9:
        result.ok("parse_read_all - 解析出 9 个温度点")
    else:
        result.fail("parse_read_all", f"期望 9 个温度, 实际 {len(temps)}")

    if temps.get("T1") == 10.0:
        result.ok("parse_read_all - T1 = 10.0°C 正确")
    else:
        result.fail("parse_read_all - T1", f"期望 10.0, 实际 {temps.get('T1')}")

    if temps.get("T9") == 90.0:
        result.ok("parse_read_all - T9 = 90.0°C 正确")
    else:
        result.fail("parse_read_all - T9", f"期望 90.0, 实际 {temps.get('T9')}")

    # 测试短响应
    short_temps = proto.parse_read_all(bytes([0x01]))
    if short_temps == {}:
        result.ok("parse_read_all - 短响应返回空字典")
    else:
        result.fail("parse_read_all - 短响应", f"期望空字典, 实际 {short_temps}")


def test_balance_rs232_protocol(result: TestResult):
    """测试天平 RS232 协议"""
    print("\n[BalanceRs232Protocol 测试]")
    proto = BalanceRs232Protocol()

    # 测试正常稳定读数
    weight = proto.parse_line("+00015.1 G S")
    if weight == 15.1:
        result.ok("parse_line - 正值解析正确 (+00015.1 -> 15.1)")
    else:
        result.fail("parse_line - 正值", f"期望 15.1, 实际 {weight}")

    # 测试负值
    weight_neg = proto.parse_line("-00003.5 G S")
    if weight_neg == -3.5:
        result.ok("parse_line - 负值解析正确 (-00003.5 -> -3.5)")
    else:
        result.fail("parse_line - 负值", f"期望 -3.5, 实际 {weight_neg}")

    # 测试不稳定读数 (无 "G S" 标记)
    unstable = proto.parse_line("+00015.1 G")
    if unstable is None:
        result.ok("parse_line - 不稳定读数返回 None")
    else:
        result.fail("parse_line - 不稳定", f"期望 None, 实际 {unstable}")

    # 测试空行
    empty = proto.parse_line("")
    if empty is None:
        result.ok("parse_line - 空行返回 None")
    else:
        result.fail("parse_line - 空行", f"期望 None, 实际 {empty}")

    # 测试乱码
    garbage = proto.parse_line("XXXX G S")
    if garbage is None:
        result.ok("parse_line - 无效格式返回 None")
    else:
        result.fail("parse_line - 乱码", f"期望 None, 实际 {garbage}")


def test_standard_frame(result: TestResult):
    """测试 StandardFrame 数据帧"""
    print("\n[StandardFrame 测试]")

    # 测试 MFC 帧构建
    mfc_frame = build_mfc_frame(
        model="MQV0020BS",
        gas_type="H2",
        pv=10.5,
        sv=20.0,
        meta={"port": "COM12", "baudrate": 19200, "slave_address": 1}
    )

    if mfc_frame.device_type == "mfc":
        result.ok("build_mfc_frame - device_type = 'mfc'")
    else:
        result.fail("build_mfc_frame - device_type", f"期望 'mfc', 实际 '{mfc_frame.device_type}'")

    if mfc_frame.protocol == "modbus-cpl":
        result.ok("build_mfc_frame - protocol = 'modbus-cpl'")
    else:
        result.fail("build_mfc_frame - protocol", f"期望 'modbus-cpl', 实际 '{mfc_frame.protocol}'")

    if mfc_frame.payload["pv"] == 10.5:
        result.ok("build_mfc_frame - payload.pv = 10.5")
    else:
        result.fail("build_mfc_frame - pv", f"期望 10.5, 实际 {mfc_frame.payload['pv']}")

    if mfc_frame.meta.get("port") == "COM12":
        result.ok("build_mfc_frame - meta.port = 'COM12'")
    else:
        result.fail("build_mfc_frame - meta.port", f"实际 {mfc_frame.meta}")

    # 测试温控帧构建
    temp_frame = build_temp_frame(
        model="TEMP-CTRL",
        temperatures={"T1": 25.0, "T2": 30.0, "T3": None},
        meta={"port": "COM10"}
    )

    if temp_frame.device_type == "temp":
        result.ok("build_temp_frame - device_type = 'temp'")
    else:
        result.fail("build_temp_frame - device_type", f"实际 '{temp_frame.device_type}'")

    if temp_frame.payload["temperatures"]["T3"] is None:
        result.ok("build_temp_frame - 支持 None 温度值")
    else:
        result.fail("build_temp_frame - None值", "T3 应为 None")

    # 测试天平帧构建
    balance_frame = build_balance_frame(
        model="BALANCE-1200",
        weight=15.123,
        meta={"port": "COM15", "baudrate": 1200}
    )

    if balance_frame.bus == "RS232":
        result.ok("build_balance_frame - bus = 'RS232'")
    else:
        result.fail("build_balance_frame - bus", f"期望 'RS232', 实际 '{balance_frame.bus}'")

    if balance_frame.payload["unit"] == "g":
        result.ok("build_balance_frame - unit = 'g'")
    else:
        result.fail("build_balance_frame - unit", f"实际 '{balance_frame.payload['unit']}'")

    # 测试时间戳自动生成
    before = time.time()
    frame = build_mfc_frame(model="TEST", gas_type="N2", pv=0.0, sv=0.0)
    after = time.time()

    if before <= frame.timestamp <= after:
        result.ok("StandardFrame - 自动生成时间戳")
    else:
        result.fail("StandardFrame - timestamp", f"时间戳不在合理范围内")


def test_crc16_modbus(result: TestResult):
    """测试 Modbus CRC16 计算"""
    print("\n[CRC16 Modbus 测试]")

    # 已知测试向量: 读寄存器命令 01 03 00 00 00 01 应生成 CRC = 84 0A
    test_data = bytes([0x01, 0x03, 0x00, 0x00, 0x00, 0x01])
    crc = _crc16_modbus(test_data)
    expected = bytes([0x84, 0x0A])

    if crc == expected:
        result.ok(f"CRC16 计算正确: {test_data.hex()} -> {crc.hex()}")
    else:
        result.fail("CRC16", f"期望 {expected.hex()}, 实际 {crc.hex()}")

    # 测试空数据
    empty_crc = _crc16_modbus(b"")
    if len(empty_crc) == 2:
        result.ok("CRC16 - 空数据返回 2 字节")
    else:
        result.fail("CRC16 - 空数据", f"返回长度 {len(empty_crc)}")


def test_edge_cases(result: TestResult):
    """边界情况测试"""
    print("\n[边界情况测试]")

    # MFC 零值地址
    proto = MfcCplProtocol()
    cmd = proto.build_read(register_addr=0, num_bytes=1, slave_address=0)
    if b"00" in cmd:
        result.ok("MFC - 地址 0 构建正常")
    else:
        result.fail("MFC - 地址 0", f"命令异常: {cmd}")

    # 天平大数值
    balance = BalanceRs232Protocol()
    big = balance.parse_line("+99999.9 G S")
    if big == 99999.9:
        result.ok("天平 - 大数值解析正确")
    else:
        result.fail("天平 - 大数值", f"期望 99999.9, 实际 {big}")

    # 温控无数据响应
    temp = TempRtuProtocol()
    no_data = temp.parse_read_all(bytes([0x01, 0x03, 0x00]))  # byte_count=0
    if no_data == {}:
        result.ok("温控 - 无数据响应返回空字典")
    else:
        result.fail("温控 - 无数据", f"实际 {no_data}")

    # 帧构建无 meta
    frame = build_mfc_frame(model="TEST", gas_type="N2", pv=1.0, sv=2.0)
    if frame.meta == {}:
        result.ok("StandardFrame - 无 meta 时默认空字典")
    else:
        result.fail("StandardFrame - meta 默认值", f"实际 {frame.meta}")


def main():
    print("=" * 50)
    print("TMH-COMM 通讯包测试")
    print("=" * 50)

    result = TestResult()

    test_mfc_cpl_protocol(result)
    test_temp_rtu_protocol(result)
    test_balance_rs232_protocol(result)
    test_standard_frame(result)
    test_crc16_modbus(result)
    test_edge_cases(result)

    success = result.summary()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
