# src/services/gb13241_calculator.py
from typing import List, Dict, Optional
import numpy as np
import logging
from datetime import datetime

class ReductionCalculator:
    """GB/T 13241-2017 还原性计算器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def calculate_reduction_degree(self, initial_weight: float, current_weight: float,
                                 oxygen_content: float) -> Optional[float]:
        """
        计算还原度
        
        Args:
            initial_weight: 初始重量 (g)
            current_weight: 当前重量 (g)
            oxygen_content: 氧含量 (%)
            
        Returns:
            float: 还原度 (%)，计算失败返回None
            
        公式：Rt = (ΔW / (W0 * O2%)) * 100%
        其中：
        - Rt: t时刻的还原度
        - ΔW: 失重量
        - W0: 初始重量
        - O2%: 氧含量百分比
        """
        try:
            if initial_weight <= 0 or oxygen_content <= 0:
                raise ValueError("初始重量和氧含量必须大于0")
                
            weight_loss = initial_weight - current_weight
            # oxygen_content is expressed as a percentage (e.g. 28.5 for 28.5%),
            # so convert it to a fraction before computing the removable-oxygen mass.
            # Rt = ΔW / (W0 * O2fraction) * 100%
            oxygen_fraction = oxygen_content / 100.0
            reduction_degree = (weight_loss / (initial_weight * oxygen_fraction)) * 100
            return round(reduction_degree, 2)
            
        except Exception as e:
            self.logger.error(f"计算还原度失败: {str(e)}")
            return None
            
    def calculate_reduction_index(self, reduction_degrees: List[float],
                                times: List[float]) -> Optional[float]:
        """
        计算还原速率指数
        
        Args:
            reduction_degrees: 还原度列表 (%)
            times: 对应的时间点列表 (min)
            
        Returns:
            float: 还原速率指数，计算失败返回None
        """
        try:
            if len(reduction_degrees) != len(times):
                raise ValueError("还原度和时间列表长度不匹配")
                
            # 使用线性回归计算斜率
            coefficients = np.polyfit(times, reduction_degrees, 1)
            reduction_index = coefficients[0]  # 斜率即为还原速率指数
            
            return round(reduction_index, 3)
            
        except Exception as e:
            self.logger.error(f"计算还原速率指数失败: {str(e)}")
            return None
            
    def analyze_experiment_data(self, data: List[Dict], oxygen_content: float) -> Dict:
        """
        分析实验数据，生成结果报告
        
        Args:
            data: 实验数据列表
            oxygen_content: 样品氧含量 (%)
            
        Returns:
            Dict: 分析结果字典
        """
        try:
            # 提取重量和时间数据
            weights = [d['weight'] for d in data]
            timestamps = [d['timestamp'] for d in data]
            
            # 计算时间序列（分钟）
            start_time = timestamps[0]
            times = [(t - start_time).total_seconds() / 60 for t in timestamps]
            
            # 计算还原度序列
            initial_weight = weights[0]
            reduction_degrees = [
                self.calculate_reduction_degree(initial_weight, w, oxygen_content)
                for w in weights
            ]
            
            # 计算还原速率指数
            reduction_index = self.calculate_reduction_index(reduction_degrees, times)
            
            # 计算最终还原度
            final_reduction_degree = reduction_degrees[-1]
            
            return {
                'initial_weight': round(initial_weight, 3),
                'final_weight': round(weights[-1], 3),
                'total_weight_loss': round(initial_weight - weights[-1], 3),
                'final_reduction_degree': final_reduction_degree,
                'reduction_index': reduction_index,
                'experiment_duration': times[-1],
                'data_points': len(data)
            }
            
        except Exception as e:
            self.logger.error(f"分析实验数据失败: {str(e)}")
            return {}
            
    def validate_experiment_conditions(self, data: List[Dict]) -> List[str]:
        """
        验证实验条件是否符合标准要求
        
        Args:
            data: 实验数据列表
            
        Returns:
            List[str]: 问题列表，如果为空则表示符合要求
        """
        problems = []
        
        try:
            temperatures = [d['temperature'] for d in data]
            gas_flows = [d['gas_flow'] for d in data]
            timestamps = [d['timestamp'] for d in data]
            
            # 检查温度是否维持在900℃
            temp_mean = np.mean(temperatures)
            temp_std = np.std(temperatures)
            if abs(temp_mean - 900) > 10 or temp_std > 5:
                problems.append("温度控制不稳定，应维持在900±10℃")
                
            # 检查气体流量
            if not all(14.5 <= flow <= 15.5 for flow in gas_flows):
                problems.append("气体流量超出范围，应维持在15±0.5L/min")
                
            # 检查实验时长
            duration = (timestamps[-1] - timestamps[0]).total_seconds() / 60
            if duration < 180:  # 至少3小时
                problems.append("实验时间不足3小时")
                
        except Exception as e:
            self.logger.error(f"验证实验条件失败: {str(e)}")
            problems.append(f"数据验证过程出错: {str(e)}")
            
        return problems 