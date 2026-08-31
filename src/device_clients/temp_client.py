# temp_client.py
import os
import queue
import time
import logging
import threading
import binascii
from pathlib import Path
from typing import Dict, Optional, Any, Callable, List, Tuple, Union

import serial
import random

from src.device_clients.base_device import BaseDevice
from tmh_comm.protocols.temp_rtu import TempRtuProtocol
# 移除数据滤波功能，直接使用实时数据


class TempClient(BaseDevice):
    """温度控制器客户端
    
    负责与温控器进行通信，读取各个温度点数据。
    通过继承BaseDevice实现串口通信基础功能。
    """
    
    # 温度点映射
    TEMP_POINTS = {
        "T1": {"index": 0, "description": "一区温度PV", "unit": "°C"},
        "T2": {"index": 1, "description": "一区温度SV", "unit": "°C"},
        "T3": {"index": 2, "description": "二区温度PV", "unit": "°C"},
        "T4": {"index": 3, "description": "二区温度SV", "unit": "°C"},
        "T5": {"index": 4, "description": "三区温度PV", "unit": "°C"},
        "T6": {"index": 5, "description": "三区温度SV", "unit": "°C"},
        "T7": {"index": 6, "description": "测温1", "unit": "°C"},
        "T8": {"index": 7, "description": "测温2", "unit": "°C"},
        "T9": {"index": 8, "description": "测温3", "unit": "°C"},
    }
    
    # 命令响应超时设置(秒)
    COMMAND_TIMEOUT = 0.5
    
    # 读取间隔(秒)
    READ_INTERVAL = 1.0
    
    # 重试参数
    MAX_RETRIES = 3
    RETRY_DELAY = 0.2

    def __init__(self, config_source):
        """初始化温度控制器客户端
        
        Args:
            config_source: 配置文件路径或注入配置
        """
        super().__init__(config_source, "Temperature", "COM_RS485_TEMP")
        
        # 验证配置
        if not self.config:
            raise ValueError(f"无法加载配置文件: {self.config_path}")

        # 获取设备地址（兼容两种配置来源）
        self.slave_address = self.config.get("SLAVE_ADDRESS_TEMP", {}).get("TEMP")
        if self.slave_address is None:
            self.slave_address = self.config.get("COM_RS485_TEMP", {}).get("slave_address")
        if self.slave_address is None:
            self.logger.error("配置中缺少温控器设备地址")
            raise ValueError("配置中缺少温控器设备地址")
            
        self.logger.info(f"温控器设备地址: {self.slave_address}")

        
        # 最后一次读取的数据
        self._last_temperature_data = {}
        self._data_lock = threading.Lock()
        
        # 统计信息
        self._read_counter = 0
        self._error_counter = 0

        # Modbus-RTU 协议封装
        self._rtu = TempRtuProtocol()

    def _format_command_hex(self, command: bytes) -> str:
        """格式化命令为可读的十六进制字符串
        
        Args:
            command: 命令字节序列
            
        Returns:
            str: 格式化后的十六进制字符串
        """
        hex_command = binascii.hexlify(command).decode('utf-8')
        return ' '.join(hex_command[i:i + 2] for i in range(0, len(hex_command), 2)).upper()

    def _send_command(self, command: bytes, retries: int = MAX_RETRIES) -> Optional[bytes]:
        """发送命令到设备并读取响应
        
        Args:
            command: 要发送的命令字节序列
            retries: 重试次数
            
        Returns:
            bytes: 设备响应数据，失败返回None
        """
        if not command:
            return None
            
        # 格式化命令日志
        cmd_hex = self._format_command_hex(command)
        self.logger.debug(f"准备发送命令: {cmd_hex}")
        
        # 尝试指定次数
        for attempt in range(retries):
            try:
                with self.serial_port_context() as ser:
                    if not ser:
                        self.logger.error("串口不可用，无法发送命令")
                        return None
                    
                    # 清空缓冲区
                    ser.reset_input_buffer()
                    ser.reset_output_buffer()
                    
                    # 发送命令
                    ser.write(command)
                    self.logger.debug(f"已发送命令: {cmd_hex}")
                    
                    # 等待响应
                    time.sleep(0.1)
                    
                    # 读取响应
                    start_time = time.time()
                    response = b''
                    while (time.time() - start_time) < self.COMMAND_TIMEOUT:
                        if ser.in_waiting > 0:
                            response += ser.read(ser.in_waiting)
                            if self._rtu.extract_read_all(
                                response,
                                slave_address=self.slave_address,
                            ) is not None:
                                # 格式化完整响应日志
                                resp_hex = self._format_command_hex(response)
                                self.logger.debug(f"收到响应: {resp_hex}")
                                return response
                        time.sleep(0.01)

                    if response:
                        self.logger.warning(
                            f"收到不完整温控响应，丢弃并重试: {response.hex(' ')}"
                        )
                    else:
                        self.logger.warning(f"命令超时 (尝试 {attempt+1}/{retries})")
            except Exception as e:
                self.logger.error(f"发送命令异常: {e}")
            
            # 重试前延迟
            if attempt < retries - 1:
                time.sleep(self.RETRY_DELAY)
                
        self.logger.error(f"命令发送失败，已重试{retries}次")
        return None

    def read_all_temperatures(self) -> Dict[str, Optional[float]]:
        """读取所有温度点数据
        
        Returns:
            Dict: 包含所有温度点及其值的字典
        """
        result = {}

        # 初始化结果字典，所有温度点设为None
        for point in self.TEMP_POINTS:
            result[point] = None

        try:
            # 构建读取9个寄存器的Modbus命令
            command = self._rtu.build_read_all(slave_address=self.slave_address)
            
            # 发送命令并接收响应
            response = self._send_command(command)

            # 解析响应：在缓冲中定位 CRC 校验通过的 0x03 响应帧，
            # 跳过半双工 RS485 适配器可能回显的请求字节/噪声。
            frame = (
                self._rtu.extract_read_all(response, slave_address=self.slave_address)
                if response else None
            )
            if frame is not None:
                scale = self.port_config.get("scale", 0.1)
                signed_registers = self.port_config.get("signed_registers", True)
                parsed = self._rtu.parse_read_all(
                    frame,
                    scale=scale,
                    signed_registers=signed_registers,
                )
                for point in self.TEMP_POINTS:
                    if point in parsed:
                        result[point] = parsed[point]
                        info = self.TEMP_POINTS[point]
                        if result[point] is None:
                            self.logger.warning(f"{info['description']}: 传感器故障")
                        else:
                            self.logger.debug(f"读取 {info['description']}: {result[point]}{info['unit']}")

                # 更新统计信息
                self._read_counter += 1

                # 更新最后读取的数据
                with self._data_lock:
                    self._last_temperature_data = result.copy()

                self.logger.debug("成功读取温度数据")
            elif response:
                # 收到了字节但没有有效帧——回显/噪声/地址或校验不匹配，打印原始字节便于现场排查
                self.logger.warning(
                    f"未找到有效温控响应帧(可能为回显/噪声/地址或校验不匹配): {response.hex(' ')}"
                )
                self._error_counter += 1
            else:
                self.logger.warning("未收到有效响应")
                self._error_counter += 1
                
            # 每100次读取输出一次统计信息
            if self._read_counter % 100 == 0:
                error_rate = (self._error_counter / self._read_counter) * 100 if self._read_counter > 0 else 0
                self.logger.info(f"读取统计: 总次数={self._read_counter}, 错误率={error_rate:.2f}%")

            # 无有效帧时返回空字典，让上层健康检查(if temps)能识别读取失败；
            # 全 None 字典本身为真值，会把断线误判为成功采集。
            if frame is None:
                return {}
            return result

        except Exception as e:
            self.logger.error(f"读取温度数据异常: {e}")
            self._error_counter += 1
            return {}

    def read_temperature(self, point: str) -> Optional[float]:
        """读取单个温度点的数据
        
        Args:
            point: 温度点名称，例如 "T1", "T3" 等
            
        Returns:
            float: 温度值，读取失败返回None
        """
        # 检查温度点是否有效
        if point not in self.TEMP_POINTS:
            self.logger.error(f"无效的温度点: {point}")
            return None

        # 从最近一次读取的数据中获取
        with self._data_lock:
            if point in self._last_temperature_data:
                value = self._last_temperature_data.get(point)
                if value is not None:
                    return value
                    
        # 如果没有缓存数据，读取所有温度
        temps = self.read_all_temperatures()
        return temps.get(point)

    def get_description(self, point: str) -> str:
        """获取温度点的描述
        
        Args:
            point: 温度点名称
            
        Returns:
            str: 温度点描述
        """
        info = self.TEMP_POINTS.get(point, {})
        return info.get("description", point)

    def get_unit(self, point: str) -> str:
        """获取温度点的单位
        
        Args:
            point: 温度点名称
            
        Returns:
            str: 温度点单位
        """
        info = self.TEMP_POINTS.get(point, {})
        return info.get("unit", "°C")

    def run(self):
        """温度采集主循环（增强版：持续重连机制 + 智能休眠）"""
        if not self.serial_port_available:
            self.logger.warning(f"========== {self.device_type} 设备串口初次检查不可用，将持续尝试重连 ==========")
            self.connection_healthy = False
            
        self.logger.info(f"========== {self.device_type} 温度采集启动 ==========")
        
        last_read_time = 0
        consecutive_errors = 0
        max_consecutive_errors = 5
        read_interval = getattr(self, "read_interval", self.READ_INTERVAL)

        while not self.stop_event.is_set():
            try:
                current_time = time.time()
                
                # 如果连接不健康，尝试智能重连
                if not self.connection_healthy:
                    if self.smart_reconnect():
                        consecutive_errors = 0
                        self.logger.info(f"{self.device_type} 连接已恢复，继续温度采集")
                    else:
                        # 重连失败，等待下次重连时机
                        time.sleep(1.0)
                        continue
                
                # 检查是否到达读取时间（智能等待，避免频繁唤醒）
                time_until_next_read = read_interval - (current_time - last_read_time)
                if time_until_next_read > 0.1:
                    # 还没到读取时间，智能休眠到接近读取时间
                    time.sleep(min(time_until_next_read - 0.05, 0.5))
                    continue
                
                # 到达读取时间，执行数据采集
                if current_time - last_read_time >= read_interval:
                    # 读取数据
                    # 直接读取真实设备数据，移除模拟模式
                    temps = self.read_all_temperatures()
                        
                    if temps:  # 确保数据有效
                        temps['timestamp'] = current_time
                        self._last_valid_data = temps
                        
                        # 成功读取，更新健康状态
                        self.last_successful_read = current_time
                        self.connection_healthy = True
                        consecutive_errors = 0
                        
                        # 确保队列不满
                        try:
                            self.data_queue.put_nowait(temps)
                        except queue.Full:
                            try:
                                # 队列满时，清除一项再添加
                                old_data = self.data_queue.get_nowait()
                                self.data_queue.put_nowait(temps)
                                self.logger.warning(f"{self.device_type} 数据队列已满，丢弃旧数据")
                            except (queue.Full, queue.Empty):
                                pass
                    else:
                        # 读取失败
                        consecutive_errors += 1
                        if consecutive_errors >= max_consecutive_errors:
                            self.logger.error(f"{self.device_type} 连续 {consecutive_errors} 次读取失败，标记连接不健康")
                            self.connection_healthy = False
                            consecutive_errors = 0
                                
                    last_read_time = current_time
                    
                # 短暂休眠，避免过于频繁检查
                time.sleep(0.1)
                
            except Exception as e:
                consecutive_errors += 1
                self.logger.error(f"温度采集异常: {e}")
                
                # 连续错误过多，标记连接不健康
                if consecutive_errors >= max_consecutive_errors:
                    self.logger.error(f"{self.device_type} 连续 {consecutive_errors} 次异常，标记连接不健康")
                    self.connection_healthy = False
                    self.close_serial_port()
                    consecutive_errors = 0
                
                time.sleep(0.5)  # 出错后短暂休眠
                
        self.logger.info(f"========== {self.device_type} 温度采集停止 ==========")

    def _log_filter_differences(self, original_data: Dict[str, Any], filtered_data: Dict[str, Any]):
        """记录滤波前后的数据差异（调试用）
        
        Args:
            original_data: 原始数据
            filtered_data: 滤波后数据
        """
        differences = []
        for key in self.TEMP_POINTS.keys():
            if key in original_data and key in filtered_data:
                original_val = original_data[key]
                filtered_val = filtered_data[key]
                if original_val is not None and filtered_val is not None:
                    diff = abs(original_val - filtered_val)
                    if diff > 0.1:  # 只记录显著差异
                        differences.append(f"{key}: {original_val:.1f} -> {filtered_val:.1f} (Δ{diff:.1f})")
        
        if differences:
            self.logger.debug(f"滤波差异: {', '.join(differences)}")

    # 移除模拟数据生成功能，专注于实时数据采集

    def _read_device_data(self) -> Optional[Dict[str, Any]]:
        """读取设备数据，实现基类抽象方法
        
        Returns:
            Dict: 包含温度数据的字典，读取失败返回None
        """
        # 直接读取真实设备温度数据，移除模拟模式
        temps = self.read_all_temperatures()
        if temps:
            temps['timestamp'] = time.time()
            return temps
        return None
        
    def get_temperature_data(self) -> Dict[str, Optional[float]]:
        """获取最新温度数据
        
        Returns:
            Dict: 包含所有温度点的最新数据
        """
        with self._data_lock:
            return self._last_temperature_data.copy()
    
    # 移除所有滤波器相关功能，专注于实时数据采集


