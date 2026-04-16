#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MFC客户端压力测试脚本
测试多台质量流量控制器的通信稳定性、性能和错误处理能力
"""

import sys
import os
import time
import threading
import statistics
from datetime import datetime
from typing import Dict, List, Any
import json

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.device_clients.multi_mfc_client import MultiMFCClient
from src.utils.logger import get_logger


class MFCPressureTester:
    """MFC压力测试器"""
    
    def __init__(self, config_file: str = None):
        self.logger = get_logger(__name__)
        self.config = self._load_config(config_file)
        self.mfc_client = None
        self.test_results = {
            'read_tests': [],
            'write_tests': [],
            'concurrent_tests': [],
            'error_tests': []
        }
        self.running = False
        
    def _load_config(self, config_file: str = None) -> Dict[str, Any]:
        """加载测试配置"""
        if config_file and os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        # 默认测试配置
        return {
            "port": "COM10",
            "baudrate": 9600,
            "parity": "E",
            "stopbits": 1,
            "bytesize": 8,
            "timeout": 1.5,
            "SLAVE_ADDRESS_MFC": {
                "H2": 1,
                "N2": 2,
                "CO2": 3,
                "CO": 4
            },
            "FLOW_SCALING": {
                "H2": 0.1,
                "N2": 1.0,
                "CO2": 0.1,
                "CO": 0.1
            }
        }
    
    def setup_mfc_client(self) -> bool:
        """初始化MFC客户端"""
        try:
            self.mfc_client = MultiMFCClient("MFC_Test", self.config)
            self.mfc_client.start()
            self.logger.info("MFC客户端初始化成功")
            return True
        except Exception as e:
            self.logger.error(f"MFC客户端初始化失败: {e}")
            return False
    
    def teardown_mfc_client(self):
        """清理MFC客户端"""
        if self.mfc_client:
            try:
                self.mfc_client.stop()
                self.logger.info("MFC客户端已停止")
            except Exception as e:
                self.logger.error(f"停止MFC客户端时出错: {e}")
    
    def test_single_read_operation(self, gas: str, iterations: int = 100) -> Dict[str, Any]:
        """测试单个气体读取操作"""
        self.logger.info(f"开始测试 {gas} 读取操作 ({iterations} 次)")
        
        results = {
            'gas': gas,
            'iterations': iterations,
            'success_count': 0,
            'error_count': 0,
            'response_times': [],
            'errors': [],
            'start_time': time.time()
        }
        
        for i in range(iterations):
            start_time = time.time()
            try:
                result = self.mfc_client.read_one(gas)
                response_time = time.time() - start_time
                results['response_times'].append(response_time)
                
                if result and not any(result.get(f"{key}_error") for key in ['PV', 'SV']):
                    results['success_count'] += 1
                else:
                    results['error_count'] += 1
                    error_msg = f"读取失败: {result}"
                    results['errors'].append(error_msg)
                    self.logger.warning(f"第 {i+1} 次读取失败: {error_msg}")
                
            except Exception as e:
                response_time = time.time() - start_time
                results['response_times'].append(response_time)
                results['error_count'] += 1
                error_msg = f"异常: {str(e)}"
                results['errors'].append(error_msg)
                self.logger.error(f"第 {i+1} 次读取异常: {error_msg}")
            
            # 短暂延迟避免过快请求
            time.sleep(0.01)
        
        results['end_time'] = time.time()
        results['total_time'] = results['end_time'] - results['start_time']
        results['avg_response_time'] = statistics.mean(results['response_times']) if results['response_times'] else 0
        results['success_rate'] = results['success_count'] / iterations * 100
        
        self.logger.info(f"{gas} 读取测试完成: 成功率 {results['success_rate']:.1f}%, 平均响应时间 {results['avg_response_time']:.3f}s")
        return results
    
    def test_single_write_operation(self, gas: str, iterations: int = 50) -> Dict[str, Any]:
        """测试单个气体写入操作"""
        self.logger.info(f"开始测试 {gas} 写入操作 ({iterations} 次)")
        
        results = {
            'gas': gas,
            'iterations': iterations,
            'success_count': 0,
            'error_count': 0,
            'response_times': [],
            'errors': [],
            'start_time': time.time()
        }
        
        # 测试不同的流量值
        test_values = [0.5, 1.0, 2.0, 5.0, 10.0, 0.0]
        
        for i in range(iterations):
            test_value = test_values[i % len(test_values)]
            start_time = time.time()
            
            try:
                result = self.mfc_client.set_sv(gas, test_value, verify=False)
                response_time = time.time() - start_time
                results['response_times'].append(response_time)
                
                if result and not result.get('error'):
                    results['success_count'] += 1
                else:
                    results['error_count'] += 1
                    error_msg = f"写入失败: {result}"
                    results['errors'].append(error_msg)
                    self.logger.warning(f"第 {i+1} 次写入失败: {error_msg}")
                
            except Exception as e:
                response_time = time.time() - start_time
                results['response_times'].append(response_time)
                results['error_count'] += 1
                error_msg = f"异常: {str(e)}"
                results['errors'].append(error_msg)
                self.logger.error(f"第 {i+1} 次写入异常: {error_msg}")
            
            # 短暂延迟避免过快请求
            time.sleep(0.05)
        
        results['end_time'] = time.time()
        results['total_time'] = results['end_time'] - results['start_time']
        results['avg_response_time'] = statistics.mean(results['response_times']) if results['response_times'] else 0
        results['success_rate'] = results['success_count'] / iterations * 100
        
        self.logger.info(f"{gas} 写入测试完成: 成功率 {results['success_rate']:.1f}%, 平均响应时间 {results['avg_response_time']:.3f}s")
        return results
    
    def test_concurrent_operations(self, duration_seconds: int = 60) -> Dict[str, Any]:
        """测试并发操作"""
        self.logger.info(f"开始并发操作测试 ({duration_seconds} 秒)")
        
        results = {
            'duration': duration_seconds,
            'total_operations': 0,
            'success_operations': 0,
            'error_operations': 0,
            'gases': list(self.config['SLAVE_ADDRESS_MFC'].keys()),
            'start_time': time.time(),
            'thread_results': []
        }
        
        self.running = True
        threads = []
        
        # 为每个气体创建读写线程
        for gas in results['gases']:
            thread = threading.Thread(target=self._concurrent_worker, args=(gas, results))
            threads.append(thread)
            thread.start()
        
        # 等待指定时间
        time.sleep(duration_seconds)
        self.running = False
        
        # 等待所有线程结束
        for thread in threads:
            thread.join(timeout=5)
        
        results['end_time'] = time.time()
        results['total_time'] = results['end_time'] - results['start_time']
        results['success_rate'] = results['success_operations'] / results['total_operations'] * 100 if results['total_operations'] > 0 else 0
        results['operations_per_second'] = results['total_operations'] / results['total_time']
        
        self.logger.info(f"并发测试完成: 总操作 {results['total_operations']}, 成功率 {results['success_rate']:.1f}%, 操作/秒 {results['operations_per_second']:.1f}")
        return results
    
    def _concurrent_worker(self, gas: str, results: Dict[str, Any]):
        """并发工作线程"""
        thread_results = {
            'gas': gas,
            'operations': 0,
            'successes': 0,
            'errors': 0,
            'response_times': []
        }
        
        while self.running:
            try:
                # 随机选择读取或写入操作
                import random
                if random.random() < 0.7:  # 70% 概率读取
                    start_time = time.time()
                    result = self.mfc_client.read_one(gas)
                    response_time = time.time() - start_time
                else:  # 30% 概率写入
                    test_value = random.uniform(0.5, 10.0)
                    start_time = time.time()
                    result = self.mfc_client.set_sv(gas, test_value, verify=False)
                    response_time = time.time() - start_time
                
                thread_results['operations'] += 1
                thread_results['response_times'].append(response_time)
                
                if result and not any(result.get(f"{key}_error", False) for key in ['PV', 'SV']) and not result.get('error'):
                    thread_results['successes'] += 1
                else:
                    thread_results['errors'] += 1
                
                # 短暂延迟
                time.sleep(0.1)
                
            except Exception as e:
                thread_results['operations'] += 1
                thread_results['errors'] += 1
                self.logger.error(f"并发操作异常 ({gas}): {e}")
                time.sleep(0.1)
        
        results['thread_results'].append(thread_results)
        results['total_operations'] += thread_results['operations']
        results['success_operations'] += thread_results['successes']
        results['error_operations'] += thread_results['errors']
    
    def test_error_recovery(self) -> Dict[str, Any]:
        """测试错误恢复能力"""
        self.logger.info("开始错误恢复测试")
        
        results = {
            'test_cases': [],
            'start_time': time.time()
        }
        
        # 测试用例1: 无效气体名称
        try:
            result = self.mfc_client.read_one("INVALID_GAS")
            results['test_cases'].append({
                'name': '无效气体名称',
                'success': False,
                'result': str(result)
            })
        except Exception as e:
            results['test_cases'].append({
                'name': '无效气体名称',
                'success': True,  # 正确抛出异常
                'result': str(e)
            })
        
        # 测试用例2: 无效流量值
        try:
            result = self.mfc_client.set_sv("N2", -100.0)  # 负值
            results['test_cases'].append({
                'name': '负流量值',
                'success': True,
                'result': str(result)
            })
        except Exception as e:
            results['test_cases'].append({
                'name': '负流量值',
                'success': False,
                'result': str(e)
            })
        
        # 测试用例3: 极大流量值
        try:
            result = self.mfc_client.set_sv("N2", 999999.0)  # 极大值
            results['test_cases'].append({
                'name': '极大流量值',
                'success': True,
                'result': str(result)
            })
        except Exception as e:
            results['test_cases'].append({
                'name': '极大流量值',
                'success': False,
                'result': str(e)
            })
        
        results['end_time'] = time.time()
        results['total_time'] = results['end_time'] - results['start_time']
        
        self.logger.info(f"错误恢复测试完成: {len(results['test_cases'])} 个测试用例")
        return results
    
    def run_comprehensive_test(self, test_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """运行综合测试"""
        if test_config is None:
            test_config = {
                'read_iterations': 50,
                'write_iterations': 25,
                'concurrent_duration': 30,
                'gases': ['N2', 'CO', 'CO2', 'H2']
            }
        
        self.logger.info("开始MFC综合压力测试")
        overall_start = time.time()
        
        # 初始化MFC客户端
        if not self.setup_mfc_client():
            return {'error': 'MFC客户端初始化失败'}
        
        try:
            # 1. 读取操作测试
            self.logger.info("=== 阶段1: 读取操作测试 ===")
            for gas in test_config['gases']:
                result = self.test_single_read_operation(gas, test_config['read_iterations'])
                self.test_results['read_tests'].append(result)
            
            # 2. 写入操作测试
            self.logger.info("=== 阶段2: 写入操作测试 ===")
            for gas in test_config['gases']:
                result = self.test_single_write_operation(gas, test_config['write_iterations'])
                self.test_results['write_tests'].append(result)
            
            # 3. 并发操作测试
            self.logger.info("=== 阶段3: 并发操作测试 ===")
            concurrent_result = self.test_concurrent_operations(test_config['concurrent_duration'])
            self.test_results['concurrent_tests'].append(concurrent_result)
            
            # 4. 错误恢复测试
            self.logger.info("=== 阶段4: 错误恢复测试 ===")
            error_result = self.test_error_recovery()
            self.test_results['error_tests'].append(error_result)
            
        finally:
            # 清理
            self.teardown_mfc_client()
        
        overall_end = time.time()
        self.test_results['overall'] = {
            'total_time': overall_end - overall_start,
            'start_time': overall_start,
            'end_time': overall_end,
            'test_config': test_config
        }
        
        self.logger.info(f"MFC综合压力测试完成，总耗时: {overall_end - overall_start:.1f}秒")
        return self.test_results
    
    def generate_report(self, output_file: str = None) -> str:
        """生成测试报告"""
        if not self.test_results:
            return "没有测试结果可生成报告"
        
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("MFC客户端压力测试报告")
        report_lines.append("=" * 80)
        report_lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("")
        
        # 总体统计
        if 'overall' in self.test_results:
            overall = self.test_results['overall']
            report_lines.append("总体统计:")
            report_lines.append(f"  总测试时间: {overall['total_time']:.1f} 秒")
            report_lines.append(f"  测试配置: {overall['test_config']}")
            report_lines.append("")
        
        # 读取测试结果
        if self.test_results['read_tests']:
            report_lines.append("读取操作测试结果:")
            for result in self.test_results['read_tests']:
                report_lines.append(f"  {result['gas']}: 成功率 {result['success_rate']:.1f}%, "
                                  f"平均响应时间 {result['avg_response_time']:.3f}s, "
                                  f"成功 {result['success_count']}/{result['iterations']}")
            report_lines.append("")
        
        # 写入测试结果
        if self.test_results['write_tests']:
            report_lines.append("写入操作测试结果:")
            for result in self.test_results['write_tests']:
                report_lines.append(f"  {result['gas']}: 成功率 {result['success_rate']:.1f}%, "
                                  f"平均响应时间 {result['avg_response_time']:.3f}s, "
                                  f"成功 {result['success_count']}/{result['iterations']}")
            report_lines.append("")
        
        # 并发测试结果
        if self.test_results['concurrent_tests']:
            report_lines.append("并发操作测试结果:")
            for result in self.test_results['concurrent_tests']:
                report_lines.append(f"  总操作数: {result['total_operations']}")
                report_lines.append(f"  成功率: {result['success_rate']:.1f}%")
                report_lines.append(f"  操作/秒: {result['operations_per_second']:.1f}")
                report_lines.append(f"  测试时长: {result['total_time']:.1f} 秒")
            report_lines.append("")
        
        # 错误恢复测试结果
        if self.test_results['error_tests']:
            report_lines.append("错误恢复测试结果:")
            for result in self.test_results['error_tests']:
                for test_case in result['test_cases']:
                    status = "通过" if test_case['success'] else "失败"
                    report_lines.append(f"  {test_case['name']}: {status}")
            report_lines.append("")
        
        report_content = "\n".join(report_lines)
        
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report_content)
            self.logger.info(f"测试报告已保存到: {output_file}")
        
        return report_content


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='MFC客户端压力测试')
    parser.add_argument('--config', type=str, help='配置文件路径')
    parser.add_argument('--read-iterations', type=int, default=50, help='读取操作测试次数')
    parser.add_argument('--write-iterations', type=int, default=25, help='写入操作测试次数')
    parser.add_argument('--concurrent-duration', type=int, default=30, help='并发测试持续时间(秒)')
    parser.add_argument('--gases', nargs='+', default=['N2', 'CO', 'CO2', 'H2'], help='测试的气体列表')
    parser.add_argument('--output', type=str, help='测试报告输出文件')
    
    args = parser.parse_args()
    
    # 创建测试器
    tester = MFCPressureTester(args.config)
    
    # 配置测试参数
    test_config = {
        'read_iterations': args.read_iterations,
        'write_iterations': args.write_iterations,
        'concurrent_duration': args.concurrent_duration,
        'gases': args.gases
    }
    
    # 运行测试
    results = tester.run_comprehensive_test(test_config)
    
    # 生成报告
    report = tester.generate_report(args.output)
    print(report)
    
    # 检查是否有严重错误
    if 'error' in results:
        print(f"测试失败: {results['error']}")
        sys.exit(1)
    
    # 检查整体成功率
    read_success_rate = 0
    write_success_rate = 0
    
    if results['read_tests']:
        read_success_rate = statistics.mean([r['success_rate'] for r in results['read_tests']])
    
    if results['write_tests']:
        write_success_rate = statistics.mean([r['success_rate'] for r in results['write_tests']])
    
    if read_success_rate < 80 or write_success_rate < 80:
        print("警告: 成功率低于80%，请检查设备连接和配置")
        sys.exit(1)
    else:
        print("测试通过: 所有测试成功率均超过80%")


if __name__ == '__main__':
    main()
