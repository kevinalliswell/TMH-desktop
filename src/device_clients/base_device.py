# base_device.py
import json
import os
import threading
import queue
import copy
from typing import Dict, Any, Optional, Union, List, Tuple

import serial
import time
import random
import psutil
from contextlib import contextmanager
from abc import ABC, abstractmethod
from src.utils.logger import get_logger
from src.utils.path_manager import PathManager


class BaseDevice(threading.Thread, ABC):
    def __init__(self, config_source, device_type, comm_type):
        super().__init__(daemon=True)
        self.config_path = config_source if isinstance(config_source, str) else "<in-memory>"
        self.device_type = device_type
        self.comm_type = comm_type
        # 优化队列大小，提高数据处理效率
        self.data_queue = queue.Queue(maxsize=20)
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.serial_port = None
        # 移除调试模式，专注于实时设备数据采集
        self.connection_retries = 3
        self.retry_interval = 2
        
        # 增强的重连机制 - 指数退避策略
        self.reconnect_delays = [1, 2, 5, 10, 30]  # 重连延迟序列（秒）
        self.reconnect_attempt = 0  # 当前重连尝试次数
        self.last_reconnect_time = 0  # 上次重连尝试时间
        self.connection_healthy = False  # 连接健康状态
        self.last_successful_read = 0  # 上次成功读取时间

        # 初始化日志
        self.logger = get_logger(f"{device_type}_Controller")
        self.logger.debug(f"{device_type} 设备初始化中...")

        # 加载配置文件
        try:
            self.config = self.load_config(config_source)
            if not self.config:
                self.logger.error(f"无法加载配置文件: {self.config_path}")
                raise ValueError(f"无法加载配置文件: {self.config_path}")
        except Exception as e:
            self.logger.error(f"加载配置文件失败: {str(e)}")
            raise
            
        self.port_config = self.config.get(self.comm_type, {})
        if not self.port_config:
            self.logger.error(f"配置文件中未找到通信类型: {self.comm_type}")
            raise ValueError(f"配置文件中未找到通信类型: {self.comm_type}")

        # 检查对应设备的串口可用性
        self.serial_port_available = self.check_serial_port()
        self.logger.debug(f'=========={device_type} serial_port_available: {self.serial_port_available}==========')

        # 加载性能配置（子类可通过 override 扩展）
        self._init_performance_config()

    def _init_performance_config(self):
        """从配置文件加载性能参数

        读取 PERFORMANCE_CONFIG 段中的采集间隔、缓冲区大小和连接超时。
        子类可覆盖此方法以添加设备特定的参数映射。
        """
        try:
            perf_config = self.config.get("PERFORMANCE_CONFIG", {})
            self.read_interval = perf_config.get("data_collection_interval", 0.5)
            self.buffer_size = perf_config.get("data_buffer_size", 50)
            self.connection_timeout = perf_config.get("connection_timeout", 5.0)

            self.logger.info(
                f"性能配置已加载: 采集间隔={self.read_interval}s, "
                f"缓冲区大小={self.buffer_size}"
            )
        except Exception as e:
            self.logger.error(f"加载性能配置失败: {e}，使用默认值")
            self.read_interval = 0.5
            self.buffer_size = 50
            self.connection_timeout = 5.0

    def open_serial_port(self) -> bool:
        """打开并保持串口连接（增强版：支持持续重连）
        
        Returns:
            bool: 串口是否成功打开
        """
        # 如果已经有串口对象但无效，先清理
        if self.serial_port is not None:
            try:
                if not self.serial_port.is_open:
                    self.serial_port = None
                else:
                    self.connection_healthy = True
                    self.last_successful_read = time.time()
                    return True  # 串口已经正常打开
            except Exception:
                self.serial_port = None
                self.connection_healthy = False
        
        # 尝试打开新的串口连接
        if self.serial_port is None:
            try:
                self.serial_port = serial.Serial(
                    port=self.port_config.get('port'),
                    baudrate=self.port_config.get('baudrate', 1200),
                    bytesize=self.port_config.get('bytesize', 8),
                    parity=self.port_config.get('parity', 'E'),
                    stopbits=self.port_config.get('stopbits', 1),
                    xonxoff=self.port_config.get('xonxoff', 0),
                    timeout=0.5  # 优化超时时间，提高响应速度
                )
                self.logger.info(f"串口 {self.port_config.get('port')} 已成功打开")
                self.connection_healthy = True
                self.last_successful_read = time.time()
                self.reconnect_attempt = 0  # 重置重连计数
                return True
            except serial.SerialException as e:
                self.logger.error(f'打开串口失败: {e}')
                self.serial_port = None
                self.connection_healthy = False
                return False
        return True
    
    def smart_reconnect(self) -> bool:
        """智能重连机制 - 使用指数退避策略
        
        Returns:
            bool: 是否成功重连
        """
        current_time = time.time()
        
        # 计算当前应该使用的延迟时间
        delay_index = min(self.reconnect_attempt, len(self.reconnect_delays) - 1)
        required_delay = self.reconnect_delays[delay_index]
        
        # 检查是否到达重连时间
        if current_time - self.last_reconnect_time < required_delay:
            return False  # 还未到重连时间
        
        # 尝试重连
        self.logger.info(f"{self.device_type} 尝试重新连接 (第 {self.reconnect_attempt + 1} 次, 延迟 {required_delay}s)")
        self.last_reconnect_time = current_time
        self.reconnect_attempt += 1
        
        # 先关闭旧连接
        self.close_serial_port()
        
        # 尝试打开新连接
        if self.open_serial_port():
            self.logger.info(f"{self.device_type} 重新连接成功！")
            return True
        else:
            self.logger.warning(f"{self.device_type} 重新连接失败，将在 {self.reconnect_delays[min(self.reconnect_attempt, len(self.reconnect_delays) - 1)]}s 后重试")
            return False

    def close_serial_port(self) -> None:
        """关闭串口连接"""
        if self.serial_port is not None:
            try:
                if self.serial_port.is_open:
                    self.serial_port.close()
                    self.logger.debug("串口已关闭")
            except Exception as e:
                self.logger.error(f'关闭串口时出错: {e}')
            finally:
                self.serial_port = None

    @contextmanager
    def serial_port_context(self):
        """提供串口操作的上下文管理器
        
        Yields:
            Optional[serial.Serial]: 串口对象，如果打开失败则为None
        """
        if not self.open_serial_port():
            yield None
            return

        try:
            yield self.serial_port
        except serial.SerialException as e:
            self.logger.error(f'串口操作出错: {e}')
            self.close_serial_port()
            raise
        except Exception as e:
            self.logger.error(f'其他串口错误: {e}')
            self.close_serial_port()
            raise

    def check_serial_port(self) -> bool:
        """检查串口是否可用
        
        Returns:
            bool: 串口是否可用
        """
        if not self.port_config.get('port'):
            self.logger.error("串口配置中缺少port参数")
            return False
            
        try:
            with self.serial_port_context() as port:
                return port is not None
        except Exception as e:
            self.logger.error(f"检查串口时出错: {e}")
            return False

    def stop(self) -> None:
        """停止设备线程"""
        self.stop_event.set()
        self.logger.debug(f"{self.device_type} 设备线程停止中...")

        # 关闭串口连接
        self.close_serial_port()

        # 等待线程结束，但不超过5秒
        if self.is_alive():
            self.join(timeout=5.0)

        if self.is_alive():
            self.logger.warning(f"{self.device_type} 设备线程未能在预期时间内停止")
        else:
            self.logger.debug(f"{self.device_type} 设备线程已停止")
            
    @contextmanager
    def create_serial_port(self, port=None, baudrate=None, bytesize=None, parity=None, stopbits=None, xonxoff=None):
        """创建并返回串行端口的上下文管理器

        Args:
            port (str, optional): 串行端口名称。默认使用配置文件设置。
            baudrate (int, optional): 串行通信的波特率。默认使用配置文件设置。
            bytesize (int, optional): 数据位。默认使用配置文件设置。
            parity (str, optional): 奇偶校验。默认使用配置文件设置。
            stopbits (int, optional): 停止位。默认使用配置文件设置。
            xonxoff (int, optional): 软件流控制。默认使用配置文件设置。

        Yields:
            serial.Serial: 串行端口对象。
        """
        # 使用传入参数或配置参数
        port = port or self.port_config.get('port')
        baudrate = baudrate or self.port_config.get('baudrate', 1200)
        bytesize = bytesize or self.port_config.get('bytesize', 8)
        parity = parity or self.port_config.get('parity', 'E')
        stopbits = stopbits or self.port_config.get('stopbits', 1)
        xonxoff = xonxoff if xonxoff is not None else self.port_config.get('xonxoff', 0)
        
        if not port:
            self.logger.error("未指定串口")
            yield None
            return
            
        serial_port = None
        try:
            serial_port = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=bytesize,
                parity=parity,
                stopbits=stopbits,
                xonxoff=xonxoff,
                timeout=1  # 添加1秒超时，避免无限等待
            )
            
            # serial.Serial创建时如果成功，端口已经是打开状态
            yield serial_port
        except serial.SerialException as e:
            self.logger.error(f"创建串口失败: {e}")
            yield None
        finally:
            if serial_port and serial_port.is_open:
                serial_port.close()
                self.logger.debug('串口已关闭')


    def run(self):
        """设备主采集循环（增强版：持续重连机制）"""
        if not self.check_serial_port():
            self.logger.warning(f"========== {self.device_type} 设备串口初次检查不可用，将持续尝试重连 ==========")
            self.connection_healthy = False

        self.logger.info(f"========== {self.device_type} 设备采集线程启动 ==========")
        
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        while not self.stop_event.is_set():
            try:
                # 如果连接不健康，尝试智能重连
                if not self.connection_healthy:
                    if self.smart_reconnect():
                        consecutive_errors = 0  # 重连成功，重置错误计数
                        self.logger.info(f"{self.device_type} 连接已恢复，继续数据采集")
                    else:
                        # 重连失败，等待下次重连时机
                        time.sleep(0.5)
                        continue
                
                # 直接读取真实设备数据，移除模拟模式
                data = self._read_device_data()

                if data:
                    # 成功读取数据，更新健康状态
                    self.last_successful_read = time.time()
                    self.connection_healthy = True
                    
                    # 缓存最新有效数据，供状态检查等场景使用（不消费队列）
                    self._last_valid_data = data

                    # 确保队列不满，必要时丢弃旧数据
                    with self.lock:
                        if self.data_queue.full():
                            try:
                                old_data = self.data_queue.get_nowait()  # 丢弃最旧的数据
                                self.logger.warning(f"{self.device_type} 数据队列已满，丢弃旧数据")
                            except queue.Empty:
                                pass  # 理论上不会发生
                        
                        self.data_queue.put(data)
                    
                    # 重置错误计数
                    consecutive_errors = 0
                else:
                    # 数据读取失败但没有异常
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        self.logger.error(f"{self.device_type} 连续 {consecutive_errors} 次读取失败，标记连接不健康")
                        self.connection_healthy = False
                        consecutive_errors = 0
                
                # 优化采集间隔，提高响应速度
                time.sleep(0.5)
            except Exception as e:
                consecutive_errors += 1
                self.logger.error(f"{self.device_type} 数据采集异常: {str(e)}")
                
                # 如果连续错误过多，标记连接不健康
                if consecutive_errors >= max_consecutive_errors:
                    self.logger.error(f"{self.device_type} 连续 {consecutive_errors} 次错误，标记连接不健康")
                    self.connection_healthy = False
                    self.close_serial_port()
                    consecutive_errors = 0
                    
                time.sleep(self.retry_interval)

        self.logger.info(f"{self.device_type} 设备采集线程停止")

    def _try_physical_connection(self) -> bool:
        """尝试物理连接
        
        Returns:
            bool: 是否成功连接
        """
        for attempt in range(1, self.connection_retries + 1):
            with self.create_serial_port() as port:
                if port:
                    return True
            self.logger.warning(f"连接尝试 {attempt}/{self.connection_retries} 失败")
            time.sleep(self.retry_interval)
        return False

    # 移除调试模式启用方法

    # 移除模拟数据生成抽象方法

    @abstractmethod
    def _read_device_data(self):
        """读取真实设备数据（子类必须实现）"""
        pass

    def get_data(self):
        """从队列获取最新数据
        
        Returns:
            Any: 队列中的数据，如果队列为空则返回上次缓存的数据
        """
        try:
            # 获取队列中的最新数据
            data = self.data_queue.get_nowait()
            # 缓存最新的有效数据
            if data is not None:
                self._last_valid_data = data
            return data
        except queue.Empty:
            # 队列为空时，返回上次缓存的数据（如果有的话）
            return getattr(self, '_last_valid_data', None)

    def get_latest_data(self):
        """获取最近一次有效数据（不消费队列）"""
        return getattr(self, '_last_valid_data', None)

    def load_config(self, config_source) -> Optional[Dict[str, Any]]:
        """从配置文件加载参数

        参数:
            config_source: 配置文件路径或内存配置字典

        返回:
            Optional[Dict[str, Any]]: 配置参数字典，加载失败返回None
        """
        try:
            if isinstance(config_source, dict):
                self.logger.debug("使用内存注入的设备配置")
                return copy.deepcopy(config_source)

            config_path = str(config_source)
            # 尝试直接打开配置文件
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.logger.debug(f"配置文件加载成功: {config_path}")
                    return config
            else:
                # 尝试使用PathManager获取路径
                if os.path.basename(config_path) == 'comm_config.json':
                    path_from_manager = PathManager.get_config_path('comm_config.json')
                    
                    if os.path.exists(path_from_manager):
                        with open(path_from_manager, 'r', encoding='utf-8') as f:
                            config = json.load(f)
                            self.logger.debug(f"配置文件加载成功: {path_from_manager}")
                            return config
                    else:
                        self.logger.warning(f"配置文件不存在: {config_path} 或 {path_from_manager}")
                        return None
                else:
                    self.logger.warning(f"配置文件不存在: {config_path}")
                    return None

        except json.JSONDecodeError as e:
            self.logger.error(f"配置文件JSON格式错误: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"加载配置文件失败: {str(e)}")
            return None


