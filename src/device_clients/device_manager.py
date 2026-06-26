# device_manager.py
import os
import time
import threading
import traceback
import atexit

# 设备客户端类将通过外部注册，不在此处直接导入
from src.utils.logger import get_logger
from src.utils.path_manager import PathManager
from tmh_comm.standard import (
    build_balance_frame,
    build_mfc_frame,
    build_temp_frame,
)
import json

class DeviceManager:
    def __init__(self, config_path: str | None = None):
        if config_path is None:
            config_path = PathManager.get_config_path('comm_config.json')
        # 设备注册表 - 支持动态注册
        self.devices = {}
        self._devices_lock = threading.Lock()  # 保护设备字典的线程安全访问
        self.temp = None
        self.balance = None
        self.multi_mfc = None
        self.running = False
        self.config_path = config_path

        # 初始化日志系统
        self.logger = get_logger("设备管理器")

        # 加载配置文件
        self.config = self._load_config()

        # 不再自动初始化设备，改为手动注册

        # 注册退出处理函数
        atexit.register(self.stop_all)

    def _load_config(self):
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                self.logger.debug(f"成功加载配置文件: {self.config_path}")
                return config
        except Exception as e:
            self.logger.error(f"加载配置文件失败: {str(e)}")
            self.logger.warning("将使用默认配置")
            return self._get_default_config()

    def _get_default_config(self):
        """返回默认配置"""
        return {
            "COM_RS485_MFC": {
                "port": "COM1",
                "baudrate": 9600,
                "bytesize": 8,
                "parity": "E",
                "stopbits": 1,
                "timeout": 0.5,
                "SLAVE_ADDRESS_MFC": {
                    "H2": 1,
                    "N2": 2,
                    "CO2": 3,
                    "CO": 4
                }
            },
            "COM_RS485_TEMP": {
                "port": "COM1",
                "baudrate": 9600,
                "bytesize": 8,
                "parity": "N",
                "stopbits": 1,
                "timeout": 1.0,
                "slave_address": 0
            },
            "SLAVE_ADDRESS_TEMP": {
                "TEMP": 0
            },
            "COM_RS232_Balance": {
                "port": "COM4",
                "baudrate": 1200,
                "bytesize": 8,
                "parity": "E",
                "stopbits": 1,
                "timeout": 1.0
            }
        }


    def set_data_handler(self, data_handler):
        """设置数据处理器"""
        self.data_handler = data_handler
        self.data_handler.set_device_manager(self)

    # ============================== 
    # 新增：设备动态注册功能
    # ==============================
    def register_device(self, name: str, device_instance):
        """注册设备实例
        
        Args:
            name: 设备名称
            device_instance: 设备实例
        """
        self.devices[name] = device_instance
        self.logger.info(f"设备 {name} 注册成功")
        
        # 为了兼容原有逻辑，同时更新传统属性
        if name.lower() == "balance":
            self.balance = device_instance
        elif name.lower() == "temp":
            self.temp = device_instance
        elif name.lower() == "mfc":
            self.multi_mfc = device_instance

    def unregister_device(self, name: str):
        """注销设备
        
        Args:
            name: 设备名称
        """
        if name in self.devices:
            device = self.devices[name]
            if hasattr(device, 'stop'):
                device.stop()
            del self.devices[name]
            self.logger.info(f"设备 {name} 注销成功")
            
            # 清理传统属性
            if name.lower() == "balance":
                self.balance = None
            elif name.lower() == "temp":
                self.temp = None
            elif name.lower() == "mfc":
                self.multi_mfc = None

    def list_devices(self):
        """列出所有已注册的设备"""
        return list(self.devices.keys())

    def get_device(self, name: str):
        """获取指定设备实例"""
        return self.devices.get(name)

    def start_device(self, name: str):
        """启动指定设备"""
        device = self.devices.get(name)
        if device and hasattr(device, 'start'):
            device.start()
            self.running = True
            self.logger.info(f"设备 {name} 启动成功")
        else:
            self.logger.error(f"设备 {name} 不存在或无法启动")

    def stop_device(self, name: str):
        """停止指定设备"""
        device = self.devices.get(name)
        if device and hasattr(device, 'stop'):
            device.stop()
            self.logger.info(f"设备 {name} 停止成功")
        else:
            self.logger.error(f"设备 {name} 不存在或无法停止")

    def get_status(self, name: str = None):
        """获取设备状态
        
        Args:
            name: 设备名称，如果为None则返回所有设备状态
        """
        if name:
            device = self.devices.get(name)
            if device and hasattr(device, 'get_data'):
                return device.get_data()
            return None
        else:
            # 返回所有设备状态（兼容原有逻辑）
            return self.get_status_legacy()

    def get_all_status(self):
        """获取所有设备状态（新接口）"""
        status = {}
        for name, device in self.devices.items():
            if hasattr(device, 'get_data'):
                status[name] = {
                    "data": device.get_data(),
                    "running": getattr(device, 'is_alive', lambda: False)()
                }
            else:
                status[name] = {"data": None, "running": False}
        return status

    def get_status_legacy(self):
        """获取所有设备状态（仅标准化帧）"""
        return {
            "frames": self._collect_standard_frames(),
            "timestamp": time.time()
        }

    def _collect_standard_frames(self) -> dict:
        """直接从设备采集并构建标准化数据帧（StandardFrame）"""
        frames = {}

        # 温度帧
        temp_device = self.devices.get("Temp") or self.temp
        if temp_device:
            temp_data = temp_device.get_data()
            if temp_data:
                model = getattr(temp_device, "model", "TEMP-CTRL")
                meta = {}
                if hasattr(temp_device, "port_config"):
                    meta = {
                        "port": temp_device.port_config.get("port"),
                        "baudrate": temp_device.port_config.get("baudrate"),
                        "slave_address": getattr(temp_device, "slave_address", None),
                    }
                frame = build_temp_frame(model=model, temperatures=temp_data, meta=meta)
                frame.timestamp = temp_data.get("timestamp", time.time())
                frames["temperature"] = frame

        # 重量帧
        balance_device = self.devices.get("Balance") or self.balance
        if balance_device:
            weight_data = balance_device.get_data()
            if weight_data:
                model = getattr(balance_device, "model", "BALANCE-1200")
                meta = {}
                if hasattr(balance_device, "port_config"):
                    meta = {
                        "port": balance_device.port_config.get("port"),
                        "baudrate": balance_device.port_config.get("baudrate"),
                    }
                frame = build_balance_frame(model=model, weight=weight_data.get("weight"), meta=meta)
                frame.timestamp = weight_data.get("timestamp", time.time())
                frames["weight"] = frame

        # 流量帧（按气体）
        mfc_device = self.devices.get("MFC") or self.multi_mfc
        if mfc_device:
            flows = getattr(mfc_device, "current_flows", {})
            setpoints = getattr(mfc_device, "setpoints", {})
            model = getattr(mfc_device, "model", "MQV0020BS")
            meta_base = {}
            if hasattr(mfc_device, "port_config"):
                meta_base = {
                    "port": mfc_device.port_config.get("port"),
                    "baudrate": mfc_device.port_config.get("baudrate"),
                }
            flow_frames = {}
            for gas_type, pv in flows.items():
                sv = setpoints.get(gas_type)
                if pv is None and sv is None:
                    continue
                meta = dict(meta_base)
                if hasattr(mfc_device, "slave_addresses"):
                    meta["slave_address"] = mfc_device.slave_addresses.get(gas_type)
                frame = build_mfc_frame(
                    model=model,
                    gas_type=gas_type,
                    pv=pv,
                    sv=sv,
                    meta=meta,
                )
                frame.timestamp = time.time()
                flow_frames[gas_type] = frame
            if flow_frames:
                frames["flows"] = flow_frames

        return frames

    def start_all(self):
        """启动所有设备线程"""
        self.running = True

        # 启动所有注册的设备
        for name, device in self.devices.items():
            try:
                if hasattr(device, 'start') and hasattr(device, 'is_alive'):
                    if not device.is_alive():
                        device.start()
                        self.logger.debug(f"{name} 线程已启动")
                    else:
                        self.logger.debug(f"{name} 线程已在运行")
            except Exception as e:
                self.logger.error(f"启动 {name} 线程失败: {str(e)}")

    def stop_all(self):
        """停止所有设备线程并清理引用"""
        with self._devices_lock:
            if not self.devices:
                return

            self.running = False
            self.logger.debug("正在停止所有设备线程...")

            # 停止所有注册的设备
            for name, device in self.devices.items():
                try:
                    if hasattr(device, 'stop'):
                        device.stop()
                        self.logger.debug(f"{name} 线程已停止")
                except Exception as e:
                    self.logger.error(f"停止 {name} 线程失败: {str(e)}")

            # 清理设备引用
            self.devices.clear()
            self.temp = None
            self.balance = None
            self.multi_mfc = None

            self.logger.debug("所有设备线程已停止，引用已清理")

    def set_flow(self, gas: str, value: float) -> bool:
        """
        设置指定气体的流量
        
        Args:
            gas: 气体类型 ('CO', 'CO2', 'N2', 'H2')
            value: 流量值 (L/min)
            
        Returns:
            bool: 设置是否成功
            
        Raises:
            ValueError: 当流量值无效时
        """
        self.logger.debug(f"设置{gas}流量为{value/10.0} L/min")
        
        # 从注册的设备中获取MFC
        mfc_device = self.devices.get("MFC") or self.multi_mfc
        if not mfc_device:
            self.logger.error("多通道质量流量计未注册")
            return False

        # 检查设备连接状态，避免在开发环境下发送无效指令
        if not getattr(mfc_device, 'serial_port_available', False):
            self.logger.warning(f"MFC设备未连接，跳过{gas}流量设置指令")
            return False

        if gas not in mfc_device.slave_addresses:
            self.logger.error(f"未知气体: {gas}")
            return False

        try:
            result = mfc_device.set_sp_value(gas, float(value))
            if result:
                self.logger.debug(f"成功设置{gas}流量为{value/10.0}")
            else:
                self.logger.warning(f"设置{gas}流量为{value/10.0}失败")
            return result
        except ValueError:
            self.logger.error(f"流量值不是有效数字: {value/10.0}")
            return False
        except Exception as e:
            self.logger.error(f"设置{gas}流量出错: {str(e)}")
            return False

    def tare_balance(self):
        """天平去皮操作"""
        self.logger.info("DeviceManager.tare_balance被调用")
        
        # 从注册的设备中获取天平
        balance_device = self.devices.get("Balance") or self.balance
        if not balance_device:
            self.logger.error("天平设备未注册")
            return False

        # 检查设备连接状态，避免在开发环境下发送无效指令
        if not getattr(balance_device, 'serial_port_available', False):
            self.logger.warning("天平设备未连接，跳过去皮指令")
            return False

        try:
            # 返回实际的去皮命令结果
            result = balance_device.send_tare_command()
            self.logger.info(f"天平去皮命令执行结果: {result}")
            return result
        except Exception as e:
            self.logger.error(f"天平去皮出错: {str(e)}")
            return False

    # 移除调试模式切换功能，专注于实时设备通信

    # 内部注册名 -> 用户可见的中文名
    _DEVICE_DISPLAY_NAMES = {
        "Temp": "温度控制器",
        "Balance": "电子天平",
        "MFC": "气体流量计",
    }

    def get_connection_status(self):
        """获取设备连接状态和错误信息（线程安全）

        返回值语义：
        - is_connected=True  + error_msg=""    -> 全部设备已连接
        - is_connected=True  + error_msg 非空  -> 部分设备已连接
        - is_connected=False                   -> 全部断开

        Returns:
            tuple: (is_connected, device_names, error_msg)
        """
        connected_devices = []
        error_messages = []

        with self._devices_lock:
            devices_snapshot = dict(self.devices)

        device_validators = {
            "Temp": lambda data: data and any(
                v is not None for v in data.values() if isinstance(v, (int, float))
            ),
            "Balance": lambda data: data and data.get('weight') is not None,
            "MFC": self._validate_mfc_payload_data,
        }

        for name, device in devices_snapshot.items():
            display = self._DEVICE_DISPLAY_NAMES.get(name, name)
            validator = device_validators.get(name, lambda data: data is not None)
            status = self._check_device_status(device, name, validator)

            if status['connected']:
                connected_devices.append(display)
            else:
                # 错误信息也替换为中文设备名
                error_messages.append(
                    status['error'].replace(name, display, 1)
                )

        is_connected = bool(connected_devices)
        device_names = ", ".join(connected_devices) if connected_devices else ""
        error_msg = "; ".join(error_messages[:2]) if error_messages else ""

        return is_connected, device_names, error_msg
    
    def _check_device_status(self, device, device_name, data_validator):
        """检查单个设备状态
        
        Args:
            device: 设备对象
            device_name: 设备名称
            data_validator: 数据验证函数
            
        Returns:
            dict: 包含连接状态信息的字典
        """
        if not device:
            return {
                'connected': False,
                'name': device_name,
                'error': f"{device_name}: 未初始化"
            }
        
        # 检查串口是否可用
        if not (hasattr(device, 'serial_port_available') and device.serial_port_available):
            return {
                'connected': False,
                'name': device_name,
                'error': f"{device_name}: 串口不可用"
            }
        
        # 检查线程是否运行
        if not (hasattr(device, 'is_alive') and device.is_alive()):
            return {
                'connected': False,
                'name': device_name,
                'error': f"{device_name}: 线程未运行"
            }
        
        # 检查数据有效性（避免消费设备数据队列）
        try:
            if hasattr(device, 'get_latest_data'):
                recent_data = device.get_latest_data()
            elif hasattr(device, '_last_valid_data'):
                recent_data = device._last_valid_data
            elif hasattr(device, 'get_data'):
                # 兜底：仅在无最新缓存时才消费队列
                recent_data = device.get_data()
            else:
                recent_data = None

            if recent_data is not None:
                if data_validator(recent_data):
                    return {
                        'connected': True,
                        'name': device_name,
                        'error': ""
                    }
                else:
                    return {
                        'connected': False,
                        'name': device_name,
                        'error': f"{device_name}: 通信超时或无数据"
                    }
            return {
                'connected': False,
                'name': device_name,
                'error': f"{device_name}: 通信超时或无数据"
            }
        except Exception as e:
            return {
                'connected': False,
                'name': device_name,
                'error': f"{device_name}: 数据获取异常 - {str(e)[:30]}"
            }
    
    def _validate_mfc_data_for_device(self, device):
        """验证MFC设备数据有效性"""
        if not device:
            return False
        
        try:
            # 检查是否有任何气体通道有有效数据
            if hasattr(device, 'get_latest_data'):
                if self._validate_mfc_payload_data(device.get_latest_data()):
                    return True
            elif hasattr(device, '_last_valid_data'):
                if self._validate_mfc_payload_data(device._last_valid_data):
                    return True

            flows = getattr(device, 'current_flows', {})
            return self._validate_mfc_payload_data(flows)
        except Exception:
            return False

    def _validate_mfc_payload_data(self, data):
        """Return True when an MFC payload contains at least one PV/SV/flow value."""
        if not isinstance(data, dict) or not data:
            return False

        channel_value_keys = ("PV", "pv", "SV", "sv")

        for key in channel_value_keys:
            if key in data and self._is_valid_mfc_numeric_value(data.get(key)):
                return True

        for key, value in data.items():
            if key == "timestamp":
                continue

            if isinstance(value, dict):
                for channel_key in channel_value_keys:
                    if (
                        channel_key in value
                        and self._is_valid_mfc_numeric_value(value.get(channel_key))
                    ):
                        return True
            elif self._is_valid_mfc_numeric_value(value):
                return True

        return False

    @staticmethod
    def _is_valid_mfc_numeric_value(value):
        return value is not None and isinstance(value, (int, float)) and not isinstance(value, bool)

    def _validate_mfc_data(self):
        """验证MFC数据有效性（兼容旧接口）"""
        mfc_device = self.devices.get("MFC") or self.multi_mfc
        return self._validate_mfc_data_for_device(mfc_device)


# 使用示例（已简化为仅创建配置文件）
if __name__ == "__main__":
    try:
        config_path = PathManager.get_config_path("comm_config.json")
        print(f"配置文件路径: {config_path}")

        # 初始化设备管理器
        dm = DeviceManager(config_path=config_path)

        # 如果配置文件不存在，创建默认配置
        if not os.path.exists(config_path):
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(dm._get_default_config(), f, indent=4)
                print(f"已创建默认配置文件: {config_path}")
        
        print("设备管理器初始化完成，请通过 register_device() 方法注册设备")

    except Exception as e:
        print(f"程序出现异常: {str(e)}")
        import traceback
        traceback.print_exc()
