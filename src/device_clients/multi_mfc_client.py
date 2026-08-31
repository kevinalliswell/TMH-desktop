import time
import os
import csv
import datetime
import math
import random
from pathlib import Path
from queue import Queue, Full, Empty, PriorityQueue
import threading
from typing import Dict, Any, Optional, List, Tuple, Union
from enum import IntEnum

from src.device_clients.base_device import BaseDevice
from tmh_comm.protocols.mfc_cpl import MfcCplProtocol
from src.utils.path_manager import PathManager
# 移除数据滤波功能，直接使用实时数据


class CommandPriority(IntEnum):
    """命令优先级枚举"""
    HIGH = 1    # 高优先级 - 设置命令
    NORMAL = 2  # 普通优先级 - 读取命令


class SerialCommand:
    """串口命令封装"""
    def __init__(self, cmd_bytes: bytes, priority: CommandPriority, callback=None, timeout: float = 1.0):
        self.cmd_bytes = cmd_bytes
        self.priority = priority
        self.callback = callback
        self.timeout = timeout
        self.timestamp = time.time()
        self.result = None
        self.completed = threading.Event()
    
    def __lt__(self, other):
        # 优先级队列排序：优先级数字越小越优先
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.timestamp < other.timestamp


class MultiMFCClient(BaseDevice):
    """多路MFC控制器客户端
    
    该类负责管理多个MFC设备的通信，包括读取当前流量和设定流量。
    所有设备共享同一个串口资源，通过设备地址进行区分。
    """
    
    # 寄存器地址常量
    PV_ADDR = 1206  # 当前流量寄存器
    SV_ADDR = 1401  # 设定流量寄存器
    
    # 命令超时时间(秒) - 增加超时时间
    COMMAND_TIMEOUT = 2.0
    WRITE_COMMAND_TIMEOUT = 3.0  # 写命令更长超时时间
    
    # 读取间隔(秒) - 增加读取间隔，减少串口占用频率
    READ_INTERVAL = 1.0
    
    # 重试参数
    MAX_RETRIES = 3
    RETRY_DELAY = 0.2
    
    # 命令队列大小
    COMMAND_QUEUE_SIZE = 50

    def __init__(self, config_source):
        """初始化多路MFC客户端
        
        Args:
            config_source: 配置文件路径或注入配置
        """
        super().__init__(config_source, "MultiMFC", "COM_RS485_MFC")
        
        # 验证配置加载
        if not self.config:
            raise ValueError(f"无法加载配置文件: {self.config_path}")
        
        # 获取设备地址信息    
        self.slave_addresses = self.config.get("SLAVE_ADDRESS_MFC", {})
        if not self.slave_addresses:
            self.logger.error("配置中缺少MFC设备地址信息")
            raise ValueError("配置中缺少MFC设备地址信息")
        
        # 获取流量缩放配置
        self.flow_scaling = self.config.get("FLOW_SCALING", {})
        if not self.flow_scaling:
            self.logger.warning("配置中缺少FLOW_SCALING信息，将使用默认缩放值")
            # 设置默认缩放值（原有的*10逻辑相当于缩放系数为0.1）
            self.flow_scaling = {gas: 0.1 for gas in self.slave_addresses.keys()}
        
        self.logger.info(f"已配置MFC设备: {', '.join(self.slave_addresses.keys())}")
        self.logger.info(f"流量缩放配置: {self.flow_scaling}")

        # 可燃气体（H2/CO）流量安全上限（L/min）——下发前硬钳制，缺省 5.0
        self.gas_safety_limits = self.config.get("GAS_SAFETY_LIMITS", {}) or {"H2": 5.0, "CO": 5.0}
        self.logger.info(f"可燃气体流量安全上限: {self.gas_safety_limits}")

        # 移除模拟数据相关变量，专注实时数据采集

        # 数据存储 - 使用线程安全的字典
        self._latest_data_lock = threading.Lock()
        
        # 初始化数据结构 - 通讯异常时返回None而不是0
        self._latest_data = {}
        for gas_type in self.slave_addresses:
            self._latest_data[gas_type] = None  # 初始化为None，通讯成功后才有数据

        # 串口管理 - 优化串口访问机制（移除自动关闭，保持长连接）
        self._serial_lock = threading.RLock()  # 使用可重入锁
        self._serial_last_used = 0
        # 移除串口超时自动关闭机制，改为保持长连接
        # self._serial_timeout = 10.0  # 已移除：导致通讯中断
        
        # 命令队列系统
        self._command_queue = PriorityQueue(maxsize=self.COMMAND_QUEUE_SIZE)
        self._command_processor_thread = None
        self._command_processor_running = False

        # Modbus-CPL 协议封装
        self._cpl = MfcCplProtocol()
        
        # 读取计数
        self._read_counter = 0
        self._error_counter = 0
        
        # 初始化串口连接
        self._init_serial_connection()

    def _init_performance_config(self):
        """加载性能配置并映射到 MFC 特定的类属性"""
        super()._init_performance_config()
        # 将通用参数映射到 MFC 专用常量
        self.READ_INTERVAL = self.read_interval
        self.COMMAND_TIMEOUT = self.connection_timeout

    def _init_serial_connection(self) -> bool:
        """初始化串口连接池
        
        Returns:
            bool: 初始化是否成功
        """
        with self._serial_lock:
            try:
                if self.serial_port is None:
                    self.logger.debug("初始化串口连接池")
                    self.open_serial_port()
                    self._serial_last_used = time.time()
                    return self.serial_port is not None
                return True
            except Exception as e:
                self.logger.error(f"初始化串口连接失败: {e}")
                return False

    def _ensure_serial_connection(self) -> bool:
        """确保串口连接可用（保持长连接，不自动关闭）
        
        Returns:
            bool: 连接是否可用
        """
        with self._serial_lock:
            # 检查连接是否需要重新建立（移除超时自动关闭逻辑）
            current_time = time.time()
            if self.serial_port is None or not self.serial_port.is_open:
                # 关闭可能存在的连接
                self.close_serial_port()
                
                # 尝试重新打开连接
                result = self.open_serial_port()
                if result:
                    self._serial_last_used = current_time
                    self.logger.info("MFC串口连接已重新建立")
                else:
                    self.logger.error("MFC串口连接失败")
                return result
            
            # 更新最后使用时间（用于统计，不再用于自动关闭）
            self._serial_last_used = current_time
            return True

    def _start_command_processor(self):
        """启动命令处理线程"""
        if self._command_processor_thread is None or not self._command_processor_thread.is_alive():
            self._command_processor_running = True
            self._command_processor_thread = threading.Thread(
                target=self._command_processor_loop, 
                daemon=True, 
                name=f"{self.device_type}_CommandProcessor"
            )
            self._command_processor_thread.start()
            self.logger.debug("命令处理线程已启动")

    def _stop_command_processor(self):
        """停止命令处理线程"""
        self._command_processor_running = False
        if self._command_processor_thread and self._command_processor_thread.is_alive():
            # 添加一个停止命令到队列
            try:
                self._command_queue.put_nowait((0, SerialCommand(b'', CommandPriority.HIGH)))
            except Full:
                pass
            self._command_processor_thread.join(timeout=3.0)
            self.logger.debug("命令处理线程已停止")

    def _command_processor_loop(self):
        """命令处理器主循环"""
        self.logger.debug("命令处理器启动")
        
        while self._command_processor_running:
            try:
                # 从优先级队列获取命令，设置超时避免无限等待
                try:
                    priority, command = self._command_queue.get(timeout=1.0)
                    
                    # 检查是否为停止命令
                    if not self._command_processor_running or command.cmd_bytes == b'':
                        break
                    
                    # 执行命令
                    result = self._execute_serial_command(command)
                    command.result = result
                    command.completed.set()
                    
                    # 标记任务完成
                    self._command_queue.task_done()
                    
                except Empty:
                    # 超时是正常的，继续循环
                    continue
                    
            except Exception as e:
                self.logger.error(f"命令处理器异常: {e}")
                time.sleep(0.1)
        
        self.logger.debug("命令处理器停止")

    def _execute_serial_command(self, command: SerialCommand) -> Optional[bytes]:
        """执行串口命令
        
        Args:
            command: 串口命令对象
            
        Returns:
            bytes: 响应数据，失败返回None
        """
        if not command.cmd_bytes:
            return None
            
        with self._serial_lock:
            # 确保串口连接可用
            if not self._ensure_serial_connection():
                self.logger.error("串口连接不可用，无法执行命令")
                return None
                
            # 尝试指定次数
            for attempt in range(self.MAX_RETRIES):
                try:
                    # 清空缓冲区
                    self.serial_port.reset_input_buffer()
                    self.serial_port.reset_output_buffer()
                    
                    # 发送命令
                    self.serial_port.write(command.cmd_bytes)
                    self.logger.debug(f"发送数据: {command.cmd_bytes}")
                    
                    # 等待响应
                    time.sleep(0.05)  # 短暂延迟，等待设备处理
                    
                    # 接收响应
                    start_time = time.time()
                    response = b''
                    
                    while time.time() - start_time < command.timeout:
                        if self.serial_port.in_waiting > 0:
                            new_data = self.serial_port.read(self.serial_port.in_waiting)
                            response += new_data
                            
                            # 检查响应是否完整
                            if b'\r\n' in response:
                                self.logger.debug(f"接收到完整响应: {response}")
                                self._serial_last_used = time.time()
                                return response
                        
                        # 短暂延迟，减少CPU使用
                        time.sleep(0.01)
                    
                    # 超时处理
                    if response:
                        self.logger.warning(f"接收到不完整响应: {response}")
                        self._serial_last_used = time.time()
                        return response
                        
                    self.logger.warning(f"命令超时 (尝试 {attempt+1}/{self.MAX_RETRIES})")
                    
                except Exception as e:
                    self.logger.error(f"执行命令出错: {e}")
                    
                # 重试前延迟
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY)
            
            return None

    def _send_command_async(self, cmd: bytes, priority: CommandPriority = CommandPriority.NORMAL, 
                           timeout: float = None) -> SerialCommand:
        """异步发送命令
        
        Args:
            cmd: 要发送的命令字节序列
            priority: 命令优先级
            timeout: 命令超时时间
            
        Returns:
            SerialCommand: 命令对象，可以通过它获取结果
        """
        if timeout is None:
            timeout = self.WRITE_COMMAND_TIMEOUT if priority == CommandPriority.HIGH else self.COMMAND_TIMEOUT
        
        command = SerialCommand(cmd, priority, timeout=timeout)
        
        try:
            self._command_queue.put_nowait((priority.value, command))
            return command
        except Full:
            self.logger.warning("命令队列已满，丢弃最旧命令")
            try:
                # 移除一个最旧的低优先级命令
                self._command_queue.get_nowait()
                self._command_queue.put_nowait((priority.value, command))
                return command
            except (Empty, Full):
                self.logger.error("无法添加命令到队列")
                command.completed.set()
                return command

    def _send_command(self, cmd: bytes, retries: int = MAX_RETRIES) -> Optional[bytes]:
        """发送命令并接收响应（兼容性方法）
        
        Args:
            cmd: 要发送的命令字节序列
            retries: 重试次数（已废弃，保持兼容性）
            
        Returns:
            bytes: 接收到的响应，失败返回None
        """
        # self.logger.info(f"发送指令：{cmd}")
        command = self._send_command_async(cmd, CommandPriority.NORMAL)
        
        # 等待命令完成
        if command.completed.wait(timeout=self.COMMAND_TIMEOUT + 1.0):
            return command.result
        else:
            self.logger.warning("命令执行超时")
            return None

    def _read_register_value(self, gas_type: str, register_addr: int) -> Optional[float]:
        """读取指定气体的寄存器值
        
        Args:
            gas_type: 气体类型
            register_addr: 寄存器地址
            
        Returns:
            float: 读取到的值，失败返回None
        """
        if gas_type not in self.slave_addresses:
            self.logger.error(f"未知的气体类型: {gas_type}")
            return None
            
        slave_address = self.slave_addresses[gas_type]
        
        # 创建读取命令
        cmd = self._cpl.build_read(
            register_addr=register_addr,
            num_bytes=2,
            slave_address=slave_address,
        )
        
        # 发送命令并接收响应
        response = self._send_command(cmd)
        if not response:
            return None
            
        # 解析响应
        try:
            value = self._cpl.parse_response(response)
            return value
        except Exception as e:
            self.logger.error(f"解析 {gas_type} 数据失败: {e}")
            return None

    def _read_gas_data(self, gas_type: str) -> Optional[Dict[str, Any]]:
        """读取单个气体的PV/SV数据(优化模拟模式)
        
        Args:
            gas_type: 气体类型
            
        Returns:
            Dict: 包含timestamp, gas_type, PV, SV的数据字典
                 失败或无效气体类型返回None
        """
        # 直接读取真实设备数据，移除模拟模式
        # 真实设备模式
        pv_raw = self._read_register_value(gas_type, self.PV_ADDR)
        sv_raw = self._read_register_value(gas_type, self.SV_ADDR)
        
        pv_final = None
        sv_final = None

        # 获取该气体的缩放系数
        scaling_factor = self._get_scaling_factor(gas_type)
        
        # 应用缩放系数：实际值 = 设备值 * 缩放系数
        if pv_raw is not None:
            pv_final = round(pv_raw * scaling_factor, 2)
        if sv_raw is not None:
            sv_final = round(sv_raw * scaling_factor, 2)

        # Prepare data dictionary
        current_time = time.time()
        data = {
            'timestamp': current_time,
            'gas_type': gas_type,
            'PV': pv_final,
            'SV': sv_final
        }

        # 只有成功读取数据时才更新缓存
        if pv_final is not None or sv_final is not None:
            # 有效数据 - 更新缓存
            with self._latest_data_lock:
                self._latest_data[gas_type] = data
            self.logger.debug(f"[设备模式] {gas_type} 数据: PV={data['PV']}, SV={data['SV']} (原始 PV={pv_raw}, SV={sv_raw}, 缩放系数={scaling_factor})")
            return data
        else:
            # 通讯失败 - 不更新缓存，保持None表示通讯异常
            self.logger.warning(f"无法读取 {gas_type} 的数据 (原始 PV={pv_raw}, SV={sv_raw})")
            return None # Return None if both reads failed

    def _read_device_data_batch(self) -> Dict[str, Dict[str, Any]]:
        """批量读取所有MFC设备数据（增强版：单气体重试机制）
        
        Returns:
            Dict: 包含所有气体数据的字典
        """
        all_data = {}
        success_count = 0
        failed_gases = []  # 记录失败的气体
        
        # 跟踪读取计数
        self._read_counter += 1
        
        start_time = time.time()
        
        try:
            # 确保串口连接可用
            if not self._ensure_serial_connection():
                self.logger.error("串口连接不可用，无法读取数据")
                self._error_counter += 1
                return all_data
                
            # 第一轮：顺序读取每个气体的数据
            for gas_type in self.slave_addresses:
                gas_data = self._read_gas_data(gas_type)
                
                if gas_data:
                    all_data[gas_type] = gas_data
                    success_count += 1
                else:
                    failed_gases.append(gas_type)
            
            # 第二轮：对失败的气体进行重试（最多2次）
            if failed_gases:
                self.logger.warning(f"第一轮读取失败的气体: {', '.join(failed_gases)}，开始重试")
                retry_count = 0
                max_retries = 2
                
                while failed_gases and retry_count < max_retries:
                    retry_count += 1
                    still_failed = []
                    
                    for gas_type in failed_gases:
                        self.logger.debug(f"重试读取 {gas_type} (第 {retry_count} 次)")
                        time.sleep(0.1)  # 重试前短暂延迟
                        gas_data = self._read_gas_data(gas_type)
                        
                        if gas_data:
                            all_data[gas_type] = gas_data
                            success_count += 1
                            self.logger.info(f"{gas_type} 重试成功")
                        else:
                            still_failed.append(gas_type)
                    
                    failed_gases = still_failed
                
                # 最终仍然失败的气体
                if failed_gases:
                    self.logger.error(f"经过 {max_retries} 次重试后仍失败的气体: {', '.join(failed_gases)}")
                    
            # 每100次读取记录一次统计信息
            if self._read_counter % 100 == 0:
                error_rate = (self._error_counter / self._read_counter) * 100 if self._read_counter > 0 else 0
                self.logger.info(f"读取统计: 总次数={self._read_counter}, 错误率={error_rate:.2f}%")
                
            # 每次批量读取完成记录成功率
            if self.slave_addresses:
                batch_success_rate = (success_count / len(self.slave_addresses)) * 100
                if batch_success_rate < 100:
                    self.logger.warning(f"本次读取成功率: {batch_success_rate:.1f}% ({success_count}/{len(self.slave_addresses)})")
                elif success_count == len(self.slave_addresses):
                    self.logger.debug(f"批量读取成功率: 100% ({success_count}/{len(self.slave_addresses)})")
                
            # 记录批量读取耗时(仅在调试级别)
            elapsed = time.time() - start_time
            self.logger.debug(f"批量读取耗时: {elapsed:.3f}秒")
                
        except Exception as e:
            self.logger.error(f"批量读取异常: {e}")
            self._error_counter += 1
            
        return all_data

    def set_sp_value(self, gas_type: str, value: float, verify: bool = True) -> bool:
        """设置指定气体的流量值（优化版本 - 使用高优先级命令）
        
        Args:
            gas_type: 气体类型
            value: 流量值
            verify: 是否验证设置结果
            
        Returns:
            bool: 设置是否成功
        """
        self.logger.info(f"设置流量值: 气体={gas_type}, 流量={value}")

        # 首先检查设备连接状态，避免在设备未连接时发送指令造成超时
        if not self.serial_port_available:
            self.logger.warning(f"设备未连接，跳过 {gas_type} 流量设置指令")
            return False

        # 验证气体类型
        if gas_type not in self.slave_addresses:
            self.logger.error(f"无效的气体类型: {gas_type}")
            return False

        slave_address = self.slave_addresses[gas_type]

        # 安全上限硬钳制（可燃气体 H2/CO）——手动/实验/程序所有路径下发前的最终关口
        value = self._clamp_flow(gas_type, value)

        # 获取该气体的缩放系数
        scaling_factor = self._get_scaling_factor(gas_type)
        # 缩放逻辑：设备值 = 输入值 / 缩放系数
        scaled_value = int(value / scaling_factor * 10)
        self.logger.info(f"为 {gas_type} 设置缩放值: {scaled_value} (输入: {value} L/min, 缩放系数: {scaling_factor})")

        try:
            # 创建写入命令
            cmd = self._cpl.build_write(
                register_addr=self.SV_ADDR,
                data_list=[scaled_value],
                slave_address=slave_address,
            )
            self.logger.info(f"设定流量指令：{cmd}")
            # 使用高优先级异步命令，避免阻塞数据采集
            command = self._send_command_async(cmd, CommandPriority.HIGH, self.WRITE_COMMAND_TIMEOUT)
            
            # 等待命令完成，设置较短的超时时间以避免UI阻塞
            if not command.completed.wait(timeout=self.WRITE_COMMAND_TIMEOUT + 1.0):
                self.logger.error(f"{gas_type} 流量设定命令超时")
                return False

            acknowledgement = self._cpl.parse_write_ack(command.result or b"")
            if acknowledgement is not True:
                if acknowledgement is False:
                    self.logger.error(f"{gas_type} 流量设定被设备拒绝 (NG)")
                else:
                    self.logger.error(f"{gas_type} 流量设定未收到有效 OK 回复")
                return False

            if verify:
                readback = self._read_register_value(gas_type, self.SV_ADDR)
                expected_readback = scaled_value / 10.0
                if readback is None or not math.isclose(
                    readback,
                    expected_readback,
                    rel_tol=0.0,
                    abs_tol=0.05,
                ):
                    self.logger.error(
                        f"{gas_type} 流量读回校验失败: "
                        f"期望寄存器值={expected_readback}, 实际={readback}"
                    )
                    return False

            self.logger.info(f"{gas_type} 流量设定成功: {value} L/min")

            # 仅在设备确认且可选读回校验成功后更新本地缓存。
            with self._latest_data_lock:
                if gas_type in self._latest_data and self._latest_data[gas_type] is not None:
                    self._latest_data[gas_type]['SV'] = value
                else:
                    self._latest_data[gas_type] = {
                        'timestamp': time.time(),
                        'gas_type': gas_type,
                        'PV': None,
                        'SV': value,
                    }
            return True

        except Exception as e:
            self.logger.error(f"设置 {gas_type} 流量时出错: {e}")
            return False

    def _get_scaling_factor(self, gas_type: str) -> float:
        """获取指定气体的缩放系数
        
        Args:
            gas_type: 气体类型
            
        Returns:
            float: 缩放系数，默认为0.1
        """
        scaling_factor = self.flow_scaling.get(gas_type)
        if scaling_factor is None:
            self.logger.warning(f"未找到 {gas_type} 的缩放配置，使用默认值 0.1")
            return 0.1
        return scaling_factor

    def _clamp_flow(self, gas_type: str, value: float) -> float:
        """将流量裁剪到配置的安全上限以内（仅作用于配置中存在的气体，如 H2/CO）。

        仅设上界，0 <= limit 恒通过，不影响安全气氛归零。
        """
        try:
            limit = self.gas_safety_limits.get(gas_type)
        except AttributeError:
            limit = None
        if limit is not None and value > limit:
            self.logger.warning(
                f"{gas_type} 流量 {value} L/min 超过安全上限 {limit} L/min，已钳制为 {limit}"
            )
            return float(limit)
        return value

    def run(self):
        """设备主循环（增强版：持续重连机制 + 智能休眠）"""
        self.logger.info(f"========== {self.device_type} 流量采集启动 ==========")

        if not self.serial_port_available:
            self.logger.warning(f"========== {self.device_type} 设备串口初次检查不可用，将持续尝试重连 ==========")
            self.connection_healthy = False

        last_read_time = 0
        consecutive_errors = 0
        max_consecutive_errors = 5

        # 初始化连接
        self._init_serial_connection()
        
        # 启动命令处理器
        self._start_command_processor()

        while not self.stop_event.is_set():
            try:
                current_time = time.time()
                
                # 如果连接不健康，尝试智能重连
                if not self.connection_healthy:
                    if self.smart_reconnect():
                        consecutive_errors = 0
                        self.logger.info(f"{self.device_type} 连接已恢复，继续流量采集")
                        # 重新初始化连接
                        self._init_serial_connection()
                    else:
                        # 重连失败，等待下次重连时机
                        time.sleep(1.0)
                        continue

                # 检查是否到达读取时间（智能等待，避免频繁唤醒）
                time_until_next_read = self.READ_INTERVAL - (current_time - last_read_time)
                if time_until_next_read > 0.1:
                    # 还没到读取时间，智能休眠到接近读取时间
                    time.sleep(min(time_until_next_read - 0.05, 0.5))
                    continue

                # 到达读取时间，执行数据采集
                if current_time - last_read_time >= self.READ_INTERVAL:
                    # 读取数据
                    # 直接读取真实设备数据，移除模拟模式
                    all_data = self._read_device_data_batch()

                    if all_data:
                        self._last_valid_data = all_data
                        # 成功读取数据，更新健康状态
                        self.last_successful_read = current_time
                        self.connection_healthy = True
                        consecutive_errors = 0
                        
                        # 更新队列
                        for gas_type, data in all_data.items():
                            # 确保队列不会阻塞
                            try:
                                self.data_queue.put_nowait(data)
                                self.logger.debug(f"[批量] {data}")
                            except Full:
                                try:
                                    # 队列满时，清除一项再添加
                                    old_data = self.data_queue.get_nowait()
                                    self.data_queue.put_nowait(data)
                                    self.logger.warning(f"{self.device_type} 数据队列已满，丢弃旧数据")
                                except (Full, Empty):
                                    # 极端情况下忽略错误
                                    pass
                    else:
                        # 批量读取完全失败
                        consecutive_errors += 1
                        if consecutive_errors >= max_consecutive_errors:
                            self.logger.error(f"{self.device_type} 连续 {consecutive_errors} 次批量读取失败，标记连接不健康")
                            self.connection_healthy = False
                            consecutive_errors = 0

                    last_read_time = current_time

                # 短暂休眠，避免过于频繁检查
                time.sleep(0.1)

            except Exception as e:
                consecutive_errors += 1
                self.logger.error(f"主循环异常: {e}")
                
                # 连续错误过多，标记连接不健康
                if consecutive_errors >= max_consecutive_errors:
                    self.logger.error(f"{self.device_type} 连续 {consecutive_errors} 次异常，标记连接不健康")
                    self.connection_healthy = False
                    with self._serial_lock:
                        self.close_serial_port()
                    consecutive_errors = 0
                
                time.sleep(0.5)  # 异常后稍作等待

        # 停止处理
        self._stop_command_processor()
        self.logger.info(f"========== {self.device_type} 流量采集停止 ==========")
        self.close_serial_port()

    def stop(self):
        """停止设备，覆盖父类方法以提供额外的清理"""
        self.logger.info(f"{self.device_type} 准备停止...")

        # 先停止命令处理线程，确保它不会在串口关闭后仍持锁读写串口
        # （父类 close_serial_port 不受 _serial_lock 保护）。
        self._stop_command_processor()

        # 再让主采集线程退出并关闭串口（父类会先 join 线程再关闭句柄）。
        super().stop()

        # 兜底确保串口已关闭。
        with self._serial_lock:
            self.close_serial_port()

    @property
    def current_flows(self) -> Dict[str, Optional[float]]:
        """获取所有气体的最新流量值
        
        Returns:
            Dict: 气体类型到流量值的映射
        """
        flows = {}
        with self._latest_data_lock:
            self.logger.debug(f"获取最新流量值PV: {self._latest_data}")
            for gas_type in self.slave_addresses.keys():
                data = self._latest_data[gas_type]
                flows[gas_type] = data.get('PV', None) if data else None
        return flows

    @property
    def setpoints(self) -> Dict[str, Optional[float]]:
        """获取所有气体的当前设定值
        
        Returns:
            Dict: 气体类型到设定值的映射
        """
        svs = {}
        with self._latest_data_lock:
            self.logger.debug(f"获取当前设定值SV: {self._latest_data}")
            for gas_type in self.slave_addresses.keys():
                data = self._latest_data[gas_type]
                svs[gas_type] = data.get('SV', None) if data else None
        return svs


    def get_data(self, gas_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """获取特定气体的数据
        
        Args:
            gas_type: 气体类型，如果为None则返回任意可用数据
            
        Returns:
            Dict: 设备数据字典，无数据时返回None
        """
        with self._latest_data_lock:
            if gas_type:
                if gas_type in self._latest_data:
                    return self._latest_data[gas_type]
                else:
                    self.logger.warning(f"请求的气体类型 {gas_type} 不存在")
                    return None
            else:
                # 返回第一个有效数据
                for gas_type, data in self._latest_data.items():
                    if data:
                        return data
                    
                # 如果没有任何数据可用，返回None而不是默认数据
                return None

    # 移除所有滤波器相关功能，专注于实时数据采集

    def _read_device_data(self) -> Dict[str, Dict[str, Any]]:
        """读取设备数据，实现基类抽象方法
        
        Returns:
            Dict: 所有气体数据的字典
        """
        return self._read_device_data_batch()
        

def test_continuous_reading():
    """测试连续读取功能"""
    config_path = PathManager.get_config_path('comm_config.json')

    # 初始化 MFC 客户端
    multi_mfc = MultiMFCClient(config_path)
    
    # 启用调试模式
    # 已移除调试模式功能

    try:
        # 启动线程
        multi_mfc.start()
        
        print("开始连续读取数据 (Ctrl+C 停止)...")
        print("当前气体类型:", list(multi_mfc.slave_addresses.keys()))
        
        # # 测试设置流量
        # for gas_type in multi_mfc.slave_addresses:
        #     test_value = round(random.uniform(5.0, 10.0), 1)
        #     print(f"测试设置 {gas_type} 流量为 {test_value}...")
        #     result = multi_mfc.set_sp_value(gas_type, test_value)
        #     print(f"设置结果: {'成功' if result else '失败'}")
        #     time.sleep(0.5)

        # 主显示循环
        while True:
            time.sleep(1)  # 显示间隔

            # 获取并显示所有气体数据
            current_flows = multi_mfc.current_flows
            setpoints = multi_mfc.setpoints

            print("\n" + "=" * 40)
            print(f"时间: {datetime.datetime.now().strftime('%H:%M:%S')}")
            for gas_type in multi_mfc.slave_addresses:
                pv = current_flows[gas_type]
                sv = setpoints[gas_type]
                pv_str = f"{pv:.2f}" if pv is not None else "N/A"
                sv_str = f"{sv:.2f}" if sv is not None else "N/A"
                print(f"{gas_type}: 当前流量={pv_str}, 设定值={sv_str}")
            print("=" * 40)

    except KeyboardInterrupt:
        print("\n正在停止采集...")
    finally:
        # 停止线程
        multi_mfc.stop()
        print("测试结束")


if __name__ == "__main__":
    test_continuous_reading()


