# TMH真实设备气体流量稳定性测试

## 快速开始

### 1. 设备准备
确保MFC设备已连接并配置正确：
- ✅ MFC设备通电且正常
- ✅ RS485通信线连接到正确COM端口  
- ✅ 通信配置正确 (`configs/comm_config.json`)

### 2. 快速测试
```bash
cd tests

# 设备连接检查（30秒）
python run_real_device_test.py --test device_check

# 通信稳定性测试（2分钟）  
python run_real_device_test.py --test communication_test

# 流量稳定性测试（5分钟）
python run_real_device_test.py --test flow_stability_test
```

## 可用测试类型

| 测试名称 | 用途 | 时间 | 命令 |
|---------|------|------|------|
| device_check | 设备连接检查 | 30秒 | `--test device_check` |
| communication_test | 通信稳定性 | 2分钟 | `--test communication_test` |
| flow_stability_test | 流量稳定性 | 5分钟 | `--test flow_stability_test` |
| endurance_test | 长期稳定性 | 30分钟 | `--test endurance_test` |
| stress_test | 压力测试 | 10分钟 | `--test stress_test` |

## 性能评估标准

### 🟢 正常指标
- 成功率: ≥ 98%
- 响应时间: < 2.0秒
- 流量精度: ≥ 95%
- 通信质量: ≥ 95%

### 🟡 需要关注
- 成功率: 95-98%
- 响应时间: 2.0-3.0秒
- 流量精度: 90-95%
- 通信质量: 90-95%

### 🔴 需要修复
- 成功率: < 95%
- 响应时间: > 3.0秒
- 流量精度: < 90%
- 通信质量: < 90%

## 常见问题解决

### ❌ 设备连接失败
1. 检查COM端口配置
2. 确认MFC设备电源
3. 验证RS485线缆连接
4. 检查设备地址设置

### ⚠️ 通信质量差
1. 排查电磁干扰源
2. 更换屏蔽通信线缆
3. 调整通信参数
4. 检查接地连接

### 📊 流量精度不足
1. 检查设备校准状态
2. 确认气体压力稳定
3. 检查管路密封性
4. 联系厂商维护

## 测试报告

测试完成后在 `tests/reports/` 目录查看：
- `gas_flow_stability_test_*.txt` - 测试报告
- `gas_flow_stability_test_*.json` - 详细数据
- `communication_test_*.json` - 通信测试数据

## 安全注意事项

⚠️ **重要提醒:**
- 确保测试环境安全通风
- 检查气体供应系统
- 准备紧急停止程序
- 测试后自动清零所有流量

---

📋 **详细文档:** 请参阅 `REAL_DEVICE_TEST_GUIDE.md` 获取完整使用指南

🔧 **技术支持:** 如遇问题请提供完整的错误日志和设备信息
