# 自定义实验模式使用指南

## 概述

本系统现在支持通过配置文件管理自定义实验模式，用户可以创建、修改、导入导出自定义的实验流程。

## 功能特性

### 🎯 核心功能
- **配置文件驱动**: 所有实验模式通过JSON配置文件管理
- **标准模式保护**: 内置的GB标准实验模式不可修改，确保合规性
- **自定义模式**: 支持创建无限制的自定义实验流程
- **参数验证**: 自动验证实验参数的合理性和安全性
- **导入导出**: 支持实验配置的备份和分享

### 🛠️ 管理功能
- **复制创建**: 从现有实验复制并修改创建新实验
- **实时加载**: 修改配置文件后自动重新加载
- **错误检查**: 详细的配置验证和错误提示
- **分类管理**: 标准实验和自定义实验分类显示

## 配置文件结构

### 文件位置
```
TMH1.0.250818/configs/experiment_modes.json
```

### 基本结构
```json
{
  "experiment_modes": {
    "standard_modes": {
      "GB_13241_2017": { ... },
      "GB_13242_2017": { ... },
      "GB_13240_2018": { ... }
    },
    "custom_modes": {
      "CUSTOM_EXPERIMENT_1": { ... },
      "CUSTOM_EXPERIMENT_2": { ... }
    }
  },
  "stage_name_mappings": { ... },
  "validation_rules": { ... }
}
```

### 实验模式定义
```json
{
  "name": "实验显示名称",
  "description": "实验描述信息",
  "category": "custom",
  "enabled": true,
  "created_by": "user",
  "created_time": "2024-01-01T00:00:00",
  "stages": [
    {
      "stage_name": "HEATING",
      "description": "阶段描述",
      "target_temp": 900.0,
      "temp_tolerance": 5.0,
      "duration": 30.0,
      "heating_rate": 10.0,
      "gas_settings": {
        "CO": 0.0,
        "CO2": 0.0,
        "N2": 5.0,
        "H2": 0.0,
        "total_flow": 5.0
      }
    }
  ]
}
```

## 使用方法

### 1. 通过GUI选择实验
- 打开实验模式选择对话框
- 标准实验显示🔬图标
- 自定义实验显示⚙️图标
- 实验按类型分组显示

### 2. 编程方式管理
```python
from src.utils.experiment_modes import ExperimentModeManager
from src.utils.experiment_config_manager import ExperimentConfigManager

# 初始化管理器
mode_manager = ExperimentModeManager()
config_manager = ExperimentConfigManager(mode_manager)

# 创建自定义实验
template = config_manager.create_experiment_template()
template['name'] = "我的自定义实验"
config_manager.create_custom_experiment("MY_EXPERIMENT", template)

# 复制现有实验
config_manager.copy_experiment("GB_13241_2017", "MY_COPY", "改进版还原实验")

# 导出实验
export_path = config_manager.export_experiment("MY_EXPERIMENT", "./exports/")

# 导入实验
config_manager.import_experiment("./imports/experiment.json", "IMPORTED_EXP")
```

### 3. 手动编辑配置文件
1. 打开 `configs/experiment_modes.json`
2. 在 `custom_modes` 部分添加新实验
3. 保存文件后系统自动重新加载

## 阶段类型说明

### 支持的阶段类型
- **IDLE**: 待机状态
- **HEATING**: 升温阶段
- **STABILIZING**: 恒温阶段  
- **REDUCING**: 还原阶段
- **COOLING**: 冷却阶段
- **COMPLETED**: 完成状态

### 阶段参数说明
- `stage_name`: 阶段类型（必需）
- `description`: 阶段描述（必需）
- `target_temp`: 目标温度，单位℃（必需）
- `temp_tolerance`: 温度误差范围，单位℃（必需）
- `duration`: 持续时间，单位分钟，0表示动态时间（必需）
- `heating_rate`: 升温速率，单位℃/min，负值表示冷却（必需）
- `gas_settings`: 气体设置（必需）

### 气体设置参数
- `CO`: CO流量，单位L/min
- `CO2`: CO2流量，单位L/min
- `N2`: N2流量，单位L/min
- `H2`: H2流量，单位L/min
- `total_flow`: 总流量，单位L/min

## 验证规则

### 默认验证规则
```json
{
  "temperature": {
    "min": 25.0,
    "max": 1200.0,
    "tolerance_max": 50.0
  },
  "flow_rate": {
    "min": 0.0,
    "max": 50.0
  },
  "duration": {
    "min": 0.0,
    "max": 1440.0
  },
  "heating_rate": {
    "min": -50.0,
    "max": 50.0
  }
}
```

### 参数范围说明
- **温度**: 25-1200℃，误差范围不超过50℃
- **流量**: 0-50 L/min
- **时间**: 0-1440分钟（24小时）
- **升温速率**: -50 到 +50 ℃/min

## 安全注意事项

### ⚠️ 重要提醒
1. **标准实验不可修改**: GB标准实验模式受保护，确保符合国家标准
2. **参数验证**: 所有参数都会经过安全性验证
3. **备份配置**: 修改前建议备份配置文件
4. **温度限制**: 系统会强制执行温度和流量的安全限制

### 🔒 安全特性
- 参数范围验证防止设备损坏
- 配置文件格式验证防止系统错误
- 实验类型隔离防止误操作标准模式
- 详细的错误日志便于问题追踪

## 故障排除

### 常见问题

#### 配置文件加载失败
```
错误: 配置文件格式错误
解决: 检查JSON格式是否正确，使用JSON验证工具
```

#### 参数超出范围
```
错误: 目标温度1500℃超出范围[25-1200℃]
解决: 调整参数到合理范围内
```

#### 实验键名冲突
```
错误: 实验键名已存在
解决: 使用唯一的实验键名
```

### 日志查看
系统会在日志中记录所有配置操作：
```
INFO: 成功加载实验模式配置: 5 个模式
ERROR: 配置文件格式错误: Missing required field 'stages'
```

## 最佳实践

### 🎯 命名规范
- 实验键名使用大写字母和下划线
- 实验名称简洁明了，包含主要特征
- 阶段描述详细说明操作目的

### 📋 配置建议
1. **模块化设计**: 将复杂实验分解为简单阶段
2. **参数合理**: 选择设备能力范围内的参数
3. **时间规划**: 合理安排各阶段时间
4. **气体配比**: 确保气体流量配比正确

### 💾 管理建议
1. **定期备份**: 备份配置文件到安全位置
2. **版本控制**: 使用Git等工具管理配置变更
3. **测试验证**: 新实验投入使用前充分测试
4. **文档记录**: 维护实验变更记录

## 示例代码

查看 `examples/custom_experiment_demo.py` 了解完整的使用示例，包括：
- 创建自定义实验
- 复制和修改实验
- 导入导出实验
- 参数验证演示

运行示例：
```bash
cd TMH1.0.250818
python examples/custom_experiment_demo.py
```

## 技术支持

如有问题或建议，请查看：
- 系统日志文件
- 示例代码和文档
- 配置文件注释说明
