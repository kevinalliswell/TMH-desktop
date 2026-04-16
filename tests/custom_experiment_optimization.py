#!/usr/bin/env python3
"""
自定义实验阶段配置优化方案
解决自定义实验参数未生效的问题
"""

import json
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

from src.services.experiment_modes import ExperimentModeManager, ExperimentType, ExperimentStage, GasSettings, StageSettings
from src.services.experiment_type_manager import ExperimentTypeManager
from src.utils.path_manager import PathManager


class CustomExperimentType(Enum):
    """自定义实验类型枚举"""
    CUSTOM = "CUSTOM"


@dataclass
class CustomExperimentProgram:
    """自定义实验程序"""
    type_id: str
    name: str
    description: str
    stages: List[StageSettings]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "type_id": self.type_id,
            "name": self.name,
            "description": self.description,
            "stages": [
                {
                    "stage_name": stage.stage.value,
                    "description": stage.description,
                    "target_temp": stage.target_temp,
                    "temp_tolerance": stage.temp_tolerance,
                    "duration": stage.duration,
                    "heating_rate": stage.heating_rate,
                    "gas_settings": {
                        "CO": stage.gas_settings.CO,
                        "CO2": stage.gas_settings.CO2,
                        "N2": stage.gas_settings.N2,
                        "H2": stage.gas_settings.H2,
                        "total_flow": stage.gas_settings.total_flow
                    }
                }
                for stage in self.stages
            ]
        }


