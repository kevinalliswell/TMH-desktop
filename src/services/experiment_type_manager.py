# src/services/experiment_type_manager.py
"""
实验类型管理器
统一管理标准实验类型和自定义实验类型，解决枚举与动态配置的冲突问题
"""

from enum import Enum
from typing import Dict, List, Optional, Any, Union
import logging
import json
import os
from datetime import datetime

from src.utils.path_manager import PathManager
from src.services.experiment_modes import ExperimentModeManager


class ExperimentTypeCategory(Enum):
    """实验类型分类"""
    STANDARD = "standard"  # 标准实验类型
    CUSTOM = "custom"      # 自定义实验类型


class ExperimentTypeInfo:
    """实验类型信息类"""
    
    def __init__(self, type_id: str, name: str, description: str = "", 
                 category: ExperimentTypeCategory = ExperimentTypeCategory.STANDARD,
                 enabled: bool = True, **kwargs):
        self.type_id = type_id
        self.name = name
        self.description = description
        self.category = category
        self.enabled = enabled
        self.extra_data = kwargs
        
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "type_id": self.type_id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "enabled": self.enabled,
            **self.extra_data
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExperimentTypeInfo':
        """从字典创建实例"""
        return cls(
            type_id=data["type_id"],
            name=data["name"],
            description=data.get("description", ""),
            category=ExperimentTypeCategory(data.get("category", "standard")),
            enabled=data.get("enabled", True),
            **{k: v for k, v in data.items() 
               if k not in ["type_id", "name", "description", "category", "enabled"]}
        )


