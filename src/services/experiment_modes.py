# src/services/experiment_modes.py
"""
实验模式管理器
根据GB国标定义的三种实验模式，提供气体控制程序的自动切换功能
支持从JSON文件加载和保存自定义实验模式
"""

from enum import Enum
from typing import Dict, List, Optional, NamedTuple, Any
import logging
import json
import os
from datetime import datetime

from src.services.standard_modes import STANDARD_MODES, ExperimentType


class ExperimentStage(Enum):
    """实验阶段枚举"""
    IDLE = "待机"
    HEATING = "升温"
    STABILIZING = "恒温"
    REDUCING = "还原"
    COOLING = "冷却"
    COMPLETED = "完成"


class GasSettings(NamedTuple):
    """气体设置"""
    CO: float = 0.0      # CO流量 (L/min)
    CO2: float = 0.0     # CO2流量 (L/min)
    N2: float = 0.0      # N2流量 (L/min)
    H2: float = 0.0      # H2流量 (L/min)
    total_flow: float = 0.0  # 总流量 (L/min)
    
    @property
    def co_percentage(self) -> float:
        """CO百分比"""
        return (self.CO / self.total_flow * 100) if self.total_flow > 0 else 0
    
    @property
    def co2_percentage(self) -> float:
        """CO2百分比"""
        return (self.CO2 / self.total_flow * 100) if self.total_flow > 0 else 0
    
    @property
    def n2_percentage(self) -> float:
        """N2百分比"""
        return (self.N2 / self.total_flow * 100) if self.total_flow > 0 else 0


class StageSettings(NamedTuple):
    """阶段设置"""
    stage: ExperimentStage
    gas_settings: GasSettings
    target_temp: float  # 目标温度 (℃)
    temp_tolerance: float  # 温度误差范围 (℃)
    duration: float  # 持续时间 (min)
    heating_rate: float  # 升温速率 (℃/min)
    description: str  # 阶段描述


