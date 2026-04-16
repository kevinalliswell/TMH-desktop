#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
真实设备气体流量稳定性测试脚本
专门用于连接真实MFC设备的通信稳定性测试

使用示例:
    python run_real_device_test.py --test device_check
    python run_real_device_test.py --test communication_test
    python run_real_device_test.py --test flow_stability_test
    python run_real_device_test.py --test endurance_test
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


def load_real_device_config() -> dict:
    """加载真实设备测试配置"""
    config_file = Path(__file__).parent / "real_device_test_config.json"
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"配置文件不存在: {config_file}")
        return {}
    except json.JSONDecodeError as e:
        print(f"配置文件格式错误: {e}")
        return {}


def check_device_connection(tester: GasFlowStabilityTester) -> bool:
    """检查设备连接状态"""
    print("正在检查设备连接...")
    
    if not tester.initialize_device_manager():
        print("❌ 设备连接失败")
        return False
    
    print("✅ 设备连接成功")
    
    # 验证通信
    print("正在验证设备通信...")
    if not tester.verify_device_communication():
        print("❌ 设备通信验证失败")
        return False
    
    print("✅ 设备通信正常")
    
    # 监控设备状态
    status = tester.monitor_device_status()
    print(f"设备状态监控:")
    print(f"  连接状态: {'正常' if status['device_connected'] else '异常'}")
    print(f"  通信质量: {status['communication_quality']:.1%}")
    
    for gas, channel_status in status['gas_channels'].items():
        if channel_status['connected']:
            print(f"  {gas}通道: 正常 (当前值: {channel_status['current_value']}, "
                  f"响应时间: {channel_status['response_time']:.3f}s)")
        else:
            print(f"  {gas}通道: 异常")
    
    return True


def run_device_test(test_name: str, config: dict) -> bool:
    """运行指定的设备测试"""
    scenarios = config.get("test_scenarios", {})
    
    if test_name not in scenarios:
        print(f"未找到测试: {test_name}")
        print(f"可用测试: {list(scenarios.keys())}")
        return False
    
    scenario = scenarios[test_name]
    print(f"\n🔬 运行测试: {test_name}")
    print(f"📝 描述: {scenario['description']}")
    print(f"⏱️  持续时间: {scenario['duration']} 秒")
    print("-" * 60)
    
    # 创建测试器
    device_params = config.get("device_settings", {})
    test_params = config.get("test_parameters", {})
    
    tester = GasFlowStabilityTester(
        test_duration=scenario["duration"],
        log_level="INFO"
    )
    
    # 应用设备参数
    if "flow_tolerance" in test_params:
        tester.flow_tolerance = test_params["flow_tolerance"]
    if "stability_check_interval" in test_params:
        tester.stability_check_interval = test_params["stability_check_interval"]
    
    # 检查设备连接
    if not check_device_connection(tester):
        return False
    
    # 运行测试
    test_modes = scenario.get("test_modes", ["comprehensive"])
    success = True
    
    try:
        for mode in test_modes:
            print(f"\n▶️  执行测试模式: {mode}")
            
            if mode == "comprehensive":
                result = tester.run_comprehensive_test()
            elif mode == "endurance":
                result = tester.run_endurance_test()
            elif mode == "communication":
                result = tester.run_communication_stability_test(scenario["duration"])
            else:
                print(f"❌ 未知测试模式: {mode}")
                result = False
            
            if not result:
                success = False
                break
            
            print(f"✅ {mode} 测试完成")
        
        if success:
            # 生成报告
            print("\n📊 生成测试报告...")
            report = tester.generate_report()
            
            # 检查告警
            check_device_alerts(tester, config)
            
            # 保存报告
            report_file = tester.save_report(report)
            if report_file:
                print(f"📄 报告已保存: {report_file}")
            
            # 执行测试后操作
            post_test_actions(tester, config)
            
        return success
        
    except KeyboardInterrupt:
        print("\n⚠️  测试被用户中断")
        return False
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {str(e)}")
        return False
    finally:
        # 确保设备正确关闭
        tester.cleanup_device_manager()


