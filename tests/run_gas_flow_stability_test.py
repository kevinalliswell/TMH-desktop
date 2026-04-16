#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
气体流量稳定性测试运行器
提供简化的测试执行界面

使用示例:
    python run_gas_flow_stability_test.py --scenario quick_test
    python run_gas_flow_stability_test.py --scenario standard_test
    python run_gas_flow_stability_test.py --scenario extended_test
    python run_gas_flow_stability_test.py --mode comprehensive --duration 300
"""

import sys
import json
import argparse
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 需要在sys.path修改后导入
# pylint: disable=wrong-import-position
from tests.gas_flow_stability_test import GasFlowStabilityTester


def load_test_config(config_file: str = None) -> dict:
    """加载测试配置"""
    if config_file is None:
        config_file = Path(__file__).parent / "gas_flow_test_config.json"
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"配置文件不存在: {config_file}")
        return {}
    except json.JSONDecodeError as e:
        print(f"配置文件格式错误: {e}")
        return {}


def run_scenario_test(scenario_name: str, config: dict, no_device: bool = False):
    """运行预定义场景测试"""
    scenarios = config.get("test_scenarios", {})
    
    if scenario_name not in scenarios:
        print(f"未找到场景: {scenario_name}")
        print(f"可用场景: {list(scenarios.keys())}")
        return False
    
    scenario = scenarios[scenario_name]
    print(f"运行测试场景: {scenario_name}")
    print(f"描述: {scenario['description']}")
    print(f"持续时间: {scenario['duration']} 秒")
    print("-" * 50)
    
    # 创建测试器
    test_params = config.get("test_parameters", {})
    tester = GasFlowStabilityTester(
        test_duration=scenario["duration"],
        log_level="INFO"
    )
    
    # 应用测试参数
    if "stability_check_interval" in test_params:
        tester.stability_check_interval = test_params["stability_check_interval"]
    if "flow_tolerance" in test_params:
        tester.flow_tolerance = test_params["flow_tolerance"]
    
    # 初始化设备
    if not no_device:
        device_available = tester.initialize_device_manager()
        if not device_available:
            print("错误: 设备连接失败，请检查设备连接和配置")
            return False
    else:
        print("警告: 使用模拟模式运行测试，不会进行真实的设备通信测试")
    
    # 运行测试
    test_modes = scenario.get("test_modes", ["comprehensive"])
    success = True
    
    for mode in test_modes:
        print(f"\n执行测试模式: {mode}")
        
        if mode == "comprehensive":
            result = tester.run_comprehensive_test()
        elif mode == "endurance":
            result = tester.run_endurance_test()
        elif mode == "communication":
            result = tester.run_communication_stability_test(scenario["duration"])
        else:
            print(f"未知测试模式: {mode}")
            result = False
        
        if not result:
            success = False
            break
    
    if success:
        # 生成报告
        print("\n测试完成，生成报告...")
        report = tester.generate_report()
        
        # 检查告警阈值
        check_alerts(tester, config)
        
        # 保存报告
        report_file = tester.save_report(report)
        if report_file:
            print(f"报告已保存到: {report_file}")
        
        print("\n" + "="*60)
        print(report)
        
    return success


def check_alerts(tester: GasFlowStabilityTester, config: dict):
    """检查告警阈值"""
    thresholds = config.get("alert_thresholds", {})
    if not thresholds:
        return
    
    metrics = tester.calculate_stability_metrics()
    alerts = []
    
    for mode_key, metric in metrics.items():
        # 检查成功率
        if metric.success_rate < thresholds.get("success_rate_min", 95.0):
            alerts.append(f"❌ {mode_key}: 成功率过低 ({metric.success_rate:.1f}%)")
        
        # 检查响应时间
        if metric.avg_response_time > thresholds.get("response_time_max", 3.0):
            alerts.append(f"⚠️  {mode_key}: 响应时间过长 ({metric.avg_response_time:.3f}s)")
        
        # 检查流量精度
        if metric.flow_accuracy < thresholds.get("flow_accuracy_min", 98.0):
            alerts.append(f"❌ {mode_key}: 流量精度不足 ({metric.flow_accuracy:.1f}%)")
        
        # 检查流量稳定性
        if metric.flow_stability > thresholds.get("flow_stability_max", 2.0):
            alerts.append(f"⚠️  {mode_key}: 流量稳定性差 ({metric.flow_stability:.1f}%)")
    
    if alerts:
        print("\n🚨 告警信息:")
        for alert in alerts:
            print(f"  {alert}")
    else:
        print("\n✅ 所有指标均正常")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="气体流量稳定性测试运行器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  %(prog)s --scenario quick_test              # 运行快速测试
  %(prog)s --scenario standard_test           # 运行标准测试
  %(prog)s --scenario extended_test           # 运行扩展测试
  %(prog)s --mode comprehensive --duration 300  # 自定义综合测试
  %(prog)s --mode endurance --duration 600      # 自定义耐久测试
        """
    )
    
    # 场景测试选项
    parser.add_argument("--scenario", 
                       choices=["quick_test", "standard_test", "extended_test"],
                       help="选择预定义的测试场景")
    
    # 自定义测试选项
    parser.add_argument("--mode", choices=["comprehensive", "endurance", "communication"], 
                       help="自定义测试模式")
    parser.add_argument("--duration", type=int, 
                       help="自定义测试持续时间（秒）")
    
    # 通用选项
    parser.add_argument("--config", 
                       help="指定配置文件路径")
    parser.add_argument("--no-device", action="store_true", 
                       help="不连接实际设备，使用模拟模式")
    parser.add_argument("--list-scenarios", action="store_true",
                       help="列出所有可用的测试场景")
    
    args = parser.parse_args()
    
    # 加载配置
    config = load_test_config(args.config)
    
    # 列出场景
    if args.list_scenarios:
        scenarios = config.get("test_scenarios", {})
        print("可用的测试场景:")
        for name, scenario in scenarios.items():
            print(f"  {name}: {scenario.get('description', '无描述')}")
        return 0
    
    try:
        success = False
        
        if args.scenario:
            # 运行预定义场景
            success = run_scenario_test(args.scenario, config, args.no_device)
            
        elif args.mode:
            # 运行自定义测试
            if not args.duration:
                print("自定义测试需要指定 --duration 参数")
                return 1
            
            print(f"运行自定义 {args.mode} 测试，持续 {args.duration} 秒")
            
            tester = GasFlowStabilityTester(
                test_duration=args.duration,
                log_level="INFO"
            )
            
            if not args.no_device:
                device_available = tester.initialize_device_manager()
                if not device_available:
                    print("错误: 设备连接失败，请检查设备连接和配置")
                    return 1
            else:
                print("警告: 使用模拟模式运行测试，不会进行真实的设备通信测试")
            
            if args.mode == "comprehensive":
                success = tester.run_comprehensive_test()
            elif args.mode == "endurance":
                success = tester.run_endurance_test()
            elif args.mode == "communication":
                success = tester.run_communication_stability_test(args.duration)
            
            if success:
                report = tester.generate_report()
                check_alerts(tester, config)
                report_file = tester.save_report(report)
                
                if report_file:
                    print(f"报告已保存到: {report_file}")
                
                print("\n" + "="*60)
                print(report)
        else:
            parser.print_help()
            return 1
        
        if success:
            print("\n✅ 测试成功完成")
            return 0
        else:
            print("\n❌ 测试失败")
            return 1
            
    except KeyboardInterrupt:
        print("\n测试被用户中断")
        return 1
    except Exception as e:
        print(f"测试过程中发生错误: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
