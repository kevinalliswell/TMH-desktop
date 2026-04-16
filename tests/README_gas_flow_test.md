# 气体流量稳定性测试说明

## 概述

该测试套件用于验证TMH系统在不同实验模式下切换气体流量的稳定性和可靠性。测试覆盖所有标准实验模式（GB/T 13241-2017、GB/T 13242-2017、GB/T 13240-2018）以及用户自定义的实验模式。

## 测试功能

### 1. 综合测试 (Comprehensive Test)
- 测试所有实验模式的所有阶段
- 验证每种气体（CO、CO2、N2、H2）的流量设置
- 检查流量设置的响应时间和准确性
- 生成详细的性能报告

### 2. 耐久性测试 (Endurance Test)
- 在指定时间内重复执行流量切换操作
- 随机选择不同的实验模式和阶段
- 监控系统在长时间运行下的稳定性
- 识别潜在的性能衰减问题

## 测试指标

### 成功率 (Success Rate)
- 流量设置命令的成功执行百分比
- 阈值：≥ 95%

### 响应时间 (Response Time)
- 从发送流量设置命令到完成的时间
- 平均响应时间应 < 3.0 秒
- 最大响应时间记录

### 流量精度 (Flow Accuracy)
- 实际流量与目标流量的偏差
- 精度要求：≥ 98%

### 流量稳定性 (Flow Stability)
- 多次测量的流量值变异系数
- 稳定性要求：变异系数 ≤ 2%

## 使用方法

### 快速开始

```bash
# 进入测试目录
cd tests

# 运行快速测试（1分钟）
python run_gas_flow_stability_test.py --scenario quick_test

# 运行标准测试（5分钟）
python run_gas_flow_stability_test.py --scenario standard_test

# 运行扩展测试（30分钟）
python run_gas_flow_stability_test.py --scenario extended_test
```

### 自定义测试

```bash
# 自定义综合测试
python run_gas_flow_stability_test.py --mode comprehensive --duration 300

# 自定义耐久性测试
python run_gas_flow_stability_test.py --mode endurance --duration 600

# 模拟模式（不连接实际设备）
python run_gas_flow_stability_test.py --scenario quick_test --no-device
```

### 查看可用场景

```bash
python run_gas_flow_stability_test.py --list-scenarios
```

## 测试场景说明

### quick_test
- **持续时间**: 60秒
- **测试模式**: 综合测试
- **适用场景**: 快速验证系统基本功能

### standard_test
- **持续时间**: 300秒（5分钟）
- **测试模式**: 综合测试 + 耐久性测试
- **适用场景**: 标准验收测试

### extended_test
- **持续时间**: 1800秒（30分钟）
- **测试模式**: 耐久性测试
- **适用场景**: 长期稳定性验证

## 输出文件

测试完成后会在 `tests/reports/` 目录下生成以下文件：

### 1. 文本报告 
`gas_flow_stability_test_YYYYMMDD_HHMMSS.txt`
- 包含测试摘要和详细统计信息
- 人类可读的格式

### 2. JSON数据文件
`gas_flow_stability_test_YYYYMMDD_HHMMSS.json`
- 包含所有原始测试数据
- 便于进一步分析和处理

## 报告内容

### 总体统计
- 测试时间和持续时间
- 总体成功率
- 平均和最大响应时间

### 按模式统计
- 每个实验模式的详细性能指标
- 成功率、响应时间、流量精度、稳定性

### 异常记录
- 失败操作的详细信息
- 错误原因和时间戳

### 告警信息
- 超出阈值的性能指标
- 需要关注的问题

## 配置文件

测试配置位于 `gas_flow_test_config.json`，包含：

### 测试参数
```json
{
  "test_parameters": {
    "stability_check_interval": 2.0,  // 稳定性检查间隔（秒）
    "flow_tolerance": 0.1,           // 流量容差（L/min）
    "response_timeout": 5.0,         // 响应超时时间（秒）
    "settlement_time": 1.0           // 流量稳定时间（秒）
  }
}
```

### 告警阈值
```json
{
  "alert_thresholds": {
    "success_rate_min": 95.0,      // 最小成功率（%）
    "response_time_max": 3.0,      // 最大响应时间（秒）
    "flow_accuracy_min": 98.0,     // 最小流量精度（%）
    "flow_stability_max": 2.0      // 最大变异系数（%）
  }
}
```

## 测试环境要求

### 硬件要求
- 连接的多通道质量流量控制器（MFC）
- 正常工作的气体供应系统

### 软件要求
- Python 3.8+
- TMH系统的完整依赖库
- 正确配置的通信设置

### 可选模式
- 支持模拟模式运行（使用 `--no-device` 参数）
- 用于算法验证和界面测试

## 故障排除

### 常见问题

1. **设备连接失败**
   - 检查MFC设备连接
   - 确认通信配置正确
   - 使用 `--no-device` 参数进行模拟测试

2. **测试超时**
   - 检查设备响应是否正常
   - 调整配置中的超时参数
   - 查看日志文件确认错误原因

3. **流量精度不达标**
   - 检查MFC设备校准
   - 确认气体供应压力稳定
   - 检查管路是否有泄漏

4. **测试结果异常**
   - 查看详细的JSON数据文件
   - 检查测试环境是否稳定
   - 对比历史测试结果

### 日志文件
测试运行时的详细日志保存在项目的 `logs/` 目录中，可用于问题诊断。

## 扩展开发

### 添加新的测试指标
1. 在 `StabilityMetrics` 类中添加新字段
2. 在 `calculate_stability_metrics` 方法中实现计算逻辑
3. 更新报告生成逻辑

### 自定义测试场景
1. 编辑 `gas_flow_test_config.json`
2. 在 `test_scenarios` 节中添加新场景
3. 指定测试参数和持续时间

### 集成到CI/CD
测试脚本支持命令行参数和返回码，可轻松集成到自动化测试流程中。

## 联系支持

如有技术问题或建议，请联系TMH系统开发团队。