class ExperimentTypeManager:
    """实验类型管理器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.experiment_mode_manager = ExperimentModeManager()
        
        # 标准实验类型定义
        self._standard_types = self._initialize_standard_types()
        
        # 自定义实验类型
        self._custom_types = {}
        
        # 加载自定义类型
        self._load_custom_types()
    
    def _initialize_standard_types(self) -> Dict[str, ExperimentTypeInfo]:
        """初始化标准实验类型"""
        return {
            "GB_13241_2017": ExperimentTypeInfo(
                type_id="GB_13241_2017",
                name="GB/T 13241-2017 铁矿石还原性测定方法",
                description="标准铁矿石还原性测定实验",
                category=ExperimentTypeCategory.STANDARD,
                enabled=True
            ),
            "GB_13242_2017": ExperimentTypeInfo(
                type_id="GB_13242_2017", 
                name="GB/T 13242-2017 铁矿石低温粉化试验方法",
                description="低温条件下铁矿石粉化特性测试",
                category=ExperimentTypeCategory.STANDARD,
                enabled=True
            ),
            "GB_13240_2018": ExperimentTypeInfo(
                type_id="GB_13240_2018",
                name="GB/T 13240-2018 球团矿自由膨胀指数测定方法", 
                description="球团矿在还原气氛下的膨胀特性测试",
                category=ExperimentTypeCategory.STANDARD,
                enabled=True
            )
        }
    
    def _load_custom_types(self):
        """从配置文件加载自定义实验类型"""
        try:
            config_path = PathManager.get_config_path("experiment_modes.json")
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                custom_modes = config.get("experiment_modes", {}).get("custom_modes", {})
                for mode_id, mode_data in custom_modes.items():
                    if mode_data.get("enabled", True):
                        type_info = ExperimentTypeInfo(
                            type_id=mode_id,
                            name=mode_data.get("name", mode_id),
                            description=mode_data.get("description", ""),
                            category=ExperimentTypeCategory.CUSTOM,
                            enabled=mode_data.get("enabled", True),
                            created_by=mode_data.get("created_by", "unknown"),
                            created_time=mode_data.get("created_time", ""),
                            stages=mode_data.get("stages", [])
                        )
                        self._custom_types[mode_id] = type_info
                        
        except Exception as e:
            self.logger.error(f"加载自定义实验类型失败: {str(e)}")
    
    def get_all_types(self) -> Dict[str, ExperimentTypeInfo]:
        """获取所有实验类型"""
        all_types = {}
        all_types.update(self._standard_types)
        all_types.update(self._custom_types)
        return all_types
    
    def get_standard_types(self) -> Dict[str, ExperimentTypeInfo]:
        """获取标准实验类型"""
        return self._standard_types.copy()
    
    def get_custom_types(self) -> Dict[str, ExperimentTypeInfo]:
        """获取自定义实验类型"""
        return self._custom_types.copy()
    
    def get_enabled_types(self) -> Dict[str, ExperimentTypeInfo]:
        """获取启用的实验类型"""
        return {k: v for k, v in self.get_all_types().items() if v.enabled}
    
    def get_type_by_id(self, type_id: str) -> Optional[ExperimentTypeInfo]:
        """根据ID获取实验类型"""
        all_types = self.get_all_types()
        return all_types.get(type_id)
    
    def get_type_by_name(self, name: str) -> Optional[ExperimentTypeInfo]:
        """根据名称获取实验类型"""
        for type_info in self.get_all_types().values():
            if type_info.name == name:
                return type_info
        return None
    
    def is_standard_type(self, type_id: str) -> bool:
        """判断是否为标准实验类型"""
        return type_id in self._standard_types
    
    def is_custom_type(self, type_id: str) -> bool:
        """判断是否为自定义实验类型"""
        return type_id in self._custom_types
    
    def get_type_category(self, type_id: str) -> Optional[ExperimentTypeCategory]:
        """获取实验类型分类"""
        type_info = self.get_type_by_id(type_id)
        return type_info.category if type_info else None
    
    def get_experiment_type_for_mode_id(self, mode_id: str) -> Optional[str]:
        """
        根据模式ID获取对应的实验类型
        用于向后兼容，将模式ID映射到实验类型
        """
        if not mode_id:
            return None
        
        # 标准模式映射
        standard_mapping = {
            "GB_13241_2017": "GB_13241_2017",
            "GB_13242_2017": "GB_13242_2017", 
            "GB_13240_2018": "GB_13240_2018"
        }
        
        if mode_id in standard_mapping:
            return standard_mapping[mode_id]
        
        # 自定义模式直接返回
        if self.is_custom_type(mode_id):
            return mode_id
        
        return None
    
    def get_mode_id_for_experiment_type(self, experiment_type: str) -> Optional[str]:
        """
        根据实验类型获取对应的模式ID
        用于向后兼容
        """
        if not experiment_type:
            return None
        
        # 标准类型映射
        if experiment_type in self._standard_types:
            return experiment_type
        
        # 自定义类型映射
        if experiment_type in self._custom_types:
            return experiment_type
        
        return None
    
    def add_custom_type(self, type_info: ExperimentTypeInfo) -> bool:
        """添加自定义实验类型"""
        try:
            self._custom_types[type_info.type_id] = type_info
            self._save_custom_types()
            return True
        except Exception as e:
            self.logger.error(f"添加自定义实验类型失败: {str(e)}")
            return False
    
    def remove_custom_type(self, type_id: str) -> bool:
        """删除自定义实验类型"""
        try:
            if type_id in self._custom_types:
                del self._custom_types[type_id]
                self._save_custom_types()
                return True
            return False
        except Exception as e:
            self.logger.error(f"删除自定义实验类型失败: {str(e)}")
            return False
    
    def update_custom_type(self, type_id: str, type_info: ExperimentTypeInfo) -> bool:
        """更新自定义实验类型"""
        try:
            if type_id in self._custom_types:
                self._custom_types[type_id] = type_info
                self._save_custom_types()
                return True
            return False
        except Exception as e:
            self.logger.error(f"更新自定义实验类型失败: {str(e)}")
            return False
    
    def _save_custom_types(self):
        """保存自定义实验类型到配置文件"""
        try:
            config_path = PathManager.get_config_path("experiment_modes.json")
            
            # 读取现有配置
            config = {}
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            
            # 确保结构存在
            if "experiment_modes" not in config:
                config["experiment_modes"] = {}
            if "custom_modes" not in config["experiment_modes"]:
                config["experiment_modes"]["custom_modes"] = {}
            
            # 更新自定义模式
            custom_modes = {}
            for type_id, type_info in self._custom_types.items():
                custom_modes[type_id] = type_info.to_dict()
            
            config["experiment_modes"]["custom_modes"] = custom_modes
            
            # 保存配置
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            self.logger.error(f"保存自定义实验类型失败: {str(e)}")
    
    def get_type_display_list(self) -> List[tuple]:
        """
        获取用于UI显示的类型列表
        返回格式: [(display_name, type_id), ...]
        """
        display_list = []
        
        # 添加标准类型
        for type_info in self._standard_types.values():
            if type_info.enabled:
                display_list.append((type_info.name, type_info.type_id))
        
        # 添加自定义类型
        for type_info in self._custom_types.values():
            if type_info.enabled:
                display_list.append((type_info.name, type_info.type_id))
        
        return display_list
    
    def validate_type_id(self, type_id: str) -> bool:
        """验证类型ID是否有效"""
        return type_id in self.get_all_types()
    
    def get_type_stages(self, type_id: str) -> List[Dict[str, Any]]:
        """获取实验类型的阶段信息"""
        type_info = self.get_type_by_id(type_id)
        if not type_info:
            return []
        
        # 标准类型从实验模式管理器获取
        if self.is_standard_type(type_id):
            try:
                # 这里需要根据type_id获取对应的ExperimentType枚举
                from src.services.experiment_modes import ExperimentType
                exp_type_mapping = {
                    "GB_13241_2017": ExperimentType.REDUCIBILITY,
                    "GB_13242_2017": ExperimentType.LOW_TEMP_DEGRADATION,
                    "GB_13240_2018": ExperimentType.FREE_SWELLING
                }
                
                if type_id in exp_type_mapping:
                    exp_type = exp_type_mapping[type_id]
                    # ExperimentModeManager exposes get_experiment_stages (not
                    # get_experiment_program); convert StageSettings -> dict so the
                    # return shape matches the custom-type branch below.
                    stages = self.experiment_mode_manager.get_experiment_stages(exp_type)
                    return [self._stage_settings_to_dict(s) for s in stages]
            except Exception as e:
                self.logger.error(f"获取标准类型阶段信息失败: {str(e)}")
                return []
        
        # 自定义类型从extra_data获取
        return type_info.extra_data.get("stages", [])

    @staticmethod
    def _stage_settings_to_dict(stage: Any) -> Dict[str, Any]:
        """Convert a StageSettings object into the dict form used by get_type_stages."""
        gas = getattr(stage, "gas_settings", None)
        stage_enum = getattr(stage, "stage", None)
        return {
            "stage_name": getattr(stage_enum, "value", stage_enum),
            "description": getattr(stage, "description", ""),
            "target_temp": getattr(stage, "target_temp", None),
            "temp_tolerance": getattr(stage, "temp_tolerance", None),
            "duration": getattr(stage, "duration", None),
            "heating_rate": getattr(stage, "heating_rate", None),
            "gas_settings": {
                "CO": getattr(gas, "CO", None),
                "CO2": getattr(gas, "CO2", None),
                "N2": getattr(gas, "N2", None),
                "H2": getattr(gas, "H2", None),
                "total_flow": getattr(gas, "total_flow", None),
            } if gas is not None else {},
        }
