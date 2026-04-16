from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class TareResult:
    """去皮命令响应解析结果"""
    success: bool
    a00_found: bool
    stable_data_found: bool
    weight: Optional[float] = None


class BalanceRs232Protocol:
    STABLE_MARKER = "G S"
    TARE_CMD = bytes([0x54, 0x20, 0x0D, 0x0A])  # ASCII "T" + SP + CR + LF
    TARE_ACK_MARKER = "A00"

    _pattern = re.compile(r"([+-]\d+\.\d+)")
    _tare_weight_pattern = re.compile(r"([+-]?\d+\.\d+)\s+G\s+S")

    def parse_line(self, line: str) -> Optional[float]:
        """解析天平稳定重量数据行

        Args:
            line: 从串口读取的原始数据行

        Returns:
            解析后的重量值，非稳定数据或解析失败返回 None
        """
        if self.STABLE_MARKER not in line:
            return None
        match = self._pattern.search(line)
        if not match:
            return None
        try:
            return float(match.group(1))
        except ValueError:
            return None

    def parse_tare_response(self, response: str) -> TareResult:
        """解析去皮命令的累积响应数据

        判断逻辑（优先级从高到低）：
        1. 检测到 A00 确认标志 → 成功
        2. 未检测到 A00 但有稳定数据且重量接近零 → 成功
        3. 其他情况 → 失败

        Args:
            response: 从串口累积读取的完整响应字符串

        Returns:
            TareResult 包含 success / a00_found / stable_data_found / weight
        """
        a00_found = self.TARE_ACK_MARKER in response
        stable_data_found = self.STABLE_MARKER in response
        weight: Optional[float] = None

        # 从包含稳定标记的行中提取重量
        if stable_data_found:
            for line in response.splitlines():
                if self.STABLE_MARKER in line:
                    match = self._tare_weight_pattern.search(line)
                    if match:
                        try:
                            weight = float(match.group(1))
                        except ValueError:
                            pass
                        break

        # 判断成功条件
        if a00_found:
            return TareResult(success=True, a00_found=True,
                              stable_data_found=stable_data_found, weight=weight)

        if stable_data_found and weight is not None and abs(weight) < 0.15:
            return TareResult(success=True, a00_found=False,
                              stable_data_found=True, weight=weight)

        return TareResult(success=False, a00_found=False,
                          stable_data_found=stable_data_found, weight=weight)