if __name__ == "__main__":
    from src.utils.path_manager import PathManager
    print(f"项目根目录: {PathManager.get_project_root()}")
    
    # 读取配置文件
    config_path = PathManager.get_config_path('comm_config.json')
    
    # 初始化并测试温控器客户端
    temp_client = TempClient(config_path=config_path)
    
    # 启用调试模式测试
    # 已移除调试模式功能
    
    try:
        # 启动线程
        temp_client.start()
        print("温度数据采集已启动 (按Ctrl+C停止)...")
        
        # 测试采集循环
        for i in range(20):
            time.sleep(1)
            temps = temp_client.get_temperature_data()
            print(f"\n=== 第 {i+1} 次采集 ===")
            for point, value in temps.items():
                if point in temp_client.TEMP_POINTS:
                    desc = temp_client.get_description(point)
                    unit = temp_client.get_unit(point)
                    stable = temp_client.is_data_stable(point)
                    status = "稳定" if stable else "波动"
                    print(f"{point} ({desc}): {value}{unit} [{status}]")
            
            # 每5次显示滤波统计信息
            if (i + 1) % 5 == 0:
                stats = temp_client.get_filter_statistics()
                if stats:
                    print(f"\n滤波统计 (第{i+1}次):")
                    print(f"  总处理: {stats['total_processed']}")
                    print(f"  总滤波: {stats['total_filtered']}")
                    print(f"  滤波率: {stats['filter_rate']:.1f}%")
                    
    except KeyboardInterrupt:
        print("\n用户中断，停止采集...")
    finally:
        # 停止线程
        temp_client.stop()
        print("温控器客户端已停止")