class EnhancedExperimentModeManager(ExperimentModeManager):
    """增强的实验模式管理器，支持自定义实验"""
    
    def __init__(self):
        super().__init__()
        self._custom_programs: Dict[str, CustomExperimentProgram] = {}
        self._current_custom_type: Optional[str] = None
        self._load_custom_programs()
    
    def _load_custom_programs(self):
        """加载自定义实验程序"""
        try:
            config_path = PathManager.get_config_path("experiment_modes.json")
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                custom_modes = config.get("experiment_modes", {}).get("custom_modes", {})
                for mode_id, mode_data in custom_modes.items():
                    if mode_data.get("enabled", True):
                        stages = self._parse_custom_stages(mode_data.get("stages", []))
                        program = CustomExperimentProgram(
                            type_id=mode_id,
                            name=mode_data.get("name", mode_id),
                            description=mode_data.get("description", ""),
                            stages=stages
                        )
                        self._custom_programs[mode_id] = program
                        
        except Exception as e:
            self.logger.error(f"加载自定义实验程序失败: {str(e)}")
    
    def _parse_custom_stages(self, stages_data: List[Dict]) -> List[StageSettings]:
        """解析自定义阶段数据"""
        stages = []
        
        # 阶段名称映射
        stage_name_mapping = {
            "IDLE": ExperimentStage.IDLE,
            "HEATING": ExperimentStage.HEATING,
            "STABILIZING": ExperimentStage.STABILIZING,
            "REDUCING": ExperimentStage.REDUCING,
            "COOLING": ExperimentStage.COOLING,
            "COMPLETED": ExperimentStage.COMPLETED
        }
        
        for stage_data in stages_data:
            try:
                # 解析气体设置
                gas_data = stage_data.get("gas_settings", {})
                gas_settings = GasSettings(
                    CO=gas_data.get("CO", 0.0),
                    CO2=gas_data.get("CO2", 0.0),
                    N2=gas_data.get("N2", 0.0),
                    H2=gas_data.get("H2", 0.0),
                    total_flow=gas_data.get("total_flow", 0.0)
                )
                
                # 解析阶段名称
                stage_name = stage_data.get("stage_name", "IDLE")
                experiment_stage = stage_name_mapping.get(stage_name, ExperimentStage.IDLE)
                
                # 解析阶段设置
                stage_settings = StageSettings(
                    stage=experiment_stage,
                    gas_settings=gas_settings,
                    target_temp=stage_data.get("target_temp", 25.0),
                    temp_tolerance=stage_data.get("temp_tolerance", 5.0),
                    duration=stage_data.get("duration", 0.0),
                    heating_rate=stage_data.get("heating_rate", 0.0),
                    description=stage_data.get("description", "")
                )
                stages.append(stage_settings)
                
            except Exception as e:
                self.logger.error(f"解析阶段数据失败: {str(e)}")
                continue
        
        return stages
    
    def set_custom_experiment_mode(self, custom_type_id: str) -> bool:
        """设置自定义实验模式"""
        if custom_type_id not in self._custom_programs:
            self.logger.error(f"未找到自定义实验类型: {custom_type_id}")
            return False
        
        self._current_custom_type = custom_type_id
        self.current_experiment = None  # 清空标准实验
        self.current_stage = ExperimentStage.IDLE
        self.current_stage_index = 0
        self.stage_start_time = 0
        
        self.logger.info(f"设置自定义实验模式: {custom_type_id}")
        return True
    
    def get_current_stage_settings(self) -> Optional[StageSettings]:
        """获取当前阶段设置（支持自定义实验）"""
        if self._current_custom_type:
            # 自定义实验模式
            if self._current_custom_type in self._custom_programs:
                stages = self._custom_programs[self._current_custom_type].stages
                if 0 <= self.current_stage_index < len(stages):
                    return stages[self.current_stage_index]
        else:
            # 标准实验模式
            if not self.current_experiment:
                return None
                
            stages = self._experiment_programs[self.current_experiment]
            if 0 <= self.current_stage_index < len(stages):
                return stages[self.current_stage_index]
        
        return None
    
    def advance_to_next_stage(self) -> Optional[StageSettings]:
        """前进到下一阶段（支持自定义实验）"""
        if self._current_custom_type:
            # 自定义实验模式
            if self._current_custom_type in self._custom_programs:
                stages = self._custom_programs[self._current_custom_type].stages
                self.current_stage_index += 1
                
                if self.current_stage_index >= len(stages):
                    self.current_stage = ExperimentStage.COMPLETED
                    return None
                
                current_settings = stages[self.current_stage_index]
                self.current_stage = current_settings.stage
                self.stage_start_time = 0
                
                self.logger.info(f"进入自定义阶段: {current_settings.description}")
                return current_settings
        else:
            # 标准实验模式
            if not self.current_experiment:
                return None
                
            stages = self._experiment_programs[self.current_experiment]
            self.current_stage_index += 1
            
            if self.current_stage_index >= len(stages):
                self.current_stage = ExperimentStage.COMPLETED
                return None
            
            current_settings = stages[self.current_stage_index]
            self.current_stage = current_settings.stage
            self.stage_start_time = 0
            
            self.logger.info(f"进入阶段: {current_settings.description}")
            return current_settings
        
        return None
    
    def get_experiment_stages(self, experiment_type: ExperimentType = None) -> List[StageSettings]:
        """获取实验阶段（支持自定义实验）"""
        if self._current_custom_type:
            # 自定义实验模式
            if self._current_custom_type in self._custom_programs:
                return self._custom_programs[self._current_custom_type].stages
        else:
            # 标准实验模式
            if experiment_type:
                return self._experiment_programs.get(experiment_type, [])
            elif self.current_experiment:
                return self._experiment_programs.get(self.current_experiment, [])
        
        return []
    
    def is_custom_mode(self) -> bool:
        """检查是否为自定义模式"""
        return self._current_custom_type is not None
    
    def get_current_custom_type(self) -> Optional[str]:
        """获取当前自定义类型"""
        return self._current_custom_type
    
    def reload_custom_programs(self):
        """重新加载自定义实验程序"""
        self._custom_programs.clear()
        self._load_custom_programs()


