# 数据导出功能使用指南

## 概述

TMH系统现在支持将实验数据导出为多种格式，包括CSV、Excel和TXT格式。数据导出功能基于 `chart_tabs` 中的数据表格，可以方便地保存和分享实验数据。

## 功能特性

### 支持的格式
- **CSV格式** (.csv): 逗号分隔值文件，兼容Excel和其他数据分析工具
- **Excel格式** (.xlsx): 原生Excel文件，支持格式化和样式
- **TXT格式** (.txt): 制表符分隔的文本文件，便于程序处理

### 导出内容
- 时间戳（国标时间格式）
- 实验时长（HH:MM:SS格式）
- 样品温度（T8传感器）
- 气体流量（N2、CO、CO2、H2的PV值）
- 重量数据
- 实验状态
- 系统提示信息

## 使用方法

### 1. 通过控制面板保存
1. 在实验运行过程中或实验结束后
2. 点击控制面板中的"保存数据"按钮
3. 系统会弹出格式选择对话框
4. 选择所需的导出格式
5. 选择保存位置和文件名
6. 点击"导出"完成保存

### 2. 程序化调用
```python
# 直接导出为CSV格式
success = chart_tabs.export_data(format_type='csv', file_path='data.csv')

# 显示导出对话框
success = chart_tabs.show_export_dialog()

# 获取数据行数
count = chart_tabs.get_table_data_count()
```

## 技术实现

### 核心模块
- `src/utils/data_saver.py`: 数据保存核心模块
- `src/ui/ui_components/chart_tabs.py`: 图表组件，包含导出方法
- `src/ui/pages/integrated_control_page.py`: 集成控制页面，处理保存信号

### 依赖库
- `openpyxl>=3.1.0`: Excel文件支持
- `csv`: Python内置库，CSV文件支持
- `PySide6`: GUI框架

### 文件结构
```
src/utils/data_saver.py          # 数据保存器
├── DataSaver                    # 主要保存类
├── DataExportDialog            # 导出对话框
└── 支持的方法:
    ├── save_data()             # 保存数据
    ├── _save_csv()             # CSV保存
    ├── _save_xls()             # Excel保存
    └── _save_txt()             # TXT保存
```

## 配置选项

### 导出设置
- **包含表头**: 默认启用，可在导出对话框中取消
- **文件编码**: CSV使用UTF-8-BOM，TXT使用UTF-8
- **Excel样式**: 自动设置表头样式和列宽

### 文件命名
默认文件名格式：`实验数据_YYYYMMDD_HHMMSS.扩展名`

## 错误处理

### 常见问题
1. **没有数据可保存**: 确保实验已运行并产生了数据
2. **Excel导出失败**: 检查是否安装了openpyxl库
3. **文件保存失败**: 检查目标路径的写入权限

### 错误信息
- 成功: "实验数据导出成功"
- 取消: "数据导出已取消"
- 失败: "保存数据失败: [具体错误信息]"

## 测试

运行测试脚本验证功能：
```bash
python tests/test_data_saver.py
```

测试覆盖：
- CSV格式导出
- TXT格式导出
- Excel格式导出（需要openpyxl）
- 数据提取功能
- 格式支持检查

## 注意事项

1. **数据完整性**: 导出的是当前表格中显示的所有数据
2. **文件覆盖**: 如果目标文件已存在，会被覆盖
3. **内存使用**: 大量数据导出时注意内存使用
4. **依赖检查**: Excel导出需要openpyxl库，系统会自动检查

## 扩展功能

### 自定义格式
可以通过继承 `DataSaver` 类来添加新的导出格式：

```python
class CustomDataSaver(DataSaver):
    def _save_custom(self, data, file_path):
        # 实现自定义格式保存
        pass
```

### 批量导出
可以修改代码支持批量导出多个实验的数据：

```python
def export_multiple_experiments(experiments, format_type='csv'):
    for exp in experiments:
        exp.chart_tabs.export_data(format_type)
```

## 更新日志

- **v1.0.250907**: 初始版本，支持CSV、Excel、TXT格式导出
- 添加了完整的错误处理和用户反馈
- 集成了导出对话框和进度显示
- 添加了完整的测试覆盖