def check_device_alerts(tester: GasFlowStabilityTester, config: dict):
    """检查设备相关的告警阈值"""
    thresholds = config.get("alert_thresholds", {})
    if not thresholds:
        return
    
    metrics = tester.calculate_stability_metrics()
    alerts = []
    
    for mode_key, metric in metrics.items():
        # 检查成功率
        if metric.success_rate < thresholds.get("success_rate_min", 98.0):
            alerts.append(f"❌ {mode_key}: 成功率过低 ({metric.success_rate:.1f}%)")
        
        # 检查响应时间
        if metric.avg_response_time > thresholds.get("response_time_max", 2.0):
            alerts.append(f"⚠️  {mode_key}: 响应时间过长 ({metric.avg_response_time:.3f}s)")
        
        # 检查流量精度
        if metric.flow_accuracy < thresholds.get("flow_accuracy_min", 95.0):
            alerts.append(f"❌ {mode_key}: 流量精度不足 ({metric.flow_accuracy:.1f}%)")
        
        # 检查流量稳定性
        if metric.flow_stability > thresholds.get("flow_stability_max", 3.0):
            alerts.append(f"⚠️  {mode_key}: 流量稳定性差 ({metric.flow_stability:.1f}%)")
    
    if alerts:
        print("\n🚨 设备告警信息:")
        for alert in alerts:
            print(f"  {alert}")
    else:
        print("\n✅ 所有设备指标均正常")


def post_test_actions(tester: GasFlowStabilityTester, config: dict):
    """执行测试后的清理操作"""
    actions = config.get("post_test_actions", {})
    
    if actions.get("auto_zero_flows", True):
        print("\n🔄 正在将所有气体流量清零...")
        try:
            for gas in ["CO", "CO2", "N2", "H2"]:
                success, _, error_msg = tester.set_gas_flow(gas, 0.0)
                if success:
                    print(f"  ✅ {gas}: 已清零")
                else:
                    print(f"  ❌ {gas}: 清零失败 - {error_msg}")
        except Exception as e:
            print(f"  ❌ 自动清零失败: {str(e)}")
    
    if actions.get("check_device_status", True):
        print("\n🔍 最终设备状态检查...")
        status = tester.monitor_device_status()
        print(f"  设备连接: {'正常' if status['device_connected'] else '异常'}")
        print(f"  通信质量: {status['communication_quality']:.1%}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="真实设备气体流量稳定性测试",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
可用测试:
  device_check         - 设备连接和基本功能检查 (30秒)
  communication_test   - 通信稳定性专项测试 (2分钟)
  flow_stability_test  - 流量设置稳定性测试 (5分钟)
  endurance_test       - 长期稳定性测试 (30分钟)
  stress_test          - 压力测试（频繁切换）(10分钟)

使用示例:
  %(prog)s --test device_check              # 快速设备检查
  %(prog)s --test communication_test        # 通信稳定性测试
  %(prog)s --test flow_stability_test       # 流量稳定性测试
        """
    )
    
    parser.add_argument("--test", 
                       choices=["device_check", "communication_test", "flow_stability_test", 
                               "endurance_test", "stress_test"],
                       required=True,
                       help="选择要执行的测试")
    
    parser.add_argument("--config", 
                       help="指定配置文件路径")
    
    parser.add_argument("--list-tests", action="store_true",
                       help="列出所有可用的测试")
    
    args = parser.parse_args()
    
    # 加载配置
    config = load_real_device_config()
    if not config:
        print("❌ 无法加载配置文件")
        return 1
    
    # 列出测试
    if args.list_tests:
        scenarios = config.get("test_scenarios", {})
        print("🧪 可用的真实设备测试:")
        for name, scenario in scenarios.items():
            duration_min = scenario.get('duration', 0) // 60
            duration_sec = scenario.get('duration', 0) % 60
            duration_str = f"{duration_min}分{duration_sec}秒" if duration_min > 0 else f"{duration_sec}秒"
            print(f"  {name:<20} - {scenario.get('description', '无描述')} ({duration_str})")
        return 0
    
    # 显示系统信息
    print("🔧 TMH真实设备气体流量稳定性测试")
    print("=" * 60)
    print("⚠️  注意: 此测试需要连接真实的MFC设备!")
    print("📋 确保以下条件:")
    print("  1. MFC设备已正确连接并通电")
    print("  2. 通信线缆连接正常")
    print("  3. 气体供应管路已连接")
    print("  4. 配置文件中的通信参数正确")
    print("=" * 60)
    
    try:
        success = run_device_test(args.test, config)
        
        if success:
            print("\n🎉 测试成功完成!")
            print("📊 请查看生成的报告文件了解详细结果")
            return 0
        else:
            print("\n❌ 测试失败")
            print("🔍 请检查设备连接和配置，查看日志了解详细错误信息")
            return 1
            
    except KeyboardInterrupt:
        print("\n⚠️  测试被用户中断")
        return 1
    except Exception as e:
        print(f"\n💥 测试过程中发生严重错误: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
