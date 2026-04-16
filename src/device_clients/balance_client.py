# balance_client.py
import time
import threading
from typing import Dict, Any, Optional

from src.device_clients.base_device import BaseDevice
from tmh_comm.protocols.balance_rs232 import BalanceRs232Protocol


class BalanceClient(BaseDevice):
    """电子天平客户端
    
    负责与电子天平进行通信，读取重量数据和发送去皮命令。
    通过继承BaseDevice实现串口通信基础功能。
    协议常量和解析逻辑委托给 tmh_comm.BalanceRs232Protocol。
    """
    
    # 读取超时设置(秒)
    READ_TIMEOUT = 0.1
    
    # 命令响应等待时间(秒)
    COMMAND_WAIT_TIME = 0.5
    
    def __init__(self, config_path: str):
        """初始化电子天平客户端
        
        Args:
            config_path: 配置文件路径
        """
        super().__init__(config_path, "Balance", "COM_RS232_Balance")
        
        # 验证配置
        if not self.config:
            raise ValueError(f"无法加载配置文件: {config_path}")
            
        # 移除模拟数据设置，专注实时数据采集
        
        # 数据锁
        self._data_lock = threading.Lock()
        
        # 最近一次有效数据
        self._last_valid_data = None
        
        # 命令执行标志，用于暂停数据采集
        self._command_executing = threading.Event()

        # RS232 协议封装
        self._rs232 = BalanceRs232Protocol()

    def _parse_data(self, data: str) -> Optional[float]:
        """解析天平数据
        
        解析电子天平输出的稳定重量数据。
        
        Args:
            data: 从串口读取的原始数据字符串，例如 "+00015.1 G S"
            
        Returns:
            float: 解析后的重量，解析失败返回None
        """
        weight = self._rs232.parse_line(data)
        if weight is None:
            self.logger.debug(f"非稳定或无效数据，忽略: {data}")
            return None
        self.logger.debug(f"成功解析重量: {weight}g")
        return weight

    def run(self):
        """重量采集主循环"""
        if not self.serial_port_available:
            self.logger.warning(f"========== {self.device_type} 设备串口初次检查不可用，将持续尝试重连 ==========")
            self.connection_healthy = False
            
        self.logger.info(f"========== {self.device_type} 重量采集启动 ==========")
        
        read_interval = 0.1  # 读取间隔(秒)
        
        while not self.stop_event.is_set():
            try:
                # 如果连接不健康，尝试智能重连
                if not self.connection_healthy:
                    if self.smart_reconnect():
                        self.logger.info(f"{self.device_type} 连接已恢复，继续重量采集")
                    else:
                        time.sleep(1.0)
                        continue

                # 如果正在执行命令，暂停数据采集
                if self._command_executing.is_set():
                    time.sleep(0.1)
                    continue
                
                # 直接读取真实设备数据，移除模拟模式
                # 真实设备模式
                with self.serial_port_context() as ser:
                    if ser:
                        # 设置临时超时
                        original_timeout = ser.timeout
                        ser.timeout = self.READ_TIMEOUT
                        
                        try:
                            # 非阻塞读取数据
                            raw_data = ser.readline().decode('utf-8', 'ignore').strip()
                            if raw_data and self._rs232.STABLE_MARKER in raw_data:
                                weight = self._parse_data(raw_data)
                                if weight is not None:
                                    data = {
                                        'timestamp': time.time(),
                                        'weight': weight
                                    }
                                    
                                    # 移除数据滤波功能，直接使用原始数据
                                    
                                    # 更新最近数据和队列
                                    with self._data_lock:
                                        self._last_valid_data = data
                                    
                                    # 确保队列不满
                                    try:
                                        self.data_queue.put_nowait(data)
                                    except Exception:
                                        try:
                                            # 如果队列满，清除一项
                                            self.data_queue.get_nowait()
                                            self.data_queue.put_nowait(data)
                                        except Exception:
                                            pass
                        finally:
                            # 恢复原始超时
                            ser.timeout = original_timeout
                
                # 短暂休眠
                time.sleep(read_interval)
                
            except Exception as e:
                self.logger.error(f"重量采集异常: {e}")
                time.sleep(0.5)  # 出错后短暂休眠
        
        self.logger.info(f"========== {self.device_type} 重量采集停止 ==========")

    def send_tare_command(self) -> bool:
        """发送去皮指令

        向天平发送去皮命令，使当前显示归零。
        串口 I/O 在此处完成，响应解析委托给 BalanceRs232Protocol.parse_tare_response()。

        Returns:
            bool: 操作是否成功
        """
        self.logger.info("========== 开始执行天平去皮命令 ==========")

        if not self.serial_port_available:
            self.logger.warning("设备未连接，跳过天平去皮指令")
            return False

        # 暂停数据采集
        self._command_executing.set()
        self.logger.info("已暂停数据采集线程")

        try:
            with self.serial_port_context() as ser:
                if not ser:
                    self.logger.error("串口不可用，无法发送去皮命令")
                    return False

                ser.reset_input_buffer()

                # 发送去皮命令（常量来自协议层）
                tare_cmd = self._rs232.TARE_CMD
                ser.write(tare_cmd)
                self.logger.info(f"已发送去皮命令: {tare_cmd!r}")

                # 等待设备处理
                time.sleep(1.0)

                # 累积读取响应，处理分段传输
                accumulated_response = ""
                max_attempts = 15

                for attempt in range(max_attempts):
                    waiting_bytes = ser.in_waiting
                    if waiting_bytes > 0:
                        new_data = ser.read(waiting_bytes).decode('utf-8', 'ignore')
                        accumulated_response += new_data
                        self.logger.debug(f"读取数据 ({attempt+1}): {new_data!r}")

                        # 同时检测到 A00 和稳定数据时可提前退出
                        if (self._rs232.TARE_ACK_MARKER in accumulated_response
                                and self._rs232.STABLE_MARKER in accumulated_response):
                            self.logger.debug("检测到完整响应（A00 + 稳定数据），停止读取")
                            break

                    time.sleep(0.15)

                # 委托协议层解析响应
                if not accumulated_response.strip():
                    self.logger.warning("未收到任何响应数据")
                    self.logger.warning("========== 天平去皮命令未能确认执行 ==========")
                    return False

                self.logger.info(f"最终累积响应: {accumulated_response!r}")
                result = self._rs232.parse_tare_response(accumulated_response)

                if result.success:
                    weight_info = f", 重量={result.weight}g" if result.weight is not None else ""
                    reason = "A00标志" if result.a00_found else "零重量数据"
                    self.logger.info(f"========== 天平去皮成功（{reason}{weight_info}） ==========")
                    return True

                self.logger.warning("========== 天平去皮命令未能确认执行 ==========")
                return False

        except Exception as e:
            self.logger.error(f"========== 执行去皮命令失败: {e} ==========")
            return False

        finally:
            self._command_executing.clear()
            self.logger.info("已恢复数据采集线程")

    # 移除模拟数据生成功能，专注于实时数据采集

    def _read_device_data(self) -> Optional[Dict[str, Any]]:
        """读取设备数据，实现基类抽象方法
        
        通过串口读取电子天平当前稳定的重量数据。
        
        Returns:
            Dict: 包含重量数据的字典，读取失败返回None
        """
        try:
            with self.serial_port_context() as ser:
                if not ser:
                    return None
                
                # 设置临时超时
                original_timeout = ser.timeout
                ser.timeout = self.READ_TIMEOUT
                
                try:
                    # 检查串口是否有数据
                    if ser.in_waiting > 0:
                        raw_data = ser.readline().decode('utf-8', 'ignore').strip()
                        if raw_data and self._rs232.STABLE_MARKER in raw_data:
                            weight = self._parse_data(raw_data)
                            if weight is not None:
                                data = {
                                    'timestamp': time.time(), 
                                    'weight': weight
                                }
                                return data
                finally:
                    # 恢复原始超时
                    ser.timeout = original_timeout
        except Exception as e:
            self.logger.error(f"读取设备数据错误: {e}")
        
        return None
    
    # 移除所有滤波器相关功能，专注于实时数据采集

    def get_latest_weight(self) -> Optional[float]:
        """获取最新重量数据
        
        Returns:
            float: 最新重量值，无数据时返回None
        """
        with self._data_lock:
            if self._last_valid_data:
                return self._last_valid_data.get('weight')
        return None


if __name__ == "__main__":
    from src.utils.path_manager import PathManager
    print(f"项目根目录: {PathManager.get_project_root()}")
    
    # 读取配置文件
    config_path = PathManager.get_config_path('comm_config.json')
    
    # 初始化并测试天平客户端
    balance_client = BalanceClient(config_path=config_path)
    
    # 启用调试模式测试
    # 已移除调试模式功能
    
    try:
        # 启动线程
        balance_client.start()
        print("天平数据采集已启动 (按Ctrl+C停止)...")
        
        # 测试采集循环
        for i in range(10):
            time.sleep(1)
            weight = balance_client.get_latest_weight()
            print(f"当前重量: {weight}g")
        
        # 测试去皮功能
        print("\n测试去皮功能...")
        result = balance_client.send_tare_command()
        print(f"去皮结果: {'成功' if result else '失败'}")
        
        # 继续采集一段时间
        for i in range(5):
            time.sleep(1)
            weight = balance_client.get_latest_weight()
            print(f"去皮后重量: {weight}g")
            
    except KeyboardInterrupt:
        print("\n用户中断，停止采集...")
    finally:
        # 停止线程
        balance_client.stop()
        print("天平客户端已停止")
