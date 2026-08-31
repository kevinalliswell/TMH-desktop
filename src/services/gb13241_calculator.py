# src/services/gb13241_calculator.py
import math
from typing import List, Dict, Optional
import numpy as np
import logging
from datetime import datetime

class ReductionCalculator:
    """GB/T 13241-2017 还原性计算器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def calculate_reduction_degree(
        self,
        initial_weight: float,
        current_weight: float,
        total_iron_content: float,
        feo_content: float,
    ) -> Optional[float]:
        """
        计算还原度
        
        Args:
            initial_weight: 初始重量 (g)
            current_weight: 当前重量 (g)
            total_iron_content: 全铁含量 w(TFe) (%)
            feo_content: 氧化亚铁含量 w(FeO) (%)
            
        Returns:
            float: 还原度 (%)，计算失败返回None
            
        公式：Rt = [0.111·w(FeO)/(0.430·w(TFe))
                    + (m0-mt)/(m0·0.430·w(TFe))] × 100%
        """
        try:
            initial_weight = float(initial_weight)
            current_weight = float(current_weight)
            total_iron_content = float(total_iron_content)
            feo_content = float(feo_content)
            values = (initial_weight, current_weight, total_iron_content, feo_content)
            if not all(math.isfinite(value) for value in values):
                raise ValueError("还原度输入必须是有限数值")
            if initial_weight <= 0 or not 0 < total_iron_content <= 100:
                raise ValueError("初始重量必须大于0且全铁含量须在(0, 100]范围内")
            if not 0 <= feo_content <= 100:
                raise ValueError("FeO含量须在[0, 100]范围内")

            total_iron_fraction = total_iron_content / 100.0
            feo_fraction = feo_content / 100.0
            bound_oxygen_fraction = 0.430 * total_iron_fraction
            feo_baseline = 0.111 * feo_fraction / bound_oxygen_fraction
            weight_loss_term = (
                (initial_weight - current_weight)
                / (initial_weight * bound_oxygen_fraction)
            )
            reduction_degree = (feo_baseline + weight_loss_term) * 100
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

    @staticmethod
    def _interpolate_at_time(
        series: List[tuple[float, float]],
        target_minutes: float,
    ) -> Optional[float]:
        if not series or target_minutes < series[0][0] or target_minutes > series[-1][0]:
            return None
        for index, (minutes, value) in enumerate(series):
            if minutes == target_minutes:
                return value
            if minutes > target_minutes and index > 0:
                previous_minutes, previous_value = series[index - 1]
                span = minutes - previous_minutes
                if span <= 0:
                    continue
                ratio = (target_minutes - previous_minutes) / span
                return previous_value + (value - previous_value) * ratio
        return None

    @staticmethod
    def _first_crossing_time(
        series: List[tuple[float, float]],
        target_value: float,
    ) -> Optional[float]:
        if not series:
            return None
        if series[0][1] >= target_value:
            return series[0][0]
        for index in range(1, len(series)):
            previous_minutes, previous_value = series[index - 1]
            minutes, value = series[index]
            if previous_value < target_value <= value:
                span = value - previous_value
                if span <= 0:
                    continue
                ratio = (target_value - previous_value) / span
                return previous_minutes + (minutes - previous_minutes) * ratio
        return None

    @staticmethod
    def _prepare_reduction_series(data: List[Dict]) -> List[tuple[float, float]]:
        has_co_measurements = any("co_flow" in point for point in data)
        start_index = 0
        if has_co_measurements:
            start_index = next(
                (
                    index
                    for index, point in enumerate(data)
                    if isinstance(point.get("co_flow"), (int, float))
                    and math.isfinite(float(point["co_flow"]))
                    and float(point["co_flow"]) > 0.0
                ),
                -1,
            )
            if start_index < 0:
                return []

        valid_points = []
        for point in data[start_index:]:
            timestamp = point.get("timestamp")
            if isinstance(timestamp, str):
                try:
                    timestamp = datetime.fromisoformat(timestamp)
                except ValueError:
                    continue
            if not isinstance(timestamp, datetime):
                continue
            try:
                weight = float(point.get("weight"))
            except (TypeError, ValueError):
                continue
            if not math.isfinite(weight):
                continue
            valid_points.append((timestamp, weight))

        if not valid_points:
            return []
        valid_points.sort(key=lambda item: item[0])
        started_at = valid_points[0][0]
        return [
            ((timestamp - started_at).total_seconds() / 60.0, weight)
            for timestamp, weight in valid_points
        ]
            
    def analyze_experiment_data(
        self,
        data: List[Dict],
        total_iron_content: Optional[float],
        feo_content: Optional[float],
        initial_sample_weight: Optional[float] = None,
    ) -> Dict:
        """
        分析实验数据，生成结果报告
        
        Args:
            data: 实验数据列表
            total_iron_content: 全铁含量 w(TFe) (%)
            feo_content: 氧化亚铁含量 w(FeO) (%)
            initial_sample_weight: 实验记录的初始样重 m0 (g)
            
        Returns:
            Dict: 分析结果字典
        """
        try:
            weight_series = self._prepare_reduction_series(data)
            if not weight_series:
                return {}

            initial_weight = self._positive_number_or_none(initial_sample_weight)
            if initial_weight is None:
                initial_weight = weight_series[0][1]
            final_weight = weight_series[-1][1]
            total_iron_content_value = self._percentage_or_none(
                total_iron_content,
                allow_zero=False,
            )
            feo_content_value = self._percentage_or_none(
                feo_content,
                allow_zero=True,
            )

            degree_series: List[tuple[float, float]] = []
            if total_iron_content_value is not None and feo_content_value is not None:
                for minutes, weight in weight_series:
                    degree = self.calculate_reduction_degree(
                        initial_weight,
                        weight,
                        total_iron_content_value,
                        feo_content_value,
                    )
                    if degree is not None:
                        degree_series.append((minutes, degree))

            weights_at = {
                minutes: self._interpolate_at_time(weight_series, minutes)
                for minutes in (30.0, 60.0, 90.0)
            }
            degrees_at = {
                minutes: self._interpolate_at_time(degree_series, minutes)
                for minutes in (30.0, 60.0, 90.0)
            }
            reduction_rate = None
            if degrees_at[30.0] is not None and degrees_at[60.0] is not None:
                reduction_rate = round((degrees_at[60.0] - degrees_at[30.0]) / 30.0, 3)

            return {
                "initial_weight": round(initial_weight, 3),
                "initial_sample_weight": round(initial_weight, 3),
                "final_weight": round(final_weight, 3),
                "total_weight_loss": round(initial_weight - final_weight, 3),
                "total_iron_content": total_iron_content_value,
                "feo_content": feo_content_value,
                "oxygen_loss_at_30min": self._weight_loss(initial_weight, weights_at[30.0]),
                "oxygen_loss_at_60min": self._weight_loss(initial_weight, weights_at[60.0]),
                "oxygen_loss_at_90min": self._weight_loss(initial_weight, weights_at[90.0]),
                "reduction_degree_at_30min_percent": degrees_at[30.0],
                "reduction_degree_at_60min_percent": degrees_at[60.0],
                "reduction_degree_at_90min_percent": degrees_at[90.0],
                "final_reduction_degree": degree_series[-1][1] if degree_series else None,
                "reduction_index": reduction_rate,
                "time_to_40_percent_reduction_min": self._first_crossing_time(degree_series, 40.0),
                "time_to_50_percent_reduction_min": self._first_crossing_time(degree_series, 50.0),
                "time_to_70_percent_reduction_min": self._first_crossing_time(degree_series, 70.0),
                "experiment_duration": weight_series[-1][0],
                "data_points": len(weight_series),
            }
            
        except Exception as e:
            self.logger.error(f"分析实验数据失败: {str(e)}")
            return {}

    @staticmethod
    def _weight_loss(initial_weight: float, current_weight: Optional[float]) -> Optional[float]:
        if current_weight is None:
            return None
        return round(initial_weight - current_weight, 3)

    @staticmethod
    def _positive_number_or_none(value) -> Optional[float]:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) and number > 0 else None

    @staticmethod
    def _percentage_or_none(value, *, allow_zero: bool) -> Optional[float]:
        try:
            percentage = float(value)
        except (TypeError, ValueError):
            return None
        lower_bound_ok = percentage >= 0 if allow_zero else percentage > 0
        return percentage if math.isfinite(percentage) and lower_bound_ok and percentage <= 100 else None
            
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
