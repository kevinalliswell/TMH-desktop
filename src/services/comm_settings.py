# src/services/comm_settings.py
import json
import os

import serial.tools.list_ports
from typing import Dict, Any, List
from src.utils.logger import get_logger
from src.utils.path_manager import PathManager

# 配置文件路径
CONFIG_PATH = PathManager.get_config_path("comm_config.json")
class CommSettings:
    """通信参数配置类"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.logger.debug("初始化通信设置管理器")
        self.config_file = CONFIG_PATH
        self.default_settings = {
            "COM_RS485_MFC": {
                "port": "COM1",
                "baudrate": 9600,
                "bytesize": 8,
                "parity": "E",
                "stopbits": 1,
                "timeout": 0.5
            },
            "COM_RS485_TEMP": {
                "port": "COM2", 
                "baudrate": 9600,
                "bytesize": 8,
                "parity": "N",
                "stopbits": 1,
                "timeout": 1.0,
                "slave_address": 0,
                "start_reg": 0,
                "reg_count": 9,
                "TEMP_CHANNELS": ["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9"],
                "scale": 0.1,
                "signed_registers": False
            },
            "COM_RS232_Balance": {
                "port": "COM3",
                "baudrate": 1200,
                "bytesize": 8,
                "parity": "E",
                "stopbits": 1,
                "timeout": 1.0
            },
            "SAMPLING": {
                "interval_s": 1.0
            },
            "PERFORMANCE_CONFIG": {
                "data_collection_interval": 0.2,
                "experiment_data_interval": 1.0,
                "heartbeat_timeout": 5.0
            },
            "SLAVE_ADDRESS_MFC": {
                "H2": 1,
                "N2": 2,
                "CO2": 3,
                "CO": 4
            },
            "SLAVE_ADDRESS_TEMP": {
                "TEMP": 0
            },
            "FLOW_SCALING": {
                "H2": 0.1,
                "N2": 1.0,
                "CO2": 0.1,
                "CO": 0.1
            }
        }
        self.settings = self.load_settings()
        
    def load_settings(self) -> Dict[str, Any]:
        """加载配置"""
        try:
            # 如果配置文件不存在，创建默认配置
            if not os.path.exists(self.config_file):
                self.logger.debug(f"配置文件不存在，创建默认配置: {self.config_file}")
                return self._create_default_config()
                
            self.logger.debug(f"正在加载配置文件: {self.config_file}")
            with open(self.config_file, 'r', encoding='utf-8') as f:
                loaded_settings = json.load(f)
                self.logger.debug(f"加载的配置: {loaded_settings}")
                
                # 验证和补充配置
                validated_settings = self._validate_and_complete_settings(loaded_settings)
                self.logger.debug("配置加载完成")
                return validated_settings
                
        except Exception as e:
            self.logger.error(f"加载配置文件失败: {str(e)}")
            return self.default_settings
            
    def _create_default_config(self) -> Dict[str, Any]:
        """创建默认配置文件"""
        try:
            # 确保配置目录存在
            PathManager.ensure_directory_exists(os.path.dirname(self.config_file))
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.default_settings, f, indent=4)
            return self.default_settings
        except Exception as e:
            self.logger.error(f"创建默认配置文件失败: {str(e)}")
            return self.default_settings

    def _validate_and_complete_settings(self, loaded_settings: Dict[str, Any]) -> Dict[str, Any]:
        """验证和补充配置信息"""
        try:
            # 确保所有必需的设备配置都存在
            for device, default_config in self.default_settings.items():
                if device not in loaded_settings:
                    self.logger.warning(f"缺少设备配置，使用默认值: {device}")
                    loaded_settings[device] = default_config.copy()
                elif device.startswith("COM_"):
                    # 验证串口参数（传入 device_key 以便精确判断设备类型）
                    self._validate_com_settings(loaded_settings[device], default_config, device)
                elif device == "SAMPLING":
                    # 验证采样配置
                    self._validate_sampling_settings(loaded_settings[device], default_config)

            # 验证顶级配置
            self._validate_top_level_configs(loaded_settings)

            return loaded_settings
        except Exception as e:
            self.logger.error(f"验证和补充配置失败: {str(e)}")
            return self.default_settings

    def _validate_com_settings(self, device_settings: Dict[str, Any],
                               default_config: Dict[str, Any],
                               device_key: str = "") -> None:
        """验证串口参数配置

        Args:
            device_settings: 当前设备配置
            default_config: 默认配置（用于补全缺失字段）
            device_key: 设备配置键名，如 "COM_RS232_Balance"
        """
        # 验证必需的串口参数
        for param in ["baudrate", "bytesize", "parity", "stopbits", "timeout"]:
            if param not in device_settings:
                self.logger.warning(f"缺少串口参数，使用默认值: {param}")
                device_settings[param] = default_config[param]

        # 天平波特率固定为 1200，通过 device_key 精确判断
        if device_key == "COM_RS232_Balance":
            if device_settings.get("baudrate") != 1200:
                self.logger.warning(
                    f"天平波特率不正确，更正为1200 (当前值: {device_settings.get('baudrate')})"
                )
                device_settings["baudrate"] = 1200

    def _validate_sampling_settings(self, sampling_settings: Dict[str, Any], default_config: Dict[str, Any]) -> None:
        """验证采样配置"""
        if "interval_s" not in sampling_settings:
            self.logger.warning("缺少采样间隔配置，使用默认值")
            sampling_settings["interval_s"] = default_config["interval_s"]

    def _validate_top_level_configs(self, settings: Dict[str, Any]) -> None:
        """验证顶级配置"""
        # 验证MFC从站地址配置
        if "SLAVE_ADDRESS_MFC" not in settings:
            self.logger.warning("缺少MFC从站地址配置，使用默认值")
            settings["SLAVE_ADDRESS_MFC"] = self.default_settings["SLAVE_ADDRESS_MFC"].copy()
        
        # 验证温控仪表从站地址配置
        if "SLAVE_ADDRESS_TEMP" not in settings:
            self.logger.warning("缺少温控仪表从站地址配置，使用默认值")
            settings["SLAVE_ADDRESS_TEMP"] = self.default_settings["SLAVE_ADDRESS_TEMP"].copy()
        
        # 验证流量缩放配置
        if "FLOW_SCALING" not in settings:
            self.logger.warning("缺少流量缩放配置，使用默认值")
            settings["FLOW_SCALING"] = self.default_settings["FLOW_SCALING"].copy()
        
        # 验证性能配置
        if "PERFORMANCE_CONFIG" not in settings:
            self.logger.warning("缺少性能配置，使用默认值")
            settings["PERFORMANCE_CONFIG"] = self.default_settings["PERFORMANCE_CONFIG"].copy()

        # 验证温控仪表配置中的嵌套项
        if "COM_RS485_TEMP" in settings:
            temp_config = settings["COM_RS485_TEMP"]
            default_temp = self.default_settings["COM_RS485_TEMP"]
            
            # 验证温控仪表参数
            for param in ["slave_address", "start_reg", "reg_count", "scale", "signed_registers"]:
                if param not in temp_config:
                    self.logger.warning(f"缺少温控仪表参数，使用默认值: {param}")
                    temp_config[param] = default_temp[param]
            
            # 验证温度通道配置
            if "TEMP_CHANNELS" not in temp_config:
                self.logger.warning("缺少温度通道配置，使用默认值")
                temp_config["TEMP_CHANNELS"] = default_temp["TEMP_CHANNELS"].copy()

    def save_settings(self) -> None:
        """保存配置"""
        try:
            # 确保配置目录存在
            PathManager.ensure_file_directory_exists(self.config_file)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
            self.logger.debug(f"配置已保存到: {self.config_file}")
        except Exception as e:
            self.logger.error(f"保存配置文件失败: {str(e)}")
            
    def get_mfc_config(self) -> Dict[str, Any]:
        """获取MFC配置"""
        return self.settings.get("COM_RS485_MFC", {})
    
    def get_temp_config(self) -> Dict[str, Any]:
        """获取温控仪表配置"""
        return self.settings.get("COM_RS485_TEMP", {})
    
    def get_balance_config(self) -> Dict[str, Any]:
        """获取天平配置"""
        return self.settings.get("COM_RS232_Balance", {})
    
    def get_sampling_config(self) -> Dict[str, Any]:
        """获取采样配置"""
        return self.settings.get("SAMPLING", {})
    
    def get_mfc_slave_addresses(self) -> Dict[str, int]:
        """获取MFC从站地址"""
        # 配置文件中SLAVE_ADDRESS_MFC是顶级配置
        return self.settings.get("SLAVE_ADDRESS_MFC", {})
    
    def get_flow_scaling(self) -> Dict[str, float]:
        """获取流量缩放配置"""
        # 配置文件中FLOW_SCALING是顶级配置
        return self.settings.get("FLOW_SCALING", {})
    
    def get_temp_channels(self) -> List[str]:
        """获取温度通道列表"""
        temp_config = self.get_temp_config()
        return temp_config.get("TEMP_CHANNELS", [])

    @staticmethod
    def get_available_ports() -> List[str]:
        """获取可用串口列表"""
        try:
            ports = [port.device for port in serial.tools.list_ports.comports()]
            return ports if ports else ["COM1", "COM2", "COM3"]
        except Exception as e:
            logger = get_logger(__name__)
            logger.error(f"获取可用串口列表失败: {str(e)}")
            return ["COM1", "COM2", "COM3"] 