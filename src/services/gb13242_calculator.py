# src/services/gb13242_calculator.py
from typing import List, Dict, Optional
import numpy as np
import logging
from datetime import datetime

class LowTempDegradationCalculator:
    """GB/T 13242-2017 低温粉化指数计算器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def calculate_rdi(self, initial_weight: float, sieve_weights: Dict[float, float]) -> Dict[str, float]:
        """
        计算低温粉化指数
        
        Args:
            initial_weight: 初始重量 (g)
            sieve_weights: 各筛分重量字典，键为筛孔尺寸(mm)，值为重量(g)
            
        Returns:
            Dict[str, float]: 各项RDI指标，计算失败返回空字典
            
        指标说明：
        - RDI+6.3: >6.3mm颗粒重量百分比
        - RDI+3.15: >3.15mm颗粒重量百分比
        - RDI-3.15: <3.15mm颗粒重量百分比
        - RDI-0.5: <0.5mm颗粒重量百分比
        """
        try:
            if initial_weight <= 0:
                raise ValueError("初始重量必须大于0")
                
            # 计算各指标
            weight_above_6_3 = sum(w for size, w in sieve_weights.items() if size > 6.3)
            weight_above_3_15 = sum(w for size, w in sieve_weights.items() if size > 3.15)
            weight_below_3_15 = sum(w for size, w in sieve_weights.items() if size < 3.15)
            weight_below_0_5 = sum(w for size, w in sieve_weights.items() if size < 0.5)
            
            rdi = {
                'RDI+6.3': round(weight_above_6_3 / initial_weight * 100, 2),
                'RDI+3.15': round(weight_above_3_15 / initial_weight * 100, 2),
                'RDI-3.15': round(weight_below_3_15 / initial_weight * 100, 2),
                'RDI-0.5': round(weight_below_0_5 / initial_weight * 100, 2)
            }
            
            return rdi
            
        except Exception as e:
            self.logger.error(f"计算低温粉化指数失败: {str(e)}")
            return {}
            
    def analyze_experiment_data(self, data: List[Dict]) -> Dict:
        """
        分析实验数据，生成结果报告
        
        Args:
            data: 实验数据列表
            
        Returns:
            Dict: 分析结果字典
        """
        try:
            # 提取温度和气体流量数据
            temperatures = [d['temperature'] for d in data]
            gas_flows = [d['gas_flow'] for d in data]
            timestamps = [d['timestamp'] for d in data]
            
            # 计算关键指标
            temp_mean = np.mean(temperatures)
            temp_std = np.std(temperatures)
            flow_mean = np.mean(gas_flows)
            flow_std = np.std(gas_flows)
            
            return {
                'average_temperature': round(temp_mean, 2),
                'temperature_std': round(temp_std, 2),
                'average_gas_flow': round(flow_mean, 2),
                'gas_flow_std': round(flow_std, 2),
                'experiment_duration': (timestamps[-1] - timestamps[0]).total_seconds() / 60,
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
            
            # 检查温度是否维持在500℃
            temp_mean = np.mean(temperatures)
            temp_std = np.std(temperatures)
            if abs(temp_mean - 500) > 10 or temp_std > 5:
                problems.append("温度控制不稳定，应维持在500±10℃")
                
            # 检查气体流量
            if not all(14.5 <= flow <= 15.5 for flow in gas_flows):
                problems.append("气体流量超出范围，应维持在15±0.5L/min")
                
            # 检查实验时长
            duration = (timestamps[-1] - timestamps[0]).total_seconds() / 60
            if duration < 60:  # 至少1小时
                problems.append("实验时间不足1小时")
                
        except Exception as e:
            self.logger.error(f"验证实验条件失败: {str(e)}")
            problems.append(f"数据验证过程出错: {str(e)}")
            
        return problems
