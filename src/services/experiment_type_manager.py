# src/services/experiment_type_manager.py
"""
实验类型管理器
统一管理标准实验类型和自定义实验类型，解决枚举与动态配置的冲突问题
"""

from enum import Enum
from typing import Dict, List, Optional, Any, Union
import logging

from src.services.experiment_modes import ExperimentModeManager
from src.services.standard_modes import STANDARD_MODES


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

    def __init__(self, mode_manager: Optional[ExperimentModeManager] = None):
        self.logger = logging.getLogger(__name__)
        self.experiment_mode_manager = mode_manager or ExperimentModeManager()
        
        # 标准实验类型定义
        self._standard_types = self._initialize_standard_types()
        
        # 自定义实验类型
        self._custom_types = {}
        
        # 加载自定义类型
        self._load_custom_types()
    
    def _initialize_standard_types(self) -> Dict[str, ExperimentTypeInfo]:
        """初始化标准实验类型"""
        return {
            mode_id: ExperimentTypeInfo(
                type_id=mode_id,
                name=definition.name,
                description=definition.description,
                category=ExperimentTypeCategory.STANDARD,
                enabled=True
            )
            for mode_id, definition in STANDARD_MODES.items()
        }
    
    def _load_custom_types(self):
        """从共享模式管理器加载自定义实验类型。"""
        try:
            self._custom_types.clear()
            custom_modes = self.experiment_mode_manager.get_custom_modes()
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

    def reload_custom_types(self) -> None:
        """Refresh the type index from the shared mode manager."""
        self._load_custom_types()
    
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
    
    def add_custom_type(self, type_info: ExperimentTypeInfo) -> bool:
        """添加自定义实验类型"""
        try:
            result = self.experiment_mode_manager.add_custom_mode(
                type_info.type_id,
                type_info.to_dict(),
            )
            if result:
                self.reload_custom_types()
            return result
        except Exception as e:
            self.logger.error(f"添加自定义实验类型失败: {str(e)}")
            return False
    
    def remove_custom_type(self, type_id: str) -> bool:
        """删除自定义实验类型"""
        try:
            result = self.experiment_mode_manager.delete_custom_mode(type_id)
            if result:
                self.reload_custom_types()
            return result
        except Exception as e:
            self.logger.error(f"删除自定义实验类型失败: {str(e)}")
            return False
    
    def update_custom_type(self, type_id: str, type_info: ExperimentTypeInfo) -> bool:
        """更新自定义实验类型"""
        try:
            result = self.experiment_mode_manager.update_custom_mode(
                type_id,
                type_info.to_dict(),
            )
            if result:
                self.reload_custom_types()
            return result
        except Exception as e:
            self.logger.error(f"更新自定义实验类型失败: {str(e)}")
            return False
    
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
                definition = STANDARD_MODES[type_id]
                stages = self.experiment_mode_manager.get_experiment_stages(
                    definition.experiment_type
                )
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
            "stage_name": getattr(stage_enum, "name", stage_enum),
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
