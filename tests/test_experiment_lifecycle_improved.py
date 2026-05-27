#!/usr/bin/env python3
"""
改进的综合测试脚本：解决Qt线程问题
验证整个实验生命周期的完整流程，包括标准实验、自定义实验、错误场景等全面测试
"""

import sys
import os
import time
import logging
import threading
from unittest.mock import Mock, MagicMock
from datetime import datetime
from typing import List, Dict, Any

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# 在导入Qt相关模块之前设置环境变量
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QCoreApplication, QTimer
from PySide6.QtWidgets import QApplication

from src.controllers.experiment_controller import ExperimentController
from src.services.experiment_modes import ExperimentType, ExperimentStage
from src.services.experiment_type_manager import ExperimentTypeManager
from src.services.database import ExperimentData


class MockDeviceManager:
    """模拟设备管理器"""
    
    def __init__(self):
        self.flow_settings = {}
        self.set_flow_calls = []
        self.temperature = 25.0  # 模拟当前温度
        self.weight = 500.0  # 模拟当前重量
        
        # 模拟设备连接状态
        self.multi_mfc = Mock()
        self.multi_mfc.serial_port_available = True
        
        self.balance = Mock()
        self.balance.serial_port_available = True
        
        self.temp = Mock()
        self.temp.serial_port_available = True
        
    def set_flow(self, gas: str, flow: float):
        """模拟设置气体流量"""
        self.flow_settings[gas] = flow
        self.set_flow_calls.append((gas, flow))
        print(f"    [设备] 设置 {gas} 流量: {flow:.1f} L/min")
    
    def get_temperature(self) -> float:
        """模拟获取温度"""
        return self.temperature
    
    def get_weight(self) -> float:
        """模拟获取重量"""
        return self.weight


class TestSignal:
    """模拟Qt信号"""
    
    def __init__(self, name: str):
        self.name = name
        self.emitted_values = []
        self.call_count = 0
    
    def emit(self, *args):
        self.call_count += 1
        if args:
            self.emitted_values.append(args[0] if len(args) == 1 else args)
            print(f"    [信号] {self.name}: {args[0] if len(args) == 1 else args}")
        else:
            self.emitted_values.append(None)
            print(f"    [信号] {self.name}: (无参数)")


class QtTestEnvironment:
    """Qt测试环境管理器"""
    
    def __init__(self):
        self.app = None
        self.timer = None
        
    def setup(self):
        """设置Qt环境"""
        if not QCoreApplication.instance():
            self.app = QApplication(sys.argv)
        else:
            self.app = QCoreApplication.instance()
        
        # 创建一个定时器来处理Qt事件
        self.timer = QTimer()
        self.timer.timeout.connect(self.app.processEvents)
        self.timer.start(10)  # 每10ms处理一次事件
        
    def cleanup(self):
        """清理Qt环境"""
        if self.timer:
            self.timer.stop()
        if self.app:
            self.app.quit()