class ExperimentModeManager:
    """实验模式管理器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # 定义三种实验模式的气体控制程序
        self._experiment_programs = self._initialize_experiment_programs()
        
        # 自定义实验模式
        self._custom_modes = {}
        
        # 当前实验状态
        self.current_experiment: Optional[ExperimentType] = None
        self.current_stage: ExperimentStage = ExperimentStage.IDLE
        self.current_stage_index: int = 0
        self.stage_start_time: float = 0
        
        # 加载自定义模式
        self._load_custom_modes()
        
    def _initialize_experiment_programs(self) -> Dict[ExperimentType, List[StageSettings]]:
        """初始化实验程序定义"""
        programs = {}
        
        # 1. GB/T 13241-2017 铁矿石还原性测定
        programs[ExperimentType.REDUCIBILITY] = [
            StageSettings(
                stage=ExperimentStage.HEATING,
                gas_settings=GasSettings(N2=5.0, total_flow=5.0),
                target_temp=900.0,
                temp_tolerance=5.0,
                duration=0,  # 动态时间，基于升温速率
                heating_rate=10.0,
                description="升温至900℃，N₂保护"
            ),
            StageSettings(
                stage=ExperimentStage.STABILIZING,
                gas_settings=GasSettings(N2=15.0, total_flow=15.0),
                target_temp=900.0,
                temp_tolerance=5.0,
                duration=30.0,
                heating_rate=0.0,
                description="900℃恒温30min，N₂气氛"
            ),
            StageSettings(
                stage=ExperimentStage.REDUCING,
                gas_settings=GasSettings(CO=4.5, N2=10.5, total_flow=15.0),
                target_temp=900.0,
                temp_tolerance=5.0,
                duration=180.0,
                heating_rate=0.0,
                description="还原180min，30%CO+70%N₂"
            ),
            StageSettings(
                stage=ExperimentStage.COOLING,
                gas_settings=GasSettings(N2=5.0, total_flow=5.0),
                target_temp=25.0,
                temp_tolerance=5.0,
                duration=0,  # 动态时间，自然冷却
                heating_rate=-10.0,  # 负值表示冷却
                description="N₂保护冷却至室温"
            )
        ]
        
        # 2. GB/T 13242-2017 低温粉化试验
        programs[ExperimentType.LOW_TEMP_DEGRADATION] = [
            StageSettings(
                stage=ExperimentStage.HEATING,
                gas_settings=GasSettings(N2=5.0, total_flow=5.0),
                target_temp=500.0,
                temp_tolerance=5.0,
                duration=0,
                heating_rate=10.0,
                description="升温至500℃，N₂保护"
            ),
            StageSettings(
                stage=ExperimentStage.STABILIZING,
                gas_settings=GasSettings(N2=15.0, total_flow=15.0),
                target_temp=500.0,
                temp_tolerance=5.0,
                duration=30.0,
                heating_rate=0.0,
                description="500℃恒温30min，N₂气氛"
            ),
            StageSettings(
                stage=ExperimentStage.REDUCING,
                gas_settings=GasSettings(CO=3.0, CO2=3.0, N2=9.0, total_flow=15.0),
                target_temp=500.0,
                temp_tolerance=5.0,
                duration=60.0,
                heating_rate=0.0,
                description="还原60min，20%CO+20%CO₂+60%N₂"
            ),
            StageSettings(
                stage=ExperimentStage.COOLING,
                gas_settings=GasSettings(N2=5.0, total_flow=5.0),
                target_temp=25.0,
                temp_tolerance=5.0,
                duration=0,
                heating_rate=-10.0,
                description="N₂保护冷却至室温"
            )
        ]
        
        # 3. GB/T 13240-2018 球团矿自由膨胀指数
        programs[ExperimentType.FREE_SWELLING] = [
            StageSettings(
                stage=ExperimentStage.HEATING,
                gas_settings=GasSettings(N2=10.0, total_flow=10.0),
                target_temp=900.0,
                temp_tolerance=5.0,
                duration=0,
                heating_rate=10.0,
                description="升温至900℃，N₂保护"
            ),
            StageSettings(
                stage=ExperimentStage.STABILIZING,
                gas_settings=GasSettings(N2=15.0, total_flow=15.0),
                target_temp=900.0,
                temp_tolerance=5.0,
                duration=15.0,
                heating_rate=0.0,
                description="900℃恒温15min，N₂气氛"
            ),
            StageSettings(
                stage=ExperimentStage.REDUCING,
                gas_settings=GasSettings(CO=4.5, N2=10.5, total_flow=15.0),
                target_temp=900.0,
                temp_tolerance=5.0,
                duration=60.0,
                heating_rate=0.0,
                description="还原60min，30%CO+70%N₂"
            ),
            StageSettings(
                stage=ExperimentStage.COOLING,
                gas_settings=GasSettings(N2=5.0, total_flow=5.0),
                target_temp=50.0,
                temp_tolerance=5.0,
                duration=0,
                heating_rate=-10.0,
                description="N₂保护冷却至50℃"
            )
        ]
        
        return programs
    
    def get_experiment_types(self) -> List[ExperimentType]:
        """获取所有实验类型"""
        return list(self._experiment_programs.keys())
    
    def get_experiment_stages(self, experiment_type: ExperimentType) -> List[StageSettings]:
        """获取指定实验的所有阶段"""
        return self._experiment_programs.get(experiment_type, [])
    
    def set_experiment_mode(self, experiment_type: ExperimentType) -> bool:
        """设置实验模式"""
        if experiment_type not in self._experiment_programs:
            self.logger.error(f"不支持的实验类型: {experiment_type}")
            return False
            
        self.current_experiment = experiment_type
        self.current_stage = ExperimentStage.IDLE
        self.current_stage_index = 0
        self.stage_start_time = 0
        
        self.logger.info(f"设置实验模式: {experiment_type.value}")
        return True
    
    def get_current_stage_settings(self) -> Optional[StageSettings]:
        """获取当前阶段设置"""
        if not self.current_experiment:
            return None
            
        stages = self._experiment_programs[self.current_experiment]
        if 0 <= self.current_stage_index < len(stages):
            return stages[self.current_stage_index]
        return None
    
    def advance_to_next_stage(self) -> Optional[StageSettings]:
        """前进到下一阶段"""
        if not self.current_experiment:
            return None
            
        stages = self._experiment_programs[self.current_experiment]
        self.current_stage_index += 1
        
        if self.current_stage_index >= len(stages):
            self.current_stage = ExperimentStage.COMPLETED
            return None
        
        current_settings = stages[self.current_stage_index]
        self.current_stage = current_settings.stage
        self.stage_start_time = 0  # 将由调用者设置
        
        self.logger.info(f"进入阶段: {current_settings.description}")
        return current_settings
    
    def can_advance_stage(self, current_temp: float, elapsed_time: float) -> bool:
        """检查是否可以进入下一阶段"""
        current_settings = self.get_current_stage_settings()
        if not current_settings:
            return False
        
        # Cooling is complete once the temperature is below the upper limit.
        # A symmetric band would reject temperatures below the target again.
        if current_settings.stage is ExperimentStage.COOLING:
            temp_ok = current_temp <= current_settings.target_temp + current_settings.temp_tolerance
        else:
            temp_ok = abs(current_temp - current_settings.target_temp) <= current_settings.temp_tolerance
        
        # 检查时间条件
        time_ok = True
        if current_settings.duration > 0:  # 固定时间阶段
            time_ok = elapsed_time >= current_settings.duration * 60  # 转换为秒
        
        return temp_ok and time_ok
    
    def get_gas_flow_for_mfc(self, gas_settings: GasSettings) -> Dict[str, float]:
        """转换气体设置为质量流量控制器格式"""

        return {
            'CO': gas_settings.CO,
            'CO2': gas_settings.CO2,
            'N2': gas_settings.N2,
            'H2': gas_settings.H2
        }
    
    def get_experiment_summary(self, experiment_type: ExperimentType) -> str:
        """获取实验摘要信息"""
        stages = self.get_experiment_stages(experiment_type)
        total_time = sum(stage.duration for stage in stages if stage.duration > 0)
        
        summary = f"实验: {experiment_type.value}\n"
        summary += f"总阶段数: {len(stages)}\n"
        summary += f"预计时间: {total_time:.0f} 分钟\n\n"
        
        for i, stage in enumerate(stages, 1):
            summary += f"阶段{i}: {stage.description}\n"
            summary += f"  温度: {stage.target_temp}±{stage.temp_tolerance}℃\n"
            summary += f"  气体: {stage.gas_settings.co_percentage:.1f}%CO "
            summary += f"{stage.gas_settings.co2_percentage:.1f}%CO₂ "
            summary += f"{stage.gas_settings.n2_percentage:.1f}%N₂\n"
            if stage.duration > 0:
                summary += f"  时间: {stage.duration:.0f}分钟\n"
            summary += "\n"
        
        return summary
    
    def _load_custom_modes(self):
        """从JSON文件加载自定义模式"""
        try:
            from src.utils.path_manager import PathManager
            config_path = PathManager.get_config_path("experiment_modes.json")
            
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._custom_modes = data.get('experiment_modes', {}).get('custom_modes', {})
                    self.logger.info(f"加载了 {len(self._custom_modes)} 个自定义实验模式")
            else:
                self.logger.warning("实验模式配置文件不存在")
        except Exception as e:
            self.logger.error(f"加载自定义模式失败: {str(e)}")
    
    def _save_custom_modes(self):
        """保存自定义模式到JSON文件"""
        try:
            from src.utils.path_manager import PathManager
            config_path = PathManager.get_config_path("experiment_modes.json")
            
            # 读取现有配置
            data = {}
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            
            # 更新自定义模式
            if 'experiment_modes' not in data:
                data['experiment_modes'] = {}
            data['experiment_modes']['custom_modes'] = self._custom_modes
            
            # 保存配置
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            self.logger.info("自定义模式已保存")
            return True
        except Exception as e:
            self.logger.error(f"保存自定义模式失败: {str(e)}")
            return False
    
    def get_standard_modes(self) -> Dict[str, Dict[str, Any]]:
        """获取标准实验模式"""
        return {
            mode_id: {
                "name": definition.name,
                "description": definition.description,
                "category": "standard",
                "enabled": True
            }
            for mode_id, definition in STANDARD_MODES.items()
        }
    
    def get_custom_modes(self) -> Dict[str, Dict[str, Any]]:
        """获取自定义实验模式"""
        return self._custom_modes
    
    def get_standard_mode(self, mode_id: str) -> Optional[Dict[str, Any]]:
        """获取标准模式详情"""
        standard_modes = self.get_standard_modes()
        if mode_id in standard_modes:
            mode_data = standard_modes[mode_id].copy()
            definition = STANDARD_MODES[mode_id]
            mode_data['stages'] = self._convert_stages_to_dict(definition.experiment_type)
            return mode_data
        return None
    
    def get_custom_mode(self, mode_id: str) -> Optional[Dict[str, Any]]:
        """获取自定义模式详情"""
        return self._custom_modes.get(mode_id)
    
    def _convert_stages_to_dict(self, experiment_type: ExperimentType) -> List[Dict[str, Any]]:
        """将阶段设置转换为字典格式"""
        stages = self.get_experiment_stages(experiment_type)
        result = []
        
        for stage in stages:
            stage_dict = {
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
            result.append(stage_dict)
        
        return result
    
    def add_custom_mode(self, mode_id: str, mode_data: Dict[str, Any]) -> bool:
        """添加自定义模式"""
        try:
            # 添加创建时间
            mode_data['created_time'] = datetime.now().isoformat()
            mode_data['created_by'] = 'user'
            
            self._custom_modes[mode_id] = mode_data
            return self._save_custom_modes()
        except Exception as e:
            self.logger.error(f"添加自定义模式失败: {str(e)}")
            return False
    
    def update_custom_mode(self, mode_id: str, mode_data: Dict[str, Any]) -> bool:
        """更新自定义模式"""
        try:
            if mode_id not in self._custom_modes:
                return False
            
            # 保留创建信息
            original_data = self._custom_modes[mode_id]
            mode_data['created_time'] = original_data.get('created_time', datetime.now().isoformat())
            mode_data['created_by'] = original_data.get('created_by', 'user')
            mode_data['modified_time'] = datetime.now().isoformat()
            
            self._custom_modes[mode_id] = mode_data
            return self._save_custom_modes()
        except Exception as e:
            self.logger.error(f"更新自定义模式失败: {str(e)}")
            return False
    
    def delete_custom_mode(self, mode_id: str) -> bool:
        """删除自定义模式"""
        try:
            if mode_id not in self._custom_modes:
                return False
            
            del self._custom_modes[mode_id]
            return self._save_custom_modes()
        except Exception as e:
            self.logger.error(f"删除自定义模式失败: {str(e)}")
            return False
