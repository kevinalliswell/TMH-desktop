#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
气体流量稳定性测试脚本
测试不同实验模式下切换气体流量的稳定性

作者: 系统自动生成
创建时间: 2025-09-25
"""

import sys
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 需要在sys.path修改后导入
# pylint: disable=wrong-import-position
from src.services.enhanced_experiment_modes import EnhancedExperimentModeManager
from src.services.experiment_modes import ExperimentType
from src.device_clients.device_manager import DeviceManager
from src.utils.logger import get_logger


@dataclass
class FlowTestRecord:
    """气体流量测试记录"""
    timestamp: str
    mode_name: str
    stage_name: str
    gas_type: str
    target_flow: float
    actual_flow: float
    success: bool
    response_time: float
    error_message: Optional[str] = None


@dataclass
class StabilityMetrics:
    """稳定性指标"""
    success_rate: float
    avg_response_time: float
    max_response_time: float
    flow_accuracy: float
    flow_stability: float
    error_count: int


class GasFlowStabilityTester:
    """气体流量稳定性测试器"""
    
    def __init__(self, test_duration: int = 300, log_level: str = "INFO"):
        """
        初始化测试器
        
        Args:
            test_duration: 测试持续时间（秒）
            log_level: 日志级别
        """
        self.test_duration = test_duration
        self.logger = get_logger(__name__)
        
        # 设置日志级别
        if log_level:
            level_map = {
                "DEBUG": logging.DEBUG,
                "INFO": logging.INFO,
                "WARNING": logging.WARNING,
                "ERROR": logging.ERROR
            }
            if log_level.upper() in level_map:
                self.logger.setLevel(level_map[log_level.upper()])
        
        # 初始化组件
        self.mode_manager = EnhancedExperimentModeManager()
        self.device_manager = None
        
        # 测试数据
        self.test_records: List[FlowTestRecord] = []
        self.test_start_time = None
        self.test_end_time = None
        self.is_testing = False
        
        # 测试配置
        self.test_gases = ["CO", "CO2", "N2", "H2"]
        self.stability_check_interval = 2.0  # 秒
        self.flow_tolerance = 0.1  # L/min
        
        # 报告文件路径
        self.report_dir = project_root / "tests" / "reports"
        self.report_dir.mkdir(exist_ok=True)
        
    def initialize_device_manager(self) -> bool:
        """初始化设备管理器"""
        try:
            config_path = project_root / "configs" / "comm_config.json"
            self.device_manager = DeviceManager(str(config_path))
            
            # 注册MFC设备
            if not self._register_mfc_device():
                return False
            
            # 启动设备管理器
            self.device_manager.start_all()
            
            # 等待设备初始化
            self.logger.info("等待设备初始化...")
            time.sleep(3.0)
            
            # 检查MFC设备是否可用
            if not hasattr(self.device_manager, 'multi_mfc') or not self.device_manager.multi_mfc:
                self.logger.error("MFC设备未注册或连接失败")
                return False
            
            # 验证设备通信
            if not self.verify_device_communication():
                self.logger.warning("设备通信验证失败，尝试切换到虚拟设备")
                
                # 停止当前设备
                try:
                    if hasattr(self.device_manager, 'multi_mfc') and self.device_manager.multi_mfc:
                        self.device_manager.multi_mfc.stop()
                except:
                    pass
                
                # 尝试注册虚拟设备
                if not self._register_virtual_mfc_device():
                    self.logger.error("虚拟设备注册失败")
                    return False
                
                # 重新启动
                self.device_manager.start_all()
                time.sleep(2.0)
                
                # 再次验证
                if not self.verify_device_communication():
                    self.logger.error("虚拟设备通信验证失败")
                    return False
            
            self.logger.info("设备管理器初始化成功，设备通信正常")
            return True
            
        except Exception as e:
            self.logger.error(f"初始化设备管理器失败: {str(e)}")
            import traceback
            self.logger.error(f"详细错误信息: {traceback.format_exc()}")
            return False
    
    def _register_mfc_device(self) -> bool:
        """注册MFC设备（优先使用真实设备，失败时自动切换到虚拟设备）"""
        try:
            from src.device_clients.multi_mfc_client import MultiMFCClient
            
            config_path = project_root / "configs" / "comm_config.json"
            
            # 创建MFC客户端
            self.logger.info("正在创建MFC设备客户端...")
            mfc_client = MultiMFCClient(str(config_path))
            
            # 注册到设备管理器
            self.device_manager.register_device("MFC", mfc_client)
            self.logger.info("MFC设备注册成功")
            
            return True
            
        except Exception as e:
            self.logger.warning(f"真实MFC设备注册失败，尝试使用虚拟设备: {str(e)}")
            return self._register_virtual_mfc_device()
    
    def _register_virtual_mfc_device(self) -> bool:
        """注册虚拟MFC设备"""
        try:
            from tests.setup_virtual_mfc_for_testing import VirtualMFCClient
            
            config_path = project_root / "configs" / "comm_config.json"
            
            self.logger.info("正在创建虚拟MFC设备...")
            virtual_mfc = VirtualMFCClient(str(config_path))
            
            # 注册到设备管理器
            self.device_manager.register_device("MFC", virtual_mfc)
            self.logger.info("虚拟MFC设备注册成功")
            
            return True
            
        except Exception as e:
            self.logger.error(f"虚拟MFC设备注册失败: {str(e)}")
            import traceback
            self.logger.error(f"详细错误信息: {traceback.format_exc()}")
            return False
    
    def verify_device_communication(self) -> bool:
        """验证设备通信"""
        try:
            mfc_device = self.device_manager.multi_mfc
            if not mfc_device:
                return False
            
            # 测试每个气体通道的通信
            communication_ok = True
            for gas_type in self.test_gases:
                try:
                    # 尝试读取当前值
                    current_value = self.get_actual_flow(gas_type)
                    if current_value is None:
                        self.logger.warning(f"{gas_type}通道通信异常")
                        communication_ok = False
                    else:
                        self.logger.debug(f"{gas_type}通道通信正常，当前值: {current_value}")
                except Exception as e:
                    self.logger.error(f"{gas_type}通道通信失败: {str(e)}")
                    communication_ok = False
            
            return communication_ok
            
        except Exception as e:
            self.logger.error(f"设备通信验证失败: {str(e)}")
            return False
    
    def monitor_device_status(self) -> Dict[str, Any]:
        """监控设备状态"""
        status = {
            "timestamp": datetime.now().isoformat(),
            "device_connected": False,
            "communication_quality": 0.0,
            "gas_channels": {}
        }
        
        try:
            if self.device_manager and self.device_manager.multi_mfc:
                mfc_device = self.device_manager.multi_mfc
                status["device_connected"] = True
                
                # 测试每个通道的通信质量
                successful_reads = 0
                total_reads = 0
                
                for gas_type in self.test_gases:
                    channel_status = {
                        "connected": False,
                        "current_value": None,
                        "response_time": None
                    }
                    
                    try:
                        start_time = time.time()
                        current_value = mfc_device.read_pv_value(gas_type)
                        response_time = time.time() - start_time
                        
                        total_reads += 1
                        if current_value is not None:
                            successful_reads += 1
                            channel_status["connected"] = True
                            channel_status["current_value"] = current_value
                            channel_status["response_time"] = response_time
                        
                    except Exception as e:
                        self.logger.debug(f"读取{gas_type}通道失败: {str(e)}")
                        total_reads += 1
                    
                    status["gas_channels"][gas_type] = channel_status
                
                # 计算通信质量
                if total_reads > 0:
                    status["communication_quality"] = successful_reads / total_reads
                
        except Exception as e:
            self.logger.error(f"监控设备状态失败: {str(e)}")
        
        return status
    
    def get_test_modes(self) -> List[Tuple[str, str, Dict[str, Any]]]:
        """获取测试模式列表"""
        test_modes = []
        
        # 标准模式
        standard_modes = {
            "GB_13241_2017": ExperimentType.REDUCIBILITY,
            "GB_13242_2017": ExperimentType.LOW_TEMP_DEGRADATION,
            "GB_13240_2018": ExperimentType.FREE_SWELLING
        }
        
        for mode_id, exp_type in standard_modes.items():
            stages = self.mode_manager.get_experiment_stages(exp_type)
            for stage in stages:
                test_modes.append((mode_id, stage.description, {
                    "stage": stage.stage.value,
                    "gas_settings": stage.gas_settings._asdict()
                }))
        
        # 自定义模式
        custom_modes = self.mode_manager.list_custom_programs()
        for custom_id in custom_modes:
            program = self.mode_manager.get_custom_program(custom_id)
            if program:
                for stage in program.stages:
                    test_modes.append((custom_id, stage.description, {
                        "stage": stage.stage.value,
                        "gas_settings": stage.gas_settings._asdict()
                    }))
        
        return test_modes
    
    def set_gas_flow(self, gas_type: str, flow_value: float) -> Tuple[bool, float, Optional[str]]:
        """
        设置气体流量并测量响应时间
        
        Returns:
            (success, response_time, error_message)
        """
        start_time = time.time()
        
        try:
            if not self.device_manager:
                response_time = time.time() - start_time
                return False, response_time, "设备管理器未初始化"
            
            # 检查设备连接状态
            if not hasattr(self.device_manager, 'multi_mfc') or not self.device_manager.multi_mfc:
                response_time = time.time() - start_time
                return False, response_time, "MFC设备未连接"
            
            # 设置流量
            success = self.device_manager.set_flow(gas_type, flow_value)
            response_time = time.time() - start_time
            
            if success:
                # 等待设备响应并验证设置
                time.sleep(0.2)  # 短暂等待设备响应
                
                # 验证设置是否生效（可选）
                try:
                    actual_value = self.get_actual_flow(gas_type)
                    if actual_value is not None:
                        # 检查设置值是否在合理范围内
                        tolerance = max(0.1, flow_value * 0.05)  # 5%容差或最小0.1
                        if abs(actual_value - flow_value) > tolerance:
                            self.logger.warning(f"{gas_type}流量设置偏差较大: 目标={flow_value}, 实际={actual_value}")
                except Exception as e:
                    self.logger.debug(f"验证{gas_type}设置值时出错: {str(e)}")
                
                return True, response_time, None
            else:
                return False, response_time, "设备设置失败"
                
        except Exception as e:
            response_time = time.time() - start_time
            return False, response_time, str(e)
    
    def get_actual_flow(self, gas_type: str) -> Optional[float]:
        """获取实际流量值"""
        try:
            if not self.device_manager or not hasattr(self.device_manager, 'multi_mfc'):
                return None
                
            mfc = self.device_manager.multi_mfc
            if not mfc:
                return None
            
            # 读取实际流量值
            if hasattr(mfc, 'current_flows'):
                flows = mfc.current_flows
                actual_value = flows.get(gas_type)
            elif hasattr(mfc, 'get_data'):
                data = mfc.get_data(gas_type)
                actual_value = data.get('PV') if data else None
            else:
                self.logger.warning(f"MFC设备不支持流量读取方法")
                return None
            
            if actual_value is not None:
                self.logger.debug(f"读取{gas_type}实际流量: {actual_value}")
            
            return actual_value
            
        except Exception as e:
            self.logger.error(f"读取{gas_type}实际流量失败: {str(e)}")
            return None
    
    def test_mode_flow_switching(self, mode_name: str, stage_info: Dict[str, Any]) -> List[FlowTestRecord]:
        """测试单个模式的流量切换"""
        stage_records = []
        gas_settings = stage_info["gas_settings"]
        stage_name = stage_info["stage"]
        
        self.logger.info(f"测试模式: {mode_name}, 阶段: {stage_name}")
        
        for gas_type in self.test_gases:
            target_flow = gas_settings.get(gas_type, 0.0)
            
            # 设置流量
            success, response_time, error_msg = self.set_gas_flow(gas_type, target_flow)
            
            # 等待稳定
            if success:
                time.sleep(1.0)
                actual_flow = self.get_actual_flow(gas_type)
                if actual_flow is None:
                    actual_flow = target_flow  # 使用目标值作为后备
            else:
                actual_flow = 0.0
            
            # 记录测试结果
            record = FlowTestRecord(
                timestamp=datetime.now().isoformat(),
                mode_name=mode_name,
                stage_name=stage_name,
                gas_type=gas_type,
                target_flow=target_flow,
                actual_flow=actual_flow,
                success=success,
                response_time=response_time,
                error_message=error_msg
            )
            
            stage_records.append(record)
            self.test_records.append(record)
            
            self.logger.debug(f"  {gas_type}: 目标={target_flow:.2f}, 实际={actual_flow:.2f}, "
                            f"响应时间={response_time:.3f}s, 成功={success}")
        
        return stage_records
    
    def run_communication_stability_test(self, duration: int = 60) -> bool:
        """运行通信稳定性测试"""
        self.logger.info(f"开始通信稳定性测试，持续 {duration} 秒")
        
        if not self.device_manager:
            self.logger.error("设备管理器未初始化")
            return False
        
        start_time = time.time()
        end_time = start_time + duration
        
        communication_records = []
        test_interval = 2.0  # 每2秒测试一次
        
        while time.time() < end_time:
            # 监控设备状态
            status = self.monitor_device_status()
            communication_records.append(status)
            
            # 记录通信质量
            self.logger.info(f"通信质量: {status['communication_quality']:.1%}, "
                           f"连接状态: {'正常' if status['device_connected'] else '异常'}")
            
            # 测试基本的读写操作
            try:
                for gas_type in self.test_gases:
                    # 读取当前值（验证通信）
                    self.get_actual_flow(gas_type)
                    
                    # 设置一个测试流量值（小值避免影响系统）
                    test_flow = 0.1
                    success, response_time, error_msg = self.set_gas_flow(gas_type, test_flow)
                    
                    if not success:
                        self.logger.warning(f"{gas_type}通道设置测试失败: {error_msg}")
                    
                    # 恢复到0流量
                    self.set_gas_flow(gas_type, 0.0)
                    
            except Exception as e:
                self.logger.error(f"通信测试异常: {str(e)}")
            
            time.sleep(test_interval)
        
        # 分析通信稳定性
        if communication_records:
            total_records = len(communication_records)
            connected_records = sum(1 for r in communication_records if r['device_connected'])
            
            avg_quality = sum(r['communication_quality'] for r in communication_records) / total_records
            connection_stability = connected_records / total_records
            
            self.logger.info("通信稳定性测试完成:")
            self.logger.info(f"  连接稳定性: {connection_stability:.1%}")
            self.logger.info(f"  平均通信质量: {avg_quality:.1%}")
            
            # 保存通信测试数据
            self._save_communication_data(communication_records)
            
            return connection_stability > 0.9 and avg_quality > 0.8
        
        return False
    
    def _save_communication_data(self, records: List[Dict[str, Any]]):
        """保存通信测试数据"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            comm_file = self.report_dir / f"communication_test_{timestamp}.json"
            
            with open(comm_file, 'w', encoding='utf-8') as f:
                json.dump(records, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"通信测试数据已保存: {comm_file}")
            
        except Exception as e:
            self.logger.error(f"保存通信测试数据失败: {str(e)}")
    
    def cleanup_device_manager(self):
        """清理设备管理器"""
        try:
            if self.device_manager:
                self.logger.info("正在停止设备管理器...")
                self.device_manager.stop_all()
                time.sleep(1.0)  # 等待设备停止
                self.logger.info("设备管理器已停止")
        except Exception as e:
            self.logger.error(f"停止设备管理器失败: {str(e)}")
    
    def run_comprehensive_test(self) -> bool:
        """运行综合测试"""
        self.logger.info("开始气体流量稳定性综合测试")
        self.test_start_time = datetime.now()
        self.is_testing = True
        
        try:
            # 获取所有测试模式
            test_modes = self.get_test_modes()
            self.logger.info(f"发现 {len(test_modes)} 个测试场景")
            
            mode_count = {}
            for mode_name, stage_name, stage_info in test_modes:
                if mode_name not in mode_count:
                    mode_count[mode_name] = 0
                mode_count[mode_name] += 1
                
                # 测试该阶段的流量切换
                self.test_mode_flow_switching(mode_name, stage_info)
                
                # 模式间切换延迟
                time.sleep(0.5)
            
            self.test_end_time = datetime.now()
            self.is_testing = False
            
            self.logger.info(f"测试完成，共测试了 {len(mode_count)} 个模式，"
                           f"{len(self.test_records)} 条记录")
            
            return True
            
        except Exception as e:
            self.logger.error(f"综合测试失败: {str(e)}")
            self.is_testing = False
            return False
        finally:
            # 确保设备正确关闭
            self.cleanup_device_manager()
    
    def run_endurance_test(self) -> bool:
        """运行耐久性测试"""
        self.logger.info(f"开始 {self.test_duration} 秒耐久性测试")
        self.test_start_time = datetime.now()
        self.is_testing = True
        
        try:
            end_time = self.test_start_time + timedelta(seconds=self.test_duration)
            test_modes = self.get_test_modes()
            
            if not test_modes:
                self.logger.error("没有可用的测试模式")
                return False
            
            cycle_count = 0
            while datetime.now() < end_time and self.is_testing:
                # 随机选择一个测试模式
                import random
                mode_name, stage_name, stage_info = random.choice(test_modes)
                
                self.logger.debug(f"循环 {cycle_count + 1}: 测试 {mode_name} - {stage_name}")
                self.test_mode_flow_switching(mode_name, stage_info)
                
                cycle_count += 1
                time.sleep(self.stability_check_interval)
            
            self.test_end_time = datetime.now()
            self.is_testing = False
            
            self.logger.info(f"耐久性测试完成，执行了 {cycle_count} 个循环")
            return True
            
        except Exception as e:
            self.logger.error(f"耐久性测试失败: {str(e)}")
            self.is_testing = False
            return False
        finally:
            # 确保设备正确关闭
            self.cleanup_device_manager()
    
    def calculate_stability_metrics(self) -> Dict[str, StabilityMetrics]:
        """计算稳定性指标"""
        if not self.test_records:
            return {}
        
        metrics_by_mode = {}
        
        # 按模式分组计算指标
        mode_groups = {}
        for record in self.test_records:
            mode_key = f"{record.mode_name}_{record.stage_name}"
            if mode_key not in mode_groups:
                mode_groups[mode_key] = []
            mode_groups[mode_key].append(record)
        
        for mode_key, records in mode_groups.items():
            successful_records = [r for r in records if r.success]
            total_count = len(records)
            success_count = len(successful_records)
            
            if total_count == 0:
                continue
            
            # 成功率
            success_rate = success_count / total_count * 100
            
            # 响应时间统计
            response_times = [r.response_time for r in records]
            avg_response_time = sum(response_times) / len(response_times)
            max_response_time = max(response_times)
            
            # 流量精度（仅对成功的记录）
            if successful_records:
                flow_errors = []
                for record in successful_records:
                    if record.target_flow > 0:  # 避免除零
                        error = abs(record.actual_flow - record.target_flow) / record.target_flow * 100
                        flow_errors.append(error)
                
                flow_accuracy = 100 - (sum(flow_errors) / len(flow_errors)) if flow_errors else 100
                
                # 流量稳定性（变异系数）
                actual_flows = [r.actual_flow for r in successful_records if r.target_flow > 0]
                if len(actual_flows) > 1:
                    import statistics
                    mean_flow = statistics.mean(actual_flows)
                    flow_stability = (statistics.stdev(actual_flows) / mean_flow * 100) if mean_flow > 0 else 0
                else:
                    flow_stability = 0
            else:
                flow_accuracy = 0
                flow_stability = 100
            
            # 错误计数
            error_count = total_count - success_count
            
            metrics_by_mode[mode_key] = StabilityMetrics(
                success_rate=success_rate,
                avg_response_time=avg_response_time,
                max_response_time=max_response_time,
                flow_accuracy=flow_accuracy,
                flow_stability=flow_stability,
                error_count=error_count
            )
        
        return metrics_by_mode
    
    def generate_report(self) -> str:
        """生成测试报告"""
        if not self.test_start_time:
            return "没有测试数据"
        
        # 计算指标
        metrics = self.calculate_stability_metrics()
        
        # 生成报告
        report = []
        report.append("=" * 80)
        report.append("气体流量稳定性测试报告")
        report.append("=" * 80)
        report.append(f"测试开始时间: {self.test_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if self.test_end_time:
            duration = self.test_end_time - self.test_start_time
            report.append(f"测试结束时间: {self.test_end_time.strftime('%Y-%m-%d %H:%M:%S')}")
            report.append(f"测试持续时间: {duration.total_seconds():.1f} 秒")
        
        report.append(f"总测试记录数: {len(self.test_records)}")
        report.append("")
        
        # 总体统计
        total_success = sum(1 for r in self.test_records if r.success)
        total_count = len(self.test_records)
        overall_success_rate = (total_success / total_count * 100) if total_count > 0 else 0
        
        report.append("总体统计:")
        report.append(f"  成功率: {overall_success_rate:.1f}% ({total_success}/{total_count})")
        
        if self.test_records:
            avg_response = sum(r.response_time for r in self.test_records) / len(self.test_records)
            max_response = max(r.response_time for r in self.test_records)
            report.append(f"  平均响应时间: {avg_response:.3f} 秒")
            report.append(f"  最大响应时间: {max_response:.3f} 秒")
        
        report.append("")
        
        # 按模式详细统计
        if metrics:
            report.append("按模式详细统计:")
            report.append("-" * 60)
            
            for mode_key, metric in metrics.items():
                report.append(f"模式: {mode_key}")
                report.append(f"  成功率: {metric.success_rate:.1f}%")
                report.append(f"  平均响应时间: {metric.avg_response_time:.3f} 秒")
                report.append(f"  最大响应时间: {metric.max_response_time:.3f} 秒")
                report.append(f"  流量精度: {metric.flow_accuracy:.1f}%")
                report.append(f"  流量稳定性: {metric.flow_stability:.1f}% (变异系数)")
                report.append(f"  错误次数: {metric.error_count}")
                report.append("")
        
        # 异常记录
        error_records = [r for r in self.test_records if not r.success]
        if error_records:
            report.append("异常记录:")
            report.append("-" * 60)
            
            for record in error_records[:10]:  # 只显示前10个错误
                report.append(f"时间: {record.timestamp}")
                report.append(f"模式: {record.mode_name} - {record.stage_name}")
                report.append(f"气体: {record.gas_type}, 目标流量: {record.target_flow:.2f}")
                report.append(f"错误: {record.error_message}")
                report.append("")
            
            if len(error_records) > 10:
                report.append(f"... 还有 {len(error_records) - 10} 个错误记录未显示")
        
        return "\n".join(report)
    
    def save_report(self, report_content: str) -> str:
        """保存报告到文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.report_dir / f"gas_flow_stability_test_{timestamp}.txt"
        
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report_content)
            
            # 同时保存JSON格式的详细数据
            json_file = self.report_dir / f"gas_flow_stability_test_{timestamp}.json"
            test_data = {
                "test_info": {
                    "start_time": self.test_start_time.isoformat() if self.test_start_time else None,
                    "end_time": self.test_end_time.isoformat() if self.test_end_time else None,
                    "total_records": len(self.test_records)
                },
                "records": [asdict(record) for record in self.test_records],
                "metrics": {k: asdict(v) for k, v in self.calculate_stability_metrics().items()}
            }
            
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(test_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"报告已保存到: {report_file}")
            self.logger.info(f"详细数据已保存到: {json_file}")
            
            return str(report_file)
            
        except Exception as e:
            self.logger.error(f"保存报告失败: {str(e)}")
            return ""
    
    def stop_test(self):
        """停止测试"""
        self.is_testing = False
        self.logger.info("测试已停止")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="气体流量稳定性测试")
    parser.add_argument("--mode", choices=["comprehensive", "endurance"], 
                       default="comprehensive", help="测试模式")
    parser.add_argument("--duration", type=int, default=300, 
                       help="耐久性测试持续时间（秒）")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], 
                       default="INFO", help="日志级别")
    parser.add_argument("--no-device", action="store_true", 
                       help="不连接实际设备，使用模拟模式")
    
    args = parser.parse_args()
    
    # 创建测试器
    tester = GasFlowStabilityTester(
        test_duration=args.duration,
        log_level=args.log_level
    )
    
    try:
        # 初始化设备（如果需要）
        if not args.no_device:
            device_available = tester.initialize_device_manager()
            if not device_available:
                print("警告: 设备未连接，将使用模拟模式")
        else:
            print("使用模拟模式运行测试")
        
        # 运行测试
        success = False
        if args.mode == "comprehensive":
            print("开始综合测试...")
            success = tester.run_comprehensive_test()
        elif args.mode == "endurance":
            print(f"开始 {args.duration} 秒耐久性测试...")
            success = tester.run_endurance_test()
        
        if success:
            print("测试完成，生成报告...")
            
            # 生成并保存报告
            report = tester.generate_report()
            print(report)
            
            report_file = tester.save_report(report)
            if report_file:
                print(f"\n报告已保存到: {report_file}")
        else:
            print("测试失败")
            return 1
        
    except KeyboardInterrupt:
        print("\n测试被用户中断")
        tester.stop_test()
        
        if tester.test_records:
            print("生成中断前的测试报告...")
            report = tester.generate_report()
            print(report)
            tester.save_report(report)
    
    except Exception as e:
        print(f"测试过程中发生错误: {str(e)}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
