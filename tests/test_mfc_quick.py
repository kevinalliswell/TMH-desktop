#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MFC客户端快速测试脚本
用于日常快速验证MFC通信是否正常
优化版本 - 支持多种配置源、更好的错误处理和测试统计
"""

import sys
import os
import time
import json
import argparse
from typing import Dict, Any, List
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.device_clients.multi_mfc_client import MultiMFCClient
from src.utils.logger import get_logger


class MFCQuickTester:
    """MFC快速测试器 - 优化版本"""
    
    def __init__(self, verbose: bool = False):
        self.logger = get_logger(__name__)
        self.mfc_client = None
        self.verbose = verbose
        self.test_stats = {
            'total_tests': 0,
            'passed_tests': 0,
            'failed_tests': 0,
            'start_time': None,
            'end_time': None,
            'test_results': []
        }
        
    def load_config(self, config_file: str = None) -> Dict[str, Any]:
        """加载配置文件 - 支持多种配置源"""
        config_sources = []
        
        # 1. 命令行指定的配置文件
        if config_file and os.path.exists(config_file):
            config_sources.append(("命令行指定", config_file))
        
        # 2. 默认配置文件
        default_configs = [
            "../configs/comm_config.json",
            "test_config.json",
            "../tests/test_config.json"
        ]
        
        for config_path in default_configs:
            if os.path.exists(config_path):
                config_sources.append(("默认配置", config_path))
        
        # 3. 环境变量配置
        env_config = os.getenv('MFC_TEST_CONFIG')
        if env_config and os.path.exists(env_config):
            config_sources.append(("环境变量", env_config))
        
        # 尝试加载配置
        for source_name, config_path in config_sources:
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # 尝试从不同位置获取MFC配置
                mfc_config = None
                if "COM_RS485_MFC" in config:
                    mfc_config = config["COM_RS485_MFC"]
                elif "port" in config:  # 直接是MFC配置
                    mfc_config = config
                
                if mfc_config:
                    self.logger.info(f"成功加载配置: {source_name} - {config_path}")
                    return mfc_config
                    
            except Exception as e:
                self.logger.warning(f"加载配置失败 {source_name} - {config_path}: {e}")
                continue
        
        # 如果所有配置都失败，返回默认配置
        self.logger.warning("所有配置文件加载失败，使用默认配置")
        return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "port": "COM10",
            "baudrate": 9600,
            "parity": "E",
            "stopbits": 1,
            "bytesize": 8,
            "timeout": 1.5,
            "SLAVE_ADDRESS_MFC": {"H2": 1, "N2": 2, "CO2": 3, "CO": 4},
            "FLOW_SCALING": {"H2": 0.1, "N2": 1.0, "CO2": 0.1, "CO": 0.1}
        }
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """验证配置完整性"""
        required_keys = ["port", "baudrate", "SLAVE_ADDRESS_MFC", "FLOW_SCALING"]
        missing_keys = [key for key in required_keys if key not in config]
        
        if missing_keys:
            self.logger.error(f"配置缺少必要字段: {missing_keys}")
            return False
        
        # 验证气体地址配置
        if not isinstance(config["SLAVE_ADDRESS_MFC"], dict) or not config["SLAVE_ADDRESS_MFC"]:
            self.logger.error("SLAVE_ADDRESS_MFC 配置无效")
            return False
        
        # 验证流量缩放配置
        if not isinstance(config["FLOW_SCALING"], dict) or not config["FLOW_SCALING"]:
            self.logger.error("FLOW_SCALING 配置无效")
            return False
        
        self.logger.info(f"配置验证通过: {len(config['SLAVE_ADDRESS_MFC'])} 个气体配置")
        return True
    
    def setup_mfc_client(self, config: dict) -> bool:
        """初始化MFC客户端"""
        try:
            self.mfc_client = MultiMFCClient("MFC_QuickTest", config)
            self.mfc_client.start()
            self.logger.info("MFC客户端初始化成功")
            return True
        except Exception as e:
            self.logger.error(f"MFC客户端初始化失败: {e}")
            return False
    
    def _record_test_result(self, test_name: str, success: bool, duration: float = 0, details: str = ""):
        """记录测试结果"""
        self.test_stats['total_tests'] += 1
        if success:
            self.test_stats['passed_tests'] += 1
        else:
            self.test_stats['failed_tests'] += 1
        
        result = {
            'test_name': test_name,
            'success': success,
            'duration': duration,
            'details': details,
            'timestamp': datetime.now().isoformat()
        }
        self.test_stats['test_results'].append(result)
        
        if self.verbose or not success:
            status = "✅" if success else "❌"
            self.logger.info(f"{status} {test_name}: {details} ({duration:.2f}s)")
    
    def _run_test_with_timeout(self, test_func, test_name: str, timeout: float = 30.0, *args, **kwargs) -> bool:
        """运行测试并记录结果"""
        start_time = time.time()
        try:
            result = test_func(*args, **kwargs)
            duration = time.time() - start_time
            self._record_test_result(test_name, result, duration, "测试完成")
            return result
        except Exception as e:
            duration = time.time() - start_time
            self._record_test_result(test_name, False, duration, f"异常: {str(e)}")
            return False
    
    def test_connection(self) -> bool:
        """测试连接"""
        if not self.mfc_client:
            self.logger.error("MFC客户端未初始化")
            return False
        
        try:
            # 测试读取所有气体
            result = self.mfc_client.read_all()
            if result and 'values' in result:
                success_count = 0
                total_gases = len(result['values'])
                
                for gas, data in result['values'].items():
                    if 'error' in data:
                        self.logger.warning(f"{gas}: {data['error']}")
                    else:
                        pv = data.get('PV', 'N/A')
                        sv = data.get('SV', 'N/A')
                        self.logger.info(f"{gas}: PV={pv}, SV={sv}")
                        success_count += 1
                
                success_rate = success_count / total_gases * 100 if total_gases > 0 else 0
                self.logger.info(f"连接测试完成: {success_count}/{total_gases} 气体通信正常 ({success_rate:.1f}%)")
                return success_count > 0  # 至少有一个气体通信正常
            else:
                self.logger.error("连接测试失败: 无响应数据")
                return False
        except Exception as e:
            self.logger.error(f"连接测试异常: {e}")
            return False
    
    def test_read_operations(self, gas: str = "N2", iterations: int = 5) -> bool:
        """测试读取操作"""
        if gas not in self.mfc_client._gas_map:
            self.logger.error(f"未知气体: {gas}")
            return False
        
        success_count = 0
        read_times = []
        
        try:
            for i in range(iterations):
                start_time = time.time()
                result = self.mfc_client.read_one(gas)
                read_time = time.time() - start_time
                read_times.append(read_time)
                
                if result and not any(result.get(f"{key}_error") for key in ['PV', 'SV']):
                    pv = result.get('PV', 'N/A')
                    sv = result.get('SV', 'N/A')
                    self.logger.info(f"第 {i+1} 次读取成功: PV={pv}, SV={sv} ({read_time:.3f}s)")
                    success_count += 1
                else:
                    self.logger.error(f"第 {i+1} 次读取失败: {result}")
                
                if i < iterations - 1:  # 最后一次不需要等待
                    time.sleep(0.1)
            
            success_rate = success_count / iterations * 100
            avg_read_time = sum(read_times) / len(read_times) if read_times else 0
            self.logger.info(f"读取测试完成: {success_count}/{iterations} 成功 ({success_rate:.1f}%), 平均耗时: {avg_read_time:.3f}s")
            return success_count >= iterations * 0.8  # 80%成功率
        except Exception as e:
            self.logger.error(f"读取操作测试异常: {e}")
            return False
    
    def test_write_operations(self, gas: str = "N2") -> bool:
        """测试写入操作"""
        if gas not in self.mfc_client._gas_map:
            self.logger.error(f"未知气体: {gas}")
            return False
        
        # 根据气体类型选择合适的测试值
        test_values = self._get_test_values_for_gas(gas)
        success_count = 0
        write_times = []
        
        try:
            for i, value in enumerate(test_values):
                self.logger.info(f"设置 {gas} 流量为 {value} L/min...")
                start_time = time.time()
                result = self.mfc_client.set_sv(gas, value, verify=False)
                write_time = time.time() - start_time
                write_times.append(write_time)
                
                if result and not result.get('error'):
                    self.logger.info(f"第 {i+1} 次写入成功 ({write_time:.3f}s)")
                    success_count += 1
                else:
                    self.logger.error(f"第 {i+1} 次写入失败: {result}")
                
                if i < len(test_values) - 1:  # 最后一次不需要等待
                    time.sleep(0.2)
            
            success_rate = success_count / len(test_values) * 100
            avg_write_time = sum(write_times) / len(write_times) if write_times else 0
            self.logger.info(f"写入测试完成: {success_count}/{len(test_values)} 成功 ({success_rate:.1f}%), 平均耗时: {avg_write_time:.3f}s")
            return success_count >= len(test_values) * 0.8  # 80%成功率
        except Exception as e:
            self.logger.error(f"写入操作测试异常: {e}")
            return False
    
    def _get_test_values_for_gas(self, gas: str) -> List[float]:
        """根据气体类型获取合适的测试值"""
        # 根据流量缩放因子调整测试值
        scaling = self.mfc_client._flow_scaling.get(gas, 1.0)
        
        if scaling <= 0.1:  # 小流量气体
            return [0.1, 0.5, 1.0, 0.0]
        else:  # 正常流量气体
            return [1.0, 2.0, 0.5, 0.0]
    
    def test_all_gases(self) -> bool:
        """测试所有气体"""
        gases = list(self.mfc_client._gas_map.keys()) if self.mfc_client else []
        if not gases:
            self.logger.error("没有配置任何气体")
            return False
        
        success_count = 0
        gas_results = {}
        
        for gas in gases:
            self.logger.info(f"测试气体: {gas}")
            try:
                start_time = time.time()
                result = self.mfc_client.read_one(gas)
                read_time = time.time() - start_time
                
                if result and not any(result.get(f"{key}_error") for key in ['PV', 'SV']):
                    pv = result.get('PV', 'N/A')
                    sv = result.get('SV', 'N/A')
                    self.logger.info(f"{gas} 读取成功: PV={pv}, SV={sv} ({read_time:.3f}s)")
                    success_count += 1
                    gas_results[gas] = {'success': True, 'pv': pv, 'sv': sv, 'time': read_time}
                else:
                    self.logger.error(f"{gas} 读取失败: {result}")
                    gas_results[gas] = {'success': False, 'error': str(result), 'time': read_time}
            except Exception as e:
                self.logger.error(f"{gas} 读取异常: {e}")
                gas_results[gas] = {'success': False, 'error': str(e), 'time': 0}
        
        success_rate = success_count / len(gases) * 100 if gases else 0
        self.logger.info(f"所有气体测试完成: {success_count}/{len(gases)} 成功 ({success_rate:.1f}%)")
        
        # 记录详细结果
        if self.verbose:
            for gas, result in gas_results.items():
                status = "✅" if result['success'] else "❌"
                self.logger.info(f"  {status} {gas}: {result}")
        
        return success_rate >= 50  # 至少50%成功
    
    def run_quick_test(self, config_file: str = None, test_gas: str = "N2", 
                      read_iterations: int = 5, skip_write: bool = False) -> bool:
        """运行快速测试"""
        self.test_stats['start_time'] = datetime.now()
        self.logger.info("开始MFC快速测试")
        
        # 加载和验证配置
        config = self.load_config(config_file)
        if not self.validate_config(config):
            self.logger.error("配置验证失败")
            return False
        
        # 初始化MFC客户端
        if not self.setup_mfc_client(config):
            return False
        
        try:
            # 测试连接
            if not self._run_test_with_timeout(self.test_connection, "连接测试", 10.0):
                self.logger.error("连接测试失败，停止后续测试")
                return False
            
            # 测试读取操作
            if not self._run_test_with_timeout(self.test_read_operations, "读取操作测试", 30.0, test_gas, read_iterations):
                self.logger.warning("读取操作测试失败，但继续后续测试")
            
            # 测试写入操作（可选）
            if not skip_write:
                if not self._run_test_with_timeout(self.test_write_operations, "写入操作测试", 30.0, test_gas):
                    self.logger.warning("写入操作测试失败，但继续后续测试")
            else:
                self.logger.info("跳过写入操作测试")
            
            # 测试所有气体
            if not self._run_test_with_timeout(self.test_all_gases, "所有气体测试", 60.0):
                self.logger.warning("所有气体测试失败")
            
            # 生成测试报告
            self._generate_test_report()
            
            # 判断整体测试结果
            success_rate = self.test_stats['passed_tests'] / self.test_stats['total_tests'] * 100 if self.test_stats['total_tests'] > 0 else 0
            overall_success = success_rate >= 70  # 70%成功率
            
            if overall_success:
                self.logger.info("✅ MFC快速测试通过!")
            else:
                self.logger.error("❌ MFC快速测试失败!")
            
            return overall_success
            
        except Exception as e:
            self.logger.error(f"快速测试异常: {e}")
            return False
        finally:
            # 清理
            self.test_stats['end_time'] = datetime.now()
            if self.mfc_client:
                self.mfc_client.stop()
                self.logger.info("MFC客户端已停止")
    
    def _generate_test_report(self):
        """生成测试报告"""
        if not self.test_stats['test_results']:
            return
        
        duration = (self.test_stats['end_time'] - self.test_stats['start_time']).total_seconds() if self.test_stats['end_time'] else 0
        success_rate = self.test_stats['passed_tests'] / self.test_stats['total_tests'] * 100 if self.test_stats['total_tests'] > 0 else 0
        
        self.logger.info("=" * 50)
        self.logger.info("MFC快速测试报告")
        self.logger.info("=" * 50)
        self.logger.info(f"总测试数: {self.test_stats['total_tests']}")
        self.logger.info(f"通过测试: {self.test_stats['passed_tests']}")
        self.logger.info(f"失败测试: {self.test_stats['failed_tests']}")
        self.logger.info(f"成功率: {success_rate:.1f}%")
        self.logger.info(f"总耗时: {duration:.2f}秒")
        self.logger.info("-" * 50)
        
        for result in self.test_stats['test_results']:
            status = "✅" if result['success'] else "❌"
            self.logger.info(f"{status} {result['test_name']}: {result['details']} ({result['duration']:.2f}s)")
        
        self.logger.info("=" * 50)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='MFC客户端快速测试 - 优化版本')
    parser.add_argument('--config', type=str, help='配置文件路径')
    parser.add_argument('--gas', type=str, default="N2", help='测试的气体')
    parser.add_argument('--iterations', type=int, default=5, help='读取测试迭代次数')
    parser.add_argument('--skip-write', action='store_true', help='跳过写入操作测试')
    parser.add_argument('--verbose', '-v', action='store_true', help='详细输出')
    parser.add_argument('--timeout', type=float, default=30.0, help='单个测试超时时间(秒)')
    
    args = parser.parse_args()
    
    # 创建测试器
    tester = MFCQuickTester(verbose=args.verbose)
    
    # 运行测试
    success = tester.run_quick_test(
        config_file=args.config,
        test_gas=args.gas,
        read_iterations=args.iterations,
        skip_write=args.skip_write
    )
    
    if success:
        print("✅ MFC快速测试通过")
        sys.exit(0)
    else:
        print("❌ MFC快速测试失败")
        sys.exit(1)


if __name__ == '__main__':
    main()