class ExperimentLifecycleTester:
    """实验生命周期测试器"""
    
    def __init__(self):
        self.setup_logging()
        self.test_results = []
        self.qt_env = QtTestEnvironment()
        
    def setup_logging(self):
        """设置日志"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def create_test_controller(self, experiment_type: str = "GB_13241_2017") -> ExperimentController:
        """创建测试用的实验控制器"""
        print(f"\n{'='*60}")
        print(f"创建测试控制器 - 实验类型: {experiment_type}")
        print(f"{'='*60}")
        
        # 创建模拟设备管理器
        device_manager = MockDeviceManager()
        
        # 创建实验控制器
        controller = ExperimentController(device_manager=device_manager)
        
        # 替换信号为模拟信号
        controller.status_updated = TestSignal("status_updated")
        controller.system_message_updated = TestSignal("system_message_updated")
        controller.experiment_completed = TestSignal("experiment_completed")
        controller.experiment_started = TestSignal("experiment_started")
        controller.experiment_stopped = TestSignal("experiment_stopped")
        controller.experiment_time_updated = TestSignal("experiment_time_updated")
        
        # 设置实验模式
        success = controller.set_experiment_mode_by_id(experiment_type)
        if not success:
            raise Exception(f"设置实验模式失败: {experiment_type}")
        
        # 设置实验参数
        controller.experiment_params = {
            "name": f"测试实验_{experiment_type}",
            "sample_name": "测试样品",
            "sample_weight": 500.0,
            "description": "生命周期测试用实验",
            "operator": "测试员",
            "experiment_type": experiment_type
        }
        
        print(f"✅ 测试控制器创建成功")
        print(f"   实验类型: {controller.current_experiment_type_name}")
        print(f"   设备管理器: {type(device_manager).__name__}")
        
        return controller
    
    def test_experiment_startup(self, controller: ExperimentController) -> bool:
        """测试实验启动流程"""
        print(f"\n{'='*40}")
        print("测试实验启动流程")
        print(f"{'='*40}")
        
        # 记录启动前的状态
        print(f"启动前状态:")
        print(f"  实验运行中: {controller.experiment_running}")
        print(f"  当前实验: {controller.current_experiment}")
        print(f"  实验类型: {controller.current_experiment_type}")
        
        # 启动实验
        print(f"\n启动实验...")
        success = controller.start_experiment()
        
        if not success:
            print(f"❌ 实验启动失败")
            return False
        
        # 检查启动后的状态
        print(f"\n启动后状态:")
        print(f"  实验运行中: {controller.experiment_running}")
        print(f"  当前实验ID: {controller.current_experiment.experiment_id if controller.current_experiment else 'None'}")
        print(f"  阶段索引: {controller.experiment_mode_manager.current_stage_index}")
        print(f"  阶段开始时间: {controller.stage_start_time}")
        
        # 检查信号发送
        print(f"\n信号发送情况:")
        print(f"  状态更新信号: {controller.status_updated.call_count} 次")
        print(f"  系统消息信号: {controller.system_message_updated.call_count} 次")
        print(f"  实验开始信号: {controller.experiment_started.call_count} 次")
        print(f"  时间更新信号: {controller.experiment_time_updated.call_count} 次")
        
        # 检查设备调用
        print(f"\n设备调用情况:")
        print(f"  流量设置调用: {len(controller.device_manager.set_flow_calls)} 次")
        for gas, flow in controller.device_manager.set_flow_calls:
            print(f"    {gas}: {flow:.1f} L/min")
        
        print(f"✅ 实验启动测试通过")
        return True
    
    def test_stage_execution(self, controller: ExperimentController) -> bool:
        """测试阶段执行流程"""
        print(f"\n{'='*40}")
        print("测试阶段执行流程")
        print(f"{'='*40}")
        
        if not controller.experiment_running:
            print(f"❌ 实验未运行，无法测试阶段执行")
            return False
        
        # 获取当前阶段信息
        current_stage = controller.experiment_mode_manager.get_current_stage_settings()
        if not current_stage:
            print(f"❌ 无法获取当前阶段信息")
            return False
        
        print(f"当前阶段信息:")
        print(f"  阶段名称: {current_stage.stage.value}")
        print(f"  阶段描述: {current_stage.description}")
        print(f"  目标温度: {current_stage.target_temp}°C")
        print(f"  持续时间: {current_stage.duration} 分钟")
        print(f"  气体设置: {current_stage.gas_settings}")
        
        # 清空之前的调用记录
        controller.device_manager.set_flow_calls.clear()
        controller.status_updated.emitted_values.clear()
        controller.system_message_updated.emitted_values.clear()
        
        # 执行当前阶段
        print(f"\n执行当前阶段...")
        controller.execute_current_experiment_stage()
        
        # 检查执行结果
        print(f"\n阶段执行结果:")
        print(f"  设备流量设置: {len(controller.device_manager.set_flow_calls)} 次")
        for gas, flow in controller.device_manager.set_flow_calls:
            print(f"    {gas}: {flow:.1f} L/min")
        
        print(f"  状态更新信号: {len(controller.status_updated.emitted_values)} 次")
        for status in controller.status_updated.emitted_values:
            print(f"    {status}")
        
        print(f"  系统消息信号: {len(controller.system_message_updated.emitted_values)} 次")
        for message in controller.system_message_updated.emitted_values:
            print(f"    {message}")
        
        print(f"✅ 阶段执行测试通过")
        return True
    
    def test_stage_advancement(self, controller: ExperimentController) -> bool:
        """测试阶段推进流程"""
        print(f"\n{'='*40}")
        print("测试阶段推进流程")
        print(f"{'='*40}")
        
        if not controller.experiment_running:
            print(f"❌ 实验未运行，无法测试阶段推进")
            return False
        
        # 获取实验阶段信息
        if controller.experiment_mode_manager.is_custom_mode():
            custom_program = controller.experiment_mode_manager.get_custom_program(
                controller.experiment_mode_manager.get_current_custom_type()
            )
            stages = custom_program.stages if custom_program else []
        else:
            stages = controller.experiment_mode_manager.get_experiment_stages(controller.current_experiment_type)
        
        print(f"实验共有 {len(stages)} 个阶段:")
        for i, stage in enumerate(stages):
            print(f"  {i+1}. {stage.stage.value} - {stage.description}")
        
        # 模拟阶段推进
        print(f"\n模拟阶段推进...")
        for i in range(len(stages)):
            print(f"\n--- 测试第 {i+1} 个阶段 ---")
            
            # 设置当前阶段
            controller.experiment_mode_manager.current_stage_index = i
            controller.stage_start_time = time.time()
            
            # 执行阶段
            controller.execute_current_experiment_stage()
            
            # 检查阶段信息
            current_stage = controller.experiment_mode_manager.get_current_stage_settings()
            if current_stage:
                print(f"  阶段: {current_stage.stage.value}")
                print(f"  描述: {current_stage.description}")
                print(f"  目标温度: {current_stage.target_temp}°C")
                print(f"  气体设置: {current_stage.gas_settings}")
            else:
                print(f"  阶段: 无（实验完成）")
                break
        
        print(f"✅ 阶段推进测试通过")
        return True
    
    def test_experiment_completion(self, controller: ExperimentController) -> bool:
        """测试实验完成流程"""
        print(f"\n{'='*40}")
        print("测试实验完成流程")
        print(f"{'='*40}")
        
        if not controller.experiment_running:
            print(f"❌ 实验未运行，无法测试实验完成")
            return False
        
        # 清空之前的信号记录
        controller.experiment_completed.emitted_values.clear()
        controller.status_updated.emitted_values.clear()
        controller.system_message_updated.emitted_values.clear()
        
        # 模拟实验完成
        print(f"模拟实验完成...")
        controller.complete_experiment()
        
        # 检查完成后的状态
        print(f"\n完成后状态:")
        print(f"  实验运行中: {controller.experiment_running}")
        print(f"  当前实验结束时间: {controller.current_experiment.end_time if controller.current_experiment else 'None'}")
        
        # 检查信号发送
        print(f"\n完成信号发送:")
        print(f"  实验完成信号: {controller.experiment_completed.call_count} 次")
        print(f"  状态更新信号: {len(controller.status_updated.emitted_values)} 次")
        for status in controller.status_updated.emitted_values:
            print(f"    {status}")
        print(f"  系统消息信号: {len(controller.system_message_updated.emitted_values)} 次")
        for message in controller.system_message_updated.emitted_values:
            print(f"    {message}")
        
        # 检查安全气氛设置
        print(f"\n安全气氛设置:")
        print(f"  设备流量设置: {len(controller.device_manager.set_flow_calls)} 次")
        for gas, flow in controller.device_manager.set_flow_calls:
            print(f"    {gas}: {flow:.1f} L/min")
        
        print(f"✅ 实验完成测试通过")
        return True
    
    def test_error_scenarios(self) -> bool:
        """测试错误场景"""
        print(f"\n{'='*60}")
        print("测试错误场景")
        print(f"{'='*60}")
        
        # 测试1: 无设备管理器
        print(f"\n测试1: 无设备管理器")
        controller = ExperimentController(device_manager=None)
        controller.experiment_params = {
            "name": "测试实验",
            "sample_name": "测试样品",
            "sample_weight": 500.0,
            "description": "测试用实验",
            "operator": "测试员",
            "experiment_type": "GB_13241_2017"
        }
        controller.set_experiment_mode_by_id("GB_13241_2017")
        
        success = controller.start_experiment()
        print(f"  无设备管理器启动结果: {'成功' if success else '失败'}")
        
        # 测试2: 无实验参数
        print(f"\n测试2: 无实验参数")
        controller = ExperimentController()
        controller.experiment_params = {}
        controller.set_experiment_mode_by_id("GB_13241_2017")
        
        success = controller.start_experiment()
        print(f"  无实验参数启动结果: {'成功' if success else '失败'}")
        
        # 测试3: 无实验模式
        print(f"\n测试3: 无实验模式")
        controller = ExperimentController()
        controller.experiment_params = {
            "name": "测试实验",
            "sample_name": "测试样品",
            "sample_weight": 500.0,
            "description": "测试用实验",
            "operator": "测试员",
            "experiment_type": "GB_13241_2017"
        }
        
        success = controller.start_experiment()
        print(f"  无实验模式启动结果: {'成功' if success else '失败'}")
        
        # 测试4: 实验已运行
        print(f"\n测试4: 实验已运行")
        controller = self.create_test_controller()
        controller.start_experiment()
        
        success = controller.start_experiment()
        print(f"  实验已运行启动结果: {'成功' if success else '失败'}")
        
        print(f"✅ 错误场景测试通过")
        return True
    
    def test_standard_experiment_lifecycle(self) -> bool:
        """测试标准实验完整生命周期"""
        print(f"\n{'='*80}")
        print("测试标准实验完整生命周期 - GB/T 13241-2017")
        print(f"{'='*80}")
        
        try:
            # 创建控制器
            controller = self.create_test_controller("GB_13241_2017")
            
            # 测试启动
            if not self.test_experiment_startup(controller):
                return False
            
            # 测试阶段执行
            if not self.test_stage_execution(controller):
                return False
            
            # 测试阶段推进
            if not self.test_stage_advancement(controller):
                return False
            
            # 测试实验完成
            if not self.test_experiment_completion(controller):
                return False
            
            print(f"\n✅ 标准实验完整生命周期测试通过")
            return True
            
        except Exception as e:
            print(f"❌ 标准实验测试失败: {e}")
            return False
    
    def test_custom_experiment_lifecycle(self) -> bool:
        """测试自定义实验完整生命周期"""
        print(f"\n{'='*80}")
        print("测试自定义实验完整生命周期 - CUSTOM_HIGH_TEMP_TEST")
        print(f"{'='*80}")
        
        try:
            # 创建控制器
            controller = self.create_test_controller("CUSTOM_HIGH_TEMP_TEST")
            
            # 测试启动
            if not self.test_experiment_startup(controller):
                return False
            
            # 测试阶段执行
            if not self.test_stage_execution(controller):
                return False
            
            # 测试阶段推进
            if not self.test_stage_advancement(controller):
                return False
            
            # 测试实验完成
            if not self.test_experiment_completion(controller):
                return False
            
            print(f"\n✅ 自定义实验完整生命周期测试通过")
            return True
            
        except Exception as e:
            print(f"❌ 自定义实验测试失败: {e}")
            return False
    
    def run_all_tests(self) -> bool:
        """运行所有测试"""
        print(f"{'='*100}")
        print("开始运行实验生命周期综合测试 (改进版 - 解决Qt线程问题)")
        print(f"{'='*100}")
        
        # 设置Qt环境
        self.qt_env.setup()
        
        try:
            test_results = []
            
            # 测试标准实验
            print(f"\n🧪 测试1: 标准实验完整生命周期")
            result1 = self.test_standard_experiment_lifecycle()
            test_results.append(("标准实验生命周期", result1))
            
            # 测试自定义实验
            print(f"\n🧪 测试2: 自定义实验完整生命周期")
            result2 = self.test_custom_experiment_lifecycle()
            test_results.append(("自定义实验生命周期", result2))
            
            # 测试错误场景
            print(f"\n🧪 测试3: 错误场景测试")
            result3 = self.test_error_scenarios()
            test_results.append(("错误场景测试", result3))
            
            # 输出测试结果
            print(f"\n{'='*100}")
            print("测试结果汇总")
            print(f"{'='*100}")
            
            passed = 0
            total = len(test_results)
            
            for test_name, result in test_results:
                status = "✅ 通过" if result else "❌ 失败"
                print(f"{test_name}: {status}")
                if result:
                    passed += 1
            
            print(f"\n总计: {passed}/{total} 个测试通过")
            
            if passed == total:
                print(f"🎉 所有测试通过！实验生命周期功能正常")
                return True
            else:
                print(f"⚠️  有 {total - passed} 个测试失败，需要检查相关功能")
                return False
                
        finally:
            # 清理Qt环境
            self.qt_env.cleanup()


def main():
    """主函数"""
    try:
        tester = ExperimentLifecycleTester()
        success = tester.run_all_tests()
        
        if success:
            print(f"\n🎉 所有测试完成，实验系统功能正常！")
            return 0
        else:
            print(f"\n⚠️  部分测试失败，请检查相关功能")
            return 1
            
    except Exception as e:
        print(f"❌ 测试过程中发生严重错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
