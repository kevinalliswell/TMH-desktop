#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
气体流量稳定性测试演示脚本
展示如何使用测试工具进行不同场景的测试

运行方式:
    python demo_gas_flow_test.py
"""

import sys
import time
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tests.gas_flow_stability_test import GasFlowStabilityTester
from src.utils.logger import get_logger


def demo_quick_test():
    """演示快速测试"""
    print("=" * 60)
    print("演示 1: 快速功能测试")
    print("=" * 60)
    
    # 创建测试器
    tester = GasFlowStabilityTester(test_duration=30, log_level="INFO")
    
    print("初始化测试器...")
    print(f"测试持续时间: {tester.test_duration} 秒")
    print(f"测试气体: {', '.join(tester.test_gases)}")
    
    # 使用模拟模式（不连接实际设备）
    print("\n运行综合测试（模拟模式）...")
    
    success = tester.run_comprehensive_test()
    
    if success:
        print("\n✅ 测试完成")
        
        # 显示测试结果
        metrics = tester.calculate_stability_metrics()
        print(f"\n测试记录数: {len(tester.test_records)}")
        print(f"测试模式数: {len(metrics)}")
        
        # 生成简化报告
        if tester.test_records:
            total_success = sum(1 for r in tester.test_records if r.success)
            success_rate = total_success / len(tester.test_records) * 100
            avg_response = sum(r.response_time for r in tester.test_records) / len(tester.test_records)
            
            print(f"总体成功率: {success_rate:.1f}%")
            print(f"平均响应时间: {avg_response:.3f} 秒")
    else:
        print("❌ 测试失败")
    
    return success


def demo_mode_comparison():
    """演示不同模式的对比测试"""
    print("\n" + "=" * 60)
    print("演示 2: 模式对比测试")
    print("=" * 60)
    
    # 创建测试器
    tester = GasFlowStabilityTester(log_level="INFO")
    
    # 获取测试模式
    test_modes = tester.get_test_modes()
    
    print(f"发现 {len(test_modes)} 个测试场景:")
    
    # 按模式分组
    mode_groups = {}
    for mode_name, stage_name, stage_info in test_modes:
        if mode_name not in mode_groups:
            mode_groups[mode_name] = []
        mode_groups[mode_name].append((stage_name, stage_info))
    
    for mode_name, stages in mode_groups.items():
        print(f"\n📋 {mode_name}:")
        for stage_name, stage_info in stages:
            gas_settings = stage_info["gas_settings"]
            active_gases = [gas for gas, flow in gas_settings.items() if flow > 0]
            print(f"  - {stage_name}: {', '.join(active_gases) if active_gases else '无气体'}")
    
    # 测试几个代表性模式
    print(f"\n测试前 3 个模式的流量切换...")
    
    test_count = 0
    for mode_name, stage_name, stage_info in test_modes[:3]:
        test_count += 1
        print(f"\n🔬 测试 {test_count}: {mode_name} - {stage_name}")
        
        records = tester.test_mode_flow_switching(mode_name, stage_info)
        
        # 显示结果
        successful = sum(1 for r in records if r.success)
        print(f"   结果: {successful}/{len(records)} 成功")
        
        time.sleep(0.5)  # 短暂停顿
    
    return True


def demo_custom_analysis():
    """演示自定义分析"""
    print("\n" + "=" * 60)
    print("演示 3: 自定义分析")
    print("=" * 60)
    
    # 创建测试器并生成一些测试数据
    tester = GasFlowStabilityTester(log_level="INFO")
    
    print("生成测试数据...")
    test_modes = tester.get_test_modes()
    
    # 选择几个不同的模式进行测试
    selected_modes = test_modes[::3][:5]  # 每隔3个选一个，最多5个
    
    for mode_name, stage_name, stage_info in selected_modes:
        tester.test_mode_flow_switching(mode_name, stage_info)
    
    if not tester.test_records:
        print("没有生成测试数据")
        return False
    
    # 自定义分析
    print(f"\n📊 分析 {len(tester.test_records)} 条测试记录:")
    
    # 按气体类型分析
    gas_stats = {}
    for record in tester.test_records:
        gas = record.gas_type
        if gas not in gas_stats:
            gas_stats[gas] = {"total": 0, "success": 0, "response_times": []}
        
        gas_stats[gas]["total"] += 1
        if record.success:
            gas_stats[gas]["success"] += 1
        gas_stats[gas]["response_times"].append(record.response_time)
    
    print("\n按气体类型统计:")
    for gas, stats in gas_stats.items():
        success_rate = stats["success"] / stats["total"] * 100
        avg_response = sum(stats["response_times"]) / len(stats["response_times"])
        print(f"  {gas}: 成功率 {success_rate:.1f}%, 平均响应 {avg_response:.3f}s")
    
    # 按模式分析
    mode_stats = {}
    for record in tester.test_records:
        mode = record.mode_name
        if mode not in mode_stats:
            mode_stats[mode] = {"total": 0, "success": 0}
        
        mode_stats[mode]["total"] += 1
        if record.success:
            mode_stats[mode]["success"] += 1
    
    print("\n按模式统计:")
    for mode, stats in mode_stats.items():
        success_rate = stats["success"] / stats["total"] * 100
        print(f"  {mode}: 成功率 {success_rate:.1f}%")
    
    return True


def main():
    """主函数"""
    print("🧪 气体流量稳定性测试演示")
    print("=" * 60)
    print("本演示展示了如何使用测试工具验证不同模式下的流量切换稳定性")
    print("注意: 演示使用模拟模式运行，不需要连接实际设备")
    
    try:
        # 演示1: 快速功能测试
        demo1_success = demo_quick_test()
        
        # 演示2: 模式对比测试
        demo2_success = demo_mode_comparison()
        
        # 演示3: 自定义分析
        demo3_success = demo_custom_analysis()
        
        # 总结
        print("\n" + "=" * 60)
        print("演示总结")
        print("=" * 60)
        
        results = [
            ("快速功能测试", demo1_success),
            ("模式对比测试", demo2_success),
            ("自定义分析", demo3_success)
        ]
        
        for name, success in results:
            status = "✅ 成功" if success else "❌ 失败"
            print(f"{name}: {status}")
        
        print("\n💡 使用建议:")
        print("1. 首次使用建议运行快速测试验证基本功能")
        print("2. 定期运行标准测试监控系统稳定性")
        print("3. 在系统升级后运行扩展测试验证兼容性")
        print("4. 使用自定义测试针对特定问题进行诊断")
        
        print("\n📝 运行真实测试:")
        print("python run_gas_flow_stability_test.py --scenario quick_test")
        print("python run_gas_flow_stability_test.py --scenario standard_test")
        print("python run_gas_flow_stability_test.py --scenario extended_test")
        
    except KeyboardInterrupt:
        print("\n演示被用户中断")
    except Exception as e:
        print(f"\n演示过程中发生错误: {str(e)}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
