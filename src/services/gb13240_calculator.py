# src/services/gb13240_calculator.py
from typing import List, Dict, Optional
import numpy as np
import logging
from datetime import datetime

class FreeExpansionCalculator:
    """GB/T 13240-2018 自由膨胀指数计算器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def calculate_expansion_index(self, initial_volume: float, final_volume: float) -> Optional[float]:
        """
        计算自由膨胀指数
        
        Args:
            initial_volume: 初始体积 (mL)
            final_volume: 最终体积 (mL)
            
        Returns:
            float: 自由膨胀指数，计算失败返回None
            
        公式：Vfs = (V1 - V0) / V0 * 100%
        其中：
        - Vfs: 自由膨胀指数
        - V0: 初始体积
        - V1: 最终体积
        """
        try:
            if initial_volume <= 0:
                raise ValueError("初始体积必须大于0")
                
            expansion_index = (final_volume - initial_volume) / initial_volume * 100
            return round(expansion_index, 2)
            
        except Exception as e:
            self.logger.error(f"计算自由膨胀指数失败: {str(e)}")
            return None
            
    def analyze_experiment_data(self, data: List[Dict]) -> Dict:
        """
        分析实验数据，生成结果报告
        
        Args:
            data: 实验数据列表，每个数据点包含timestamp和相关测量值
            
        Returns:
            Dict: 分析结果字典
        """
        try:
            # 提取温度数据
            temperatures = [d['temperature'] for d in data]
            timestamps = [d['timestamp'] for d in data]
            
            # 计算关键指标
            max_temp = max(temperatures)
            avg_temp = np.mean(temperatures)
            temp_std = np.std(temperatures)
            
            # 计算升温速率
            temp_diff = np.diff(temperatures)
            time_diff = np.diff([t.timestamp() for t in timestamps])
            heat_rates = temp_diff / time_diff * 60  # 转换为℃/min
            avg_heat_rate = np.mean(heat_rates)
            
            return {
                'max_temperature': round(max_temp, 2),
                'average_temperature': round(avg_temp, 2),
                'temperature_std': round(temp_std, 2),
                'average_heat_rate': round(avg_heat_rate, 2),
                'experiment_duration': (timestamps[-1] - timestamps[0]).total_seconds() / 60,  # 分钟
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

            # GB/T 13240 还原阶段应维持在 900℃。
            temp_mean = np.mean(temperatures)
            temp_std = np.std(temperatures)
            if abs(temp_mean - 900) > 10 or temp_std > 5:
                problems.append("温度控制不稳定，应维持在900±10℃")

            # 还原气总流量为 15 L/min。
            if not all(14.5 <= flow <= 15.5 for flow in gas_flows):
                problems.append("气体流量超出范围，应维持在15±0.5L/min")
                
            # 检查升温速率
            temp_diff = np.diff(temperatures)
            time_diff = np.diff([t.timestamp() for t in timestamps])
            heat_rates = temp_diff / time_diff * 60
            
            if max(heat_rates) > 10:
                problems.append("升温速率超过10℃/min")
                
            # 检查实验时长
            duration = (timestamps[-1] - timestamps[0]).total_seconds() / 60
            if duration < 60:  # 还原阶段至少1小时
                problems.append("实验时间不足1小时")
                
        except Exception as e:
            self.logger.error(f"验证实验条件失败: {str(e)}")
            problems.append(f"数据验证过程出错: {str(e)}")
            
        return problems
