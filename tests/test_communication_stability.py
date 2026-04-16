#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
通讯稳定性和重连机制测试脚本

测试内容：
1. 持续重连机制验证
2. 数据采集稳定性测试
3. 数据库写入压力测试
4. 断线恢复能力测试
"""

import sys
import os
import time
import threading
from datetime import datetime
import json

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.device_clients.device_manager import DeviceManager
from src.device_clients.data_handler import DataHandler
from src.device_clients.device_health_monitor import DeviceHealthMonitor
from src.device_clients.balance_client import BalanceClient
from src.device_clients.temp_client import TempClient
from src.device_clients.multi_mfc_client import MultiMFCClient
from src.utils.path_manager import PathManager
from src.utils.logger import get_logger

logger = get_logger("通讯稳定性测试")


class CommunicationStabilityTest:
    """通讯稳定性测试类"""
    
    def __init__(self):
        self.logger = logger
        self.config_path = PathManager.get_config_path('comm_config.json')
        self.device_manager = None
        self.data_handler = None
        self.health_monitor = None
        self.test_results = {
            'start_time': None,
            'end_time': None,
            'duration': 0,
            'tests_passed': 0,
            'tests_failed': 0,
            'details': []
        }
    
    def setup(self):
        """初始化测试环境"""
        self.logger.info("=" * 60)
        self.logger.info("初始化测试环境...")
        self.logger.info("=" * 60)
        
        try:
            # 初始化设备管理器
            self.device_manager = DeviceManager(config_path=self.config_path)
            
            # 注册设备
            try:
                balance = BalanceClient(config_path=self.config_path)
                self.device_manager.register_device("Balance", balance)
                self.logger.info("天平设备已注册")
            except Exception as e:
                self.logger.warning(f"天平设备注册失败: {e}")
            
            try:
                temp = TempClient(config_path=self.config_path)
                self.device_manager.register_device("Temp", temp)
                self.logger.info("温度控制器已注册")
            except Exception as e:
                self.logger.warning(f"温度控制器注册失败: {e}")
            
            try:
                mfc = MultiMFCClient(config_path=self.config_path)
                self.device_manager.register_device("MFC", mfc)
                self.logger.info("MFC设备已注册")
            except Exception as e:
                self.logger.warning(f"MFC设备注册失败: {e}")
            
            # 初始化数据处理器
            db_path = PathManager.get_data_path('test_data.db')
            self.data_handler = DataHandler(db_path=db_path, save_interval=10)
            self.data_handler.set_device_manager(self.device_manager)
            
            # 初始化健康监控
            self.health_monitor = DeviceHealthMonitor(self.device_manager, check_interval=2.0)
            
            self.logger.info("测试环境初始化完成")
            return True
            
        except Exception as e:
            self.logger.error(f"测试环境初始化失败: {e}")
            return False
    
    def teardown(self):
        """清理测试环境"""
        self.logger.info("=" * 60)
        self.logger.info("清理测试环境...")
        self.logger.info("=" * 60)
        
        try:
            if self.health_monitor:
                self.health_monitor.stop_monitoring()
            
            if self.data_handler:
                self.data_handler.stop()
            
            if self.device_manager:
                self.device_manager.stop_all()
            
            self.logger.info("测试环境清理完成")
            
        except Exception as e:
            self.logger.error(f"测试环境清理失败: {e}")
    
    def test_reconnection_mechanism(self, duration=60):
        """测试1: 持续重连机制验证
        
        Args:
            duration: 测试持续时间（秒）
        """
        test_name = "持续重连机制验证"
        self.logger.info(f"\n{'=' * 60}")
        self.logger.info(f"测试1: {test_name} (持续{duration}秒)")
        self.logger.info(f"{'=' * 60}")
        
        result = {
            'test_name': test_name,
            'status': 'PASS',
            'details': [],
            'metrics': {}
        }
        
        try:
            # 启动设备
            self.device_manager.start_all()
            self.logger.info("所有设备已启动")
            
            # 监控连接状态
            start_time = time.time()
            check_interval = 5  # 每5秒检查一次
            
            reconnection_events = []
            connection_status_history = []
            
            while time.time() - start_time < duration:
                # 获取连接状态
                is_connected, device_names, error_msg = self.device_manager.get_connection_status()
                
                status_info = {
                    'timestamp': time.time() - start_time,
                    'connected': is_connected,
                    'devices': device_names,
                    'error': error_msg
                }
                connection_status_history.append(status_info)
                
                # 检查设备连接健康度
                for device_name, device in self.device_manager.devices.items():
                    if hasattr(device, 'connection_healthy'):
                        if not device.connection_healthy:
                            reconnection_events.append({
                                'timestamp': time.time() - start_time,
                                'device': device_name,
                                'reconnect_attempt': getattr(device, 'reconnect_attempt', 0)
                            })
                
                # 显示状态
                if is_connected:
                    self.logger.info(f"[{time.time() - start_time:.1f}s] 连接正常: {device_names}")
                else:
                    self.logger.warning(f"[{time.time() - start_time:.1f}s] 连接异常: {error_msg}")
                
                time.sleep(check_interval)
            
            # 统计结果
            total_checks = len(connection_status_history)
            connected_checks = sum(1 for s in connection_status_history if s['connected'])
            connection_rate = (connected_checks / total_checks * 100) if total_checks > 0 else 0
            
            result['metrics'] = {
                'total_checks': total_checks,
                'connected_checks': connected_checks,
                'connection_rate': f"{connection_rate:.1f}%",
                'reconnection_events': len(reconnection_events)
            }
            
            result['details'].append(f"连接成功率: {connection_rate:.1f}% ({connected_checks}/{total_checks})")
            result['details'].append(f"重连事件次数: {len(reconnection_events)}")
            
            # 判断测试结果
            if connection_rate >= 90:
                result['status'] = 'PASS'
                result['details'].append("✓ 重连机制工作正常，连接稳定性良好")
                self.test_results['tests_passed'] += 1
            else:
                result['status'] = 'FAIL'
                result['details'].append("✗ 连接稳定性不足，需要检查")
                self.test_results['tests_failed'] += 1
            
        except Exception as e:
            result['status'] = 'ERROR'
            result['details'].append(f"测试异常: {str(e)}")
            self.test_results['tests_failed'] += 1
            self.logger.error(f"测试异常: {e}")
        
        self.test_results['details'].append(result)
        self._print_test_result(result)
        return result
    
    def test_data_collection_stability(self, duration=60):
        """测试2: 数据采集稳定性测试
        
        Args:
            duration: 测试持续时间（秒）
        """
        test_name = "数据采集稳定性测试"
        self.logger.info(f"\n{'=' * 60}")
        self.logger.info(f"测试2: {test_name} (持续{duration}秒)")
        self.logger.info(f"{'=' * 60}")
        
        result = {
            'test_name': test_name,
            'status': 'PASS',
            'details': [],
            'metrics': {}
        }
        
        try:
            # 启动数据处理器
            self.data_handler.start()
            self.logger.info("数据处理器已启动")
            
            # 监控数据采集
            start_time = time.time()
            check_interval = 5
            
            data_samples = {
                'temperature': [],
                'weight': [],
                'flows': []
            }
            
            while time.time() - start_time < duration:
                status = self.device_manager.get_status()
                
                # 收集数据样本
                if status.get('temperature'):
                    data_samples['temperature'].append(status['temperature'])
                if status.get('weight'):
                    data_samples['weight'].append(status['weight'])
                if status.get('flows'):
                    data_samples['flows'].append(status['flows'])
                
                time.sleep(check_interval)
            
            # 统计数据采集率
            expected_samples = duration / check_interval
            
            temp_rate = (len(data_samples['temperature']) / expected_samples * 100) if expected_samples > 0 else 0
            weight_rate = (len(data_samples['weight']) / expected_samples * 100) if expected_samples > 0 else 0
            flow_rate = (len(data_samples['flows']) / expected_samples * 100) if expected_samples > 0 else 0
            
            result['metrics'] = {
                'temperature_samples': len(data_samples['temperature']),
                'temperature_rate': f"{temp_rate:.1f}%",
                'weight_samples': len(data_samples['weight']),
                'weight_rate': f"{weight_rate:.1f}%",
                'flow_samples': len(data_samples['flows']),
                'flow_rate': f"{flow_rate:.1f}%"
            }
            
            result['details'].append(f"温度数据采集率: {temp_rate:.1f}%")
            result['details'].append(f"重量数据采集率: {weight_rate:.1f}%")
            result['details'].append(f"流量数据采集率: {flow_rate:.1f}%")
            
            # 判断测试结果
            avg_rate = (temp_rate + weight_rate + flow_rate) / 3
            if avg_rate >= 85:
                result['status'] = 'PASS'
                result['details'].append("✓ 数据采集稳定性良好")
                self.test_results['tests_passed'] += 1
            else:
                result['status'] = 'FAIL'
                result['details'].append("✗ 数据采集率不足，存在停滞")
                self.test_results['tests_failed'] += 1
            
        except Exception as e:
            result['status'] = 'ERROR'
            result['details'].append(f"测试异常: {str(e)}")
            self.test_results['tests_failed'] += 1
            self.logger.error(f"测试异常: {e}")
        
        self.test_results['details'].append(result)
        self._print_test_result(result)
        return result
    
    def test_database_write_stability(self, duration=30):
        """测试3: 数据库写入压力测试
        
        Args:
            duration: 测试持续时间（秒）
        """
        test_name = "数据库写入压力测试"
        self.logger.info(f"\n{'=' * 60}")
        self.logger.info(f"测试3: {test_name} (持续{duration}秒)")
        self.logger.info(f"{'=' * 60}")
        
        result = {
            'test_name': test_name,
            'status': 'PASS',
            'details': [],
            'metrics': {}
        }
        
        try:
            # 确保数据处理器在运行
            if not self.data_handler.is_running:
                self.data_handler.start()
            
            start_time = time.time()
            initial_queue_size = self.data_handler.data_buffer.qsize()
            
            # 监控数据缓冲区
            max_queue_size = 0
            queue_full_count = 0
            
            while time.time() - start_time < duration:
                current_queue_size = self.data_handler.data_buffer.qsize()
                max_queue_size = max(max_queue_size, current_queue_size)
                
                if current_queue_size >= 1000:  # 接近最大容量
                    queue_full_count += 1
                    self.logger.warning(f"数据缓冲区接近满载: {current_queue_size}/1000")
                
                time.sleep(2)
            
            final_queue_size = self.data_handler.data_buffer.qsize()
            
            result['metrics'] = {
                'initial_queue_size': initial_queue_size,
                'final_queue_size': final_queue_size,
                'max_queue_size': max_queue_size,
                'queue_full_count': queue_full_count
            }
            
            result['details'].append(f"初始缓冲区大小: {initial_queue_size}")
            result['details'].append(f"最终缓冲区大小: {final_queue_size}")
            result['details'].append(f"最大缓冲区大小: {max_queue_size}")
            result['details'].append(f"缓冲区满载次数: {queue_full_count}")
            
            # 判断测试结果
            if max_queue_size < 900 and queue_full_count == 0:
                result['status'] = 'PASS'
                result['details'].append("✓ 数据库写入稳定，无积压")
                self.test_results['tests_passed'] += 1
            elif max_queue_size < 1000:
                result['status'] = 'PASS'
                result['details'].append("⚠ 数据库写入基本稳定，偶有积压")
                self.test_results['tests_passed'] += 1
            else:
                result['status'] = 'FAIL'
                result['details'].append("✗ 数据库写入存在严重积压")
                self.test_results['tests_failed'] += 1
            
        except Exception as e:
            result['status'] = 'ERROR'
            result['details'].append(f"测试异常: {str(e)}")
            self.test_results['tests_failed'] += 1
            self.logger.error(f"测试异常: {e}")
        
        self.test_results['details'].append(result)
        self._print_test_result(result)
        return result
    
    def test_health_monitoring(self, duration=30):
        """测试4: 健康监控功能测试
        
        Args:
            duration: 测试持续时间（秒）
        """
        test_name = "健康监控功能测试"
        self.logger.info(f"\n{'=' * 60}")
        self.logger.info(f"测试4: {test_name} (持续{duration}秒)")
        self.logger.info(f"{'=' * 60}")
        
        result = {
            'test_name': test_name,
            'status': 'PASS',
            'details': [],
            'metrics': {}
        }
        
        try:
            # 启动健康监控
            self.health_monitor.start_monitoring()
            self.logger.info("健康监控已启动")
            
            # 等待监控运行
            time.sleep(duration)
            
            # 获取健康摘要
            health_summary = self.health_monitor.get_system_health_summary()
            
            # 生成诊断报告
            diagnostic_report = self.health_monitor.generate_diagnostic_report()
            
            result['metrics'] = {
                'total_devices': health_summary['total_devices'],
                'connected_devices': health_summary['connected_devices'],
                'connection_rate': f"{health_summary['connection_rate'] * 100:.1f}%",
                'overall_health': health_summary['overall_health'].value,
                'active_alerts': health_summary['active_alerts']
            }
            
            result['details'].append(f"监控设备数: {health_summary['total_devices']}")
            result['details'].append(f"已连接设备: {health_summary['connected_devices']}")
            result['details'].append(f"整体健康: {health_summary['overall_health'].value}")
            result['details'].append(f"活跃警报: {health_summary['active_alerts']}")
            
            # 导出诊断报告
            report_exported = self.health_monitor.export_diagnostic_report()
            if report_exported:
                result['details'].append("✓ 诊断报告已导出")
            
            # 判断测试结果
            result['status'] = 'PASS'
            result['details'].append("✓ 健康监控功能正常")
            self.test_results['tests_passed'] += 1
            
        except Exception as e:
            result['status'] = 'ERROR'
            result['details'].append(f"测试异常: {str(e)}")
            self.test_results['tests_failed'] += 1
            self.logger.error(f"测试异常: {e}")
        
        self.test_results['details'].append(result)
        self._print_test_result(result)
        return result
    
    def _print_test_result(self, result):
        """打印测试结果"""
        status_symbol = {
            'PASS': '✓',
            'FAIL': '✗',
            'ERROR': '⚠'
        }
        
        self.logger.info(f"\n{'-' * 60}")
        self.logger.info(f"测试: {result['test_name']}")
        self.logger.info(f"状态: {status_symbol.get(result['status'], '?')} {result['status']}")
        self.logger.info(f"指标:")
        for key, value in result['metrics'].items():
            self.logger.info(f"  {key}: {value}")
        self.logger.info(f"详情:")
        for detail in result['details']:
            self.logger.info(f"  {detail}")
        self.logger.info(f"{'-' * 60}")
    
    def run_all_tests(self):
        """运行所有测试"""
        self.logger.info("\n" + "=" * 60)
        self.logger.info("通讯稳定性和重连机制测试套件")
        self.logger.info("=" * 60)
        
        self.test_results['start_time'] = datetime.now().isoformat()
        start_time = time.time()
        
        # 设置测试环境
        if not self.setup():
            self.logger.error("测试环境初始化失败，终止测试")
            return
        
        try:
            # 执行测试
            self.test_reconnection_mechanism(duration=60)
            self.test_data_collection_stability(duration=60)
            self.test_database_write_stability(duration=30)
            self.test_health_monitoring(duration=30)
            
        finally:
            # 清理测试环境
            self.teardown()
        
        # 计算总测试时间
        self.test_results['end_time'] = datetime.now().isoformat()
        self.test_results['duration'] = time.time() - start_time
        
        # 生成测试报告
        self._generate_test_report()
    
    def _generate_test_report(self):
        """生成测试报告"""
        self.logger.info("\n" + "=" * 60)
        self.logger.info("测试报告")
        self.logger.info("=" * 60)
        
        total_tests = self.test_results['tests_passed'] + self.test_results['tests_failed']
        success_rate = (self.test_results['tests_passed'] / total_tests * 100) if total_tests > 0 else 0
        
        self.logger.info(f"测试开始时间: {self.test_results['start_time']}")
        self.logger.info(f"测试结束时间: {self.test_results['end_time']}")
        self.logger.info(f"测试总时长: {self.test_results['duration']:.1f}秒")
        self.logger.info(f"测试通过: {self.test_results['tests_passed']}/{total_tests}")
        self.logger.info(f"测试失败: {self.test_results['tests_failed']}/{total_tests}")
        self.logger.info(f"成功率: {success_rate:.1f}%")
        
        # 保存测试报告
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_path = PathManager.get_data_path(f"test_report_{timestamp}.json")
            
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(self.test_results, f, indent=4, ensure_ascii=False)
            
            self.logger.info(f"\n测试报告已保存: {report_path}")
            
        except Exception as e:
            self.logger.error(f"保存测试报告失败: {e}")
        
        self.logger.info("=" * 60)
        
        # 返回测试是否全部通过
        return self.test_results['tests_failed'] == 0


def main():
    """主函数"""
    test = CommunicationStabilityTest()
    all_passed = test.run_all_tests()
    
    # 返回退出码
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()

