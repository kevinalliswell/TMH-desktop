# src/services/enhanced_experiment_modes.py
"""
增强的实验模式管理器
支持自定义实验的完整配置加载和执行
"""

import json
import os
import copy
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from src.services.experiment_modes import ExperimentModeManager, ExperimentType, ExperimentStage, GasSettings, StageSettings
from src.utils.path_manager import PathManager
from src.utils.logger import get_logger

logger = get_logger(__name__)


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
                    "stage_name": stage.stage.name,
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
        self._active_custom_program: Optional[CustomExperimentProgram] = None
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
            logger.error(f"加载自定义实验程序失败: {str(e)}")
    
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
        stage_name_mapping.update({stage.value: stage for stage in ExperimentStage})
        
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
                logger.error(f"解析阶段数据失败: {str(e)}")
                continue
        
        return stages
    
    def set_experiment_mode(self, experiment_type: ExperimentType) -> bool:
        """设置标准实验模式。

        必须清除 _current_custom_type，否则先选自定义模式、再切回标准模式时，
        get_current_stage_settings / advance_to_next_stage 等仍会走自定义分支，
        导致运行错误的气氛/温度程序。
        """
        success = super().set_experiment_mode(experiment_type)
        if success:
            self._current_custom_type = None
            self._active_custom_program = None
        return success

    def set_custom_experiment_mode(self, custom_type_id: str) -> bool:
        """设置自定义实验模式"""
        if custom_type_id not in self._custom_programs:
            logger.error(f"未找到自定义实验类型: {custom_type_id}")
            return False
        
        self._current_custom_type = custom_type_id
        self._active_custom_program = copy.deepcopy(
            self._custom_programs[custom_type_id]
        )
        self.current_experiment = None  # 清空标准实验
        self.current_stage = ExperimentStage.IDLE
        self.current_stage_index = 0
        self.stage_start_time = 0
        
        logger.info(f"设置自定义实验模式: {custom_type_id}")
        return True
    
    def get_current_stage_settings(self) -> Optional[StageSettings]:
        """获取当前阶段设置（支持自定义实验）"""
        if self._current_custom_type:
            # 自定义实验模式
            if self._active_custom_program is not None:
                stages = self._active_custom_program.stages
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
            if self._active_custom_program is not None:
                stages = self._active_custom_program.stages
                self.current_stage_index += 1
                
                if self.current_stage_index >= len(stages):
                    self.current_stage = ExperimentStage.COMPLETED
                    return None
                
                current_settings = stages[self.current_stage_index]
                self.current_stage = current_settings.stage
                self.stage_start_time = 0
                
                logger.info(f"进入自定义阶段: {current_settings.description}")
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
            
            logger.info(f"进入阶段: {current_settings.description}")
            return current_settings
        
        return None
    
    def get_experiment_stages(self, experiment_type: ExperimentType = None) -> List[StageSettings]:
        """获取实验阶段（支持自定义实验）"""
        if experiment_type is not None:
            return self._experiment_programs.get(experiment_type, [])
        if self._current_custom_type:
            # 自定义实验模式
            if self._active_custom_program is not None:
                return self._active_custom_program.stages
        else:
            # 标准实验模式
            if self.current_experiment:
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
        self._custom_modes.clear()
        self._load_custom_modes()
        self._custom_programs.clear()
        self._load_custom_programs()
    
    def get_custom_program(self, custom_type_id: str) -> Optional[CustomExperimentProgram]:
        """获取自定义实验程序"""
        return self._custom_programs.get(custom_type_id)
    
    def list_custom_programs(self) -> List[str]:
        """列出所有自定义实验程序ID"""
        return list(self._custom_programs.keys())
