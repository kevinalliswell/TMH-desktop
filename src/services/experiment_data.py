# src/services/experiment_data.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Any

@dataclass
class BaseExperimentData:
    """所有实验数据类的基类，包含通用字段"""
    experiment_id: str
    experiment_name: str
    sample_name: str
    start_time: datetime
    operator: str
    description: Optional[str] = None
    end_time: Optional[datetime] = None
    # 存储原始的、按时间序列记录的各类传感器数据点
    # 每个数据点可以是一个字典，例如:
    # {'timestamp': datetime, 'temperature': 900.5, 'weight': 495.2, 'CO_flow': 2.5, ...}
    raw_data_log: List[Dict[str, Any]] = field(default_factory=list)
    # 存储根据国标或实验特定需求计算和分析得出的最终结果
    calculated_results: Dict[str, Any] = field(default_factory=dict)
    # 实验过程中捕获的任何备注、异常或观察记录
    remarks: List[str] = field(default_factory=list)


@dataclass
class ReductionExperimentData(BaseExperimentData):
    """
    铁矿石还原性实验 (GB/T 13241-2017) 数据模型
    """
    # 实验特定输入参数
    # NOTE: dataclass inheritance requires these to carry defaults because the
    # base class (BaseExperimentData) already declares fields with defaults.
    initial_sample_weight_g: float = 0.0 # 样品初始重量 (克)
    total_iron_content_percentage: float = 0.0 # 全铁含量 w(TFe) (%)
    feo_content_percentage: float = 0.0 # 氧化亚铁含量 w(FeO) (%)
    oxygen_content_percentage: float = 0.0 # 旧实验文件兼容字段，不再用于 GB/T 13241 计算

    # 实验过程中记录的关键数据序列 (可选，也可以从raw_data_log中提取)
    timestamps: List[datetime] = field(default_factory=list)
    weights_g: List[float] = field(default_factory=list) # 各时间点的样品重量 (克)
    temperatures_celsius: List[float] = field(default_factory=list) # 各时间点的炉温 (摄氏度)
    gas_flows_l_min: Dict[str, List[float]] = field(default_factory=dict) # 各气体流量 (升/分钟), e.g., {'CO': [], 'CO2': [], 'N2': []}

    # calculated_results 字典中可能包含:
    # 'final_reduction_degree_percent': float, 最终还原度 (%)
    # 'reduction_index_ri_percent': float, RI 指数 (通常是 R60) (%)
    # 'reduction_rate_dr_dt_percent_min': float, dR/dt (%/分钟)
    # 'reduction_degree_at_30min_percent': float
    # 'reduction_degree_at_60min_percent': float
    # 'reduction_degree_at_90min_percent': float
    # 'time_to_40_percent_reduction_min': float, (t40)
    # 'time_to_70_percent_reduction_min': float, (t70)
    # 'total_weight_loss_g': float
    # ... 其他分析结果


@dataclass
class RDIExperimentData(BaseExperimentData):
    """
    铁矿石低温还原粉化实验 (GB/T 13242-2017) 数据模型
    RDI: Reduction Degradation Index
    """
    # 实验特定输入参数
    initial_sample_mass_g: float = 0.0 # 还原前试样总质量 (克)

    # 实验结束后测量的各粒级筛分质量
    sieve_data_g: Dict[str, float] = field(default_factory=dict)
    # Key 为粒级描述, 例如:
    # ">6.3mm": float, (g)
    # "3.15mm-6.3mm": float, (g)
    # "0.5mm-3.15mm": float, (g)
    # "<0.5mm": float, (g)

    # calculated_results 字典中可能包含:
    # 'RDI_plus_6_3_mm_percent': float, (%)
    # 'RDI_plus_3_15_mm_percent': float, (%)
    # 'RDI_minus_0_5_mm_percent': float, (%)
    # 'total_mass_after_sieving_g': float, # 筛后总质量，用于校验

@dataclass
class PelletData:
    """单个球团的数据"""
    pellet_id: int
    initial_diameter_mm: Optional[float] = None
    final_diameter_mm: Optional[float] = None
    initial_volume_cm3: Optional[float] = None # 国标中提及用排水法测体积，单位mL(cm³)
    final_volume_cm3: Optional[float] = None   # 国标中提及用排水法测体积，单位mL(cm³)
    swelling_index_percent: Optional[float] = None
    # 还原后形态描述
    appearance_after_reduction: Optional[str] = None
    cracks_description: Optional[str] = None
    strength_evaluation: Optional[str] = None


@dataclass
class SwellingExperimentData(BaseExperimentData):
    """
    球团矿自由膨胀指数实验 (GB/T 13240-2017) 数据模型
    SI: Swelling Index
    """
    # 实验特定输入参数
    number_of_pellets_tested: int = 0

    # 每个球团的详细数据
    pellets_data: List[PelletData] = field(default_factory=list)

    # calculated_results 字典中可能包含:
    # 'average_swelling_index_percent': float, 平均体积膨胀指数 (%)
    # 'swelling_indices_all_pellets': List[float], 每个球团的膨胀指数列表
    # 'average_initial_diameter_mm': float
    # 'average_final_diameter_mm': float
    # 'average_initial_volume_cm3': float
    # 'average_final_volume_cm3': float
