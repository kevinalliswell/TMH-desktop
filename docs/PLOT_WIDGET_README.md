# TMH绘图组件使用说明

## 概述

`plot_widget.py` 是基于 `integrated_control_page.py` 中的 `PlotDockWidget` 类重新设计的专门绘图组件。该组件提供了模块化的绘图功能，支持温度、流量、重量等实验数据的实时绘图和显示。

## 主要组件

### 1. DataDisplayWidget
实时数据显示组件，用于显示当前实验参数值。

**主要功能：**
- 添加实时数据显示项
- 更新数值显示
- 支持自定义颜色和精度

### 2. PlotWidget
基础绘图组件，提供通用的绘图功能。

**主要功能：**
- 配置图表参数（坐标轴标签、范围等）
- 添加和管理曲线
- 支持滚动窗口显示
- 自动跟随X轴

### 3. 专用绘图组件

#### TemperaturePlotWidget
温度绘图组件，专门用于显示温度数据。

**特性：**
- 支持9个温度点（T1-T9）
- 预设温度上限报警线（1200℃）
- 实时显示PV/SV温度和测温点数据

#### FlowPlotWidget
流量绘图组件，专门用于显示气体流量数据。

**特性：**
- 支持CO、CO2、N2、H2四种气体
- 预设可燃气体上限报警线（5L/min）
- 实时显示PV/SV流量和总流量

#### WeightPlotWidget
重量绘图组件，专门用于显示重量相关数据。

**特性：**
- 显示当前重量、初始重量、重量变化
- 计算并显示重量变化率
- 支持失重分析

### 4. ExperimentPlotManager
实验绘图管理器，统一管理所有绘图组件。

**主要功能：**
- 管理温度、流量、重量三个绘图组件
- 提供统一的数据更新接口
- 支持自动定时更新
- 提供数据清除功能

## 使用方法

### 基本使用

```python
from plot_widget import ExperimentPlotManager

# 创建绘图管理器
plot_manager = ExperimentPlotManager()

# 获取绘图组件
temp_plot = plot_manager.temp_plot
flow_plot = plot_manager.flow_plot
weight_plot = plot_manager.weight_plot

# 开始监控
plot_manager.start_monitoring()

# 更新数据
current_data = {
    'temp_T1': 25.5,
    'temp_T2': 26.0,
    'weight': 100.0,
    'CO': 0.5,
    'CO2': 1.0,
    'N2': 5.0,
    'H2': 0.0,
    'total_flow': 6.5
}

plot_manager.update_current_data(current_data)
plot_manager.update_experiment_time(10.5)  # 10.5分钟

# 停止监控
plot_manager.stop_monitoring()
```

### 在integrated_control_page中使用

```python
# 替换原有的PlotDockWidget
from plot_widget import ExperimentPlotManager

class IntegratedControlPage(QMainWindow):
    def __init__(self, device_manager, data_handler=None, parent_window=None):
        super().__init__()
        
        # 创建绘图管理器
        self.plot_manager = ExperimentPlotManager()
        
        # 获取绘图组件
        self.temp_widget = self.plot_manager.temp_plot
        self.flow_widget = self.plot_manager.flow_plot
        self.weight_widget = self.plot_manager.weight_plot
        
        # 添加到UI
        self.chart_tabs.addTab(self.temp_widget, "温度曲线")
        self.chart_tabs.addTab(self.flow_widget, "流量曲线")
        self.chart_tabs.addTab(self.weight_widget, "重量曲线")
    
    def update_from_current_data(self):
        """从current_data更新绘图"""
        # 更新绘图管理器的数据
        self.plot_manager.update_current_data(self.current_data)
        self.plot_manager.update_experiment_time(self.experiment_time)
        
        # 手动更新图表（或依赖定时器自动更新）
        self.plot_manager.update_plots()
```

## 数据格式

### current_data结构

```python
current_data = {
    # 温度数据
    'temp_T1': 25.5,    # 一区PV温度
    'temp_T2': 26.0,    # 二区PV温度
    'temp_T3': 25.8,    # 三区PV温度
    'temp_T4': 25.0,    # 一区SV温度
    'temp_T5': 26.2,    # 二区SV温度
    'temp_T6': 25.5,    # 三区SV温度
    'temp_T7': 25.3,    # 测温1-样品上部
    'temp_T8': 25.7,    # 测温2-样品中部（主要温度）
    'temp_T9': 25.4,    # 测温3-样品下部
    'temperature': 25.7, # 样品温度（通常等于T8）
    
    # 流量数据
    'CO': 0.5,          # CO流量
    'CO2': 1.0,         # CO2流量
    'N2': 5.0,          # N2流量
    'H2': 0.0,          # H2流量
    'total_flow': 6.5,  # 总流量
    
    # 重量数据
    'weight': 100.0,           # 当前重量
    'weight_loss': 0.5,        # 重量变化
    'weight_loss_rate': 0.5,   # 变化率（%）
    'initial_weight': 100.0,   # 初始重量
}
```

## 配置选项

### 滚动窗口大小
```python
# 设置滚动窗口大小（显示最近600个数据点）
plot_widget.window_size = 600

# 禁用滚动窗口（显示所有数据）
plot_widget.window_size = None
```

### X轴跟随
```python
# 启用X轴自动跟随
plot_widget.follow_x = True

# 禁用X轴自动跟随
plot_widget.follow_x = False
```

### 更新频率
```python
# 设置自动更新频率（毫秒）
plot_manager.update_timer.setInterval(2000)  # 每2秒更新一次
```

## 测试

运行测试代码：

```bash
cd TMH1.0.250818/src/ui
python plot_widget.py
```

或运行使用示例：

```bash
python plot_usage_example.py
```

## 注意事项

1. **数据同步**：确保 `current_data` 中的数据格式与组件期望的格式一致
2. **性能优化**：对于大量数据，建议使用滚动窗口模式
3. **内存管理**：长时间运行时注意内存使用，必要时清除历史数据
4. **线程安全**：绘图更新应在主线程中进行

## 扩展功能

### 添加新的绘图类型
```python
class CustomPlotWidget(PlotWidget):
    def __init__(self, parent=None):
        super().__init__("自定义监控", parent)
        self.setup_custom_plot()
    
    def setup_custom_plot(self):
        # 配置自定义图表
        self.configure_plot("自定义参数", "单位", [0, 100])
        # 添加曲线和显示项
        # ...
```

### 添加报警功能
```python
def add_alarm_line(self, value, color=(255, 0, 0)):
    """添加报警线"""
    pen = pg.mkPen(color=color, width=2, style=Qt.DashLine)
    self.plot_widget.plotItem.addLine(y=value, pen=pen)
```

## 版本历史

- v1.0.0: 初始版本，基于integrated_control_page.py中的PlotDockWidget重构
- 支持温度、流量、重量三种绘图类型
- 提供统一的ExperimentPlotManager管理接口
- 支持实时数据显示和滚动窗口