class EnhancedExperimentController:
    """增强的实验控制器，支持自定义实验配置"""
    
    def __init__(self, device_manager=None, parent=None):
        self.device_manager = device_manager
        self.parent = parent
        self.logger = logging.getLogger(__name__)
        
        # 使用增强的实验模式管理器
        self.experiment_mode_manager = EnhancedExperimentModeManager()
        self.experiment_type_manager = ExperimentTypeManager()
        
        # 其他属性...
        self.current_experiment_type = None
        self.current_experiment_type_name = None
        self.experiment_running = False
    
    def set_experiment_mode_by_id(self, mode_id: str) -> bool:
        """
        根据模式ID设置实验模式（支持自定义模式）
        
        Args:
            mode_id: 模式ID
            
        Returns:
            bool: 设置是否成功
        """
        try:
            # 获取类型信息
            type_info = self.experiment_type_manager.get_type_by_id(mode_id)
            if not type_info:
                self.logger.error(f"未找到实验类型: {mode_id}")
                return False
            
            # 标准模式使用原有的设置方法
            if self.experiment_type_manager.is_standard_type(mode_id):
                from src.services.experiment_modes import ExperimentType
                
                mode_mapping = {
                    "GB_13241_2017": ExperimentType.REDUCIBILITY,
                    "GB_13242_2017": ExperimentType.LOW_TEMP_DEGRADATION,
                    "GB_13240_2018": ExperimentType.FREE_SWELLING
                }
                
                if mode_id in mode_mapping:
                    success = self.experiment_mode_manager.set_experiment_mode(mode_mapping[mode_id])
                    if success:
                        self.current_experiment_type = mode_mapping[mode_id]
                        self.current_experiment_type_name = type_info.name
                        self.logger.info(f"设置标准实验模式: {type_info.name}")
                    return success
                else:
                    self.logger.error(f"标准模式ID映射失败: {mode_id}")
                    return False
            
            # 自定义模式使用新的设置方法
            elif self.experiment_type_manager.is_custom_type(mode_id):
                success = self.experiment_mode_manager.set_custom_experiment_mode(mode_id)
                if success:
                    self.current_experiment_type = None  # 自定义模式不使用标准枚举
                    self.current_experiment_type_name = type_info.name
                    self.logger.info(f"设置自定义实验模式: {type_info.name}")
                return success
            
            else:
                self.logger.error(f"未知的实验类型: {mode_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"设置实验模式失败: {str(e)}")
            return False
    
    def get_current_stage_settings(self) -> Optional[StageSettings]:
        """获取当前阶段设置"""
        return self.experiment_mode_manager.get_current_stage_settings()
    
    def get_experiment_stages(self) -> List[StageSettings]:
        """获取实验阶段"""
        return self.experiment_mode_manager.get_experiment_stages()
    
    def is_custom_mode(self) -> bool:
        """检查是否为自定义模式"""
        return self.experiment_mode_manager.is_custom_mode()
    
    def get_current_custom_type(self) -> Optional[str]:
        """获取当前自定义类型"""
        return self.experiment_mode_manager.get_current_custom_type()


def test_custom_experiment_optimization():
    """测试自定义实验优化"""
    print("=" * 60)
    print("测试自定义实验优化")
    print("=" * 60)
    
    # 创建增强的实验控制器
    controller = EnhancedExperimentController()
    
    # 测试自定义实验设置
    custom_mode_id = "CUSTOM_HIGH_TEMP_TEST"
    print(f"\n设置自定义实验模式: {custom_mode_id}")
    
    success = controller.set_experiment_mode_by_id(custom_mode_id)
    print(f"设置结果: {'成功' if success else '失败'}")
    
    if success:
        print(f"当前模式: {controller.current_experiment_type_name}")
        print(f"是否为自定义模式: {controller.is_custom_mode()}")
        print(f"自定义类型ID: {controller.get_current_custom_type()}")
        
        # 获取阶段信息
        stages = controller.get_experiment_stages()
        print(f"\n实验阶段数量: {len(stages)}")
        
        for i, stage in enumerate(stages):
            print(f"阶段 {i+1}: {stage.stage.value}")
            print(f"  描述: {stage.description}")
            print(f"  目标温度: {stage.target_temp}°C")
            print(f"  持续时间: {stage.duration} 分钟")
            print(f"  气体设置: {stage.gas_settings}")
            print()
        
        # 测试阶段执行
        print("测试阶段执行...")
        controller.experiment_mode_manager.current_stage_index = 0
        current_stage = controller.get_current_stage_settings()
        
        if current_stage:
            print(f"当前阶段: {current_stage.stage.value}")
            print(f"阶段描述: {current_stage.description}")
            print(f"目标温度: {current_stage.target_temp}°C")
            print(f"气体设置: {current_stage.gas_settings}")
        else:
            print("无法获取当前阶段设置")


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    test_custom_experiment_optimization()
