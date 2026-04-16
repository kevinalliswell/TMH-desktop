# TMH绘图组件集成指南

## 概述

本指南说明如何将新的 `plot_widget.py` 绘图组件集成到现有的 `integrated_control_page.py` 中，替换原有的 `PlotDockWidget` 类。

## 集成步骤

### 1. 导入新的绘图组件

在 `integrated_control_page.py` 文件顶部添加导入：

```python
# 在现有导入后添加
from src.ui.plot_widget import ExperimentPlotManager
```

### 2. 修改初始化方法

在 `IntegratedControlPage.__init__()` 方法中，替换原有的绘图组件创建代码：

```python
def __init__(self, device_manager, data_handler=None, parent_window=None):
    super().__init__()
    # ... 现有初始化代码 ...
    
    # 替换原有的绘图组件创建
    # 删除原有的 PlotDockWidget 创建代码
    # 添加新的绘图管理器
    self.plot_manager = ExperimentPlotManager()
    
    # 获取绘图组件
    self.temp_widget = self.plot_manager.temp_plot
    self.flow_widget = self.plot_manager.flow_plot
    self.weight_widget = self.plot_manager.weight_plot
    
    # ... 其余初始化代码 ...
```

### 3. 修改UI创建方法

在 `init_ui()` 方法中，替换图表创建代码：

```python
def init_ui(self):
    # ... 现有UI创建代码 ...
    
    # 创建图表标签页
    self.chart_tabs = QTabWidget()
    left_layout.addWidget(self.chart_tabs)
    
    # 使用新的绘图组件
    self.chart_tabs.addTab(self.temp_widget, "温度曲线")
    self.chart_tabs.addTab(self.flow_widget, "流量曲线")
    self.chart_tabs.addTab(self.weight_widget, "重量曲线")
    
    # 删除原有的 PlotDockWidget 创建和配置代码
    # ... 其余UI创建代码 ...
```

### 4. 修改数据更新方法

更新数据更新方法以使用新的绘图管理器：

```python
def update_displays_from_data(self):
    """从data_dict更新曲线和表格显示"""
    if not self.is_collecting or not self.experiment_running:
        return

    try:
        # 更新绘图管理器的数据
        self.plot_manager.update_current_data(self.current_data)
        self.plot_manager.update_experiment_time(self.experiment_time)
        
        # 启动绘图监控（如果尚未启动）
        if not self.plot_manager.update_timer.isActive():
            self.plot_manager.start_monitoring()
        
        # 更新数据表格
        self.update_data_table()

    except Exception as e:
        self.logger.error(f"更新显示数据出错: {str(e)}")
```

### 5. 修改实验控制方法

在实验开始和停止方法中添加绘图管理器的控制：

```python
def start_experiment(self):
    """开始自动实验"""
    # ... 现有实验开始代码 ...
    
    # 启动绘图监控
    self.plot_manager.start_monitoring()
    
    # ... 其余实验开始代码 ...

def stop_experiment(self):
    """停止自动实验"""
    # ... 现有实验停止代码 ...
    
    # 停止绘图监控
    self.plot_manager.stop_monitoring()
    
    # ... 其余实验停止代码 ...

def complete_experiment(self):
    """完成实验"""
    # ... 现有实验完成代码 ...
    
    # 停止绘图监控
    self.plot_manager.stop_monitoring()
    
    # ... 其余实验完成代码 ...
```

### 6. 修改数据清除方法

在 `clear_data()` 方法中添加绘图数据清除：

```python
def clear_data(self):
    """清除数据"""
    reply = QMessageBox.question(self, "确认清除", "确定要清除所有收集的数据吗？",
                                 QMessageBox.Yes | QMessageBox.No)
    if reply == QMessageBox.Yes:
        # ... 现有清除代码 ...
        
        # 清除绘图数据
        self.plot_manager.clear_all_data()
        
        # ... 其余清除代码 ...
```

### 7. 删除不再需要的方法

可以删除以下原有的方法，因为它们的功能已被新的绘图组件替代：

```python
# 可以删除的方法
def _update_temperature_curves_from_data(self):
def _update_flow_curves_from_data(self):
def _update_weight_curves_from_data(self):
def _add_simulated_data(self):
```

### 8. 修改数据更新方法

简化数据更新方法，因为绘图更新现在由绘图管理器自动处理：

```python
def update_temperature_data(self, data):
    """更新温度数据 - 只更新data_dict和实时标签"""
    if not self.is_collecting:
        return

    try:
        if not data:
            return

        # 更新实时数据到data_dict
        for i in range(1, 10):
            key = f"T{i}"
            if key in data:
                value = data[key]
                if isinstance(value, (int, float)):
                    self.current_data[f'temp_{key}'] = value
                    
                    # 使用测温中部热电偶T8作为样品温度
                    if key == 'T8':
                        self.current_data['temperature'] = value
                        if hasattr(self, 'monitor_displays') and 'temperature' in self.monitor_displays:
                            self.monitor_displays['temperature'].setText(f"{value:.1f}")

    except Exception as e:
        self.logger.error(f"更新温度数据出错: {str(e)}")

def update_flow_data(self, data):
    """更新流量数据 - 只更新data_dict"""
    if not self.is_collecting:
        return

    try:
        total_measured_flow = 0.0
        if not data:
            return

        for key in ["CO", "CO2", "N2", "H2"]:
            if key in data:
                gas_data = data[key]
                if isinstance(gas_data, dict):
                    pv = gas_data.get("PV", 0.0) or 0.0
                    sv = gas_data.get("SV", 0.0) or 0.0

                    # N2需要乘以10
                    if key == "N2":
                        pv *= 10
                        sv *= 10

                    total_measured_flow += pv
                    self.current_data[key] = pv
                    self.current_data[f'{key}_sv'] = sv

        self.current_data['total_flow'] = total_measured_flow

    except Exception as e:
        self.logger.error(f"更新流量数据出错: {str(e)}")

def update_weight_data(self, data):
    """更新重量数据 - 只更新data_dict"""
    if not self.is_collecting:
        return

    try:
        if not data or not isinstance(data, dict):
            return

        weight = data.get("weight", 0)
        if not isinstance(weight, (int, float)):
            return

        # 计算重量变化和变化率
        initial_weight = getattr(self, 'initial_weight', 0.0)
        weight_change = weight - initial_weight
        change_rate = (weight_change / initial_weight * 100) if initial_weight > 0 else 0.0

        self.current_data['weight'] = weight
        self.current_data['weight_loss'] = weight_change
        self.current_data['weight_loss_rate'] = change_rate

    except Exception as e:
        self.logger.error(f"更新重量数据出错: {str(e)}")
```

## 配置选项

### 绘图更新频率

```python
# 在初始化后设置更新频率
self.plot_manager.update_timer.setInterval(2000)  # 每2秒更新一次
```

### 滚动窗口大小

```python
# 设置滚动窗口大小
self.temp_widget.window_size = 600  # 显示最近600个数据点
self.flow_widget.window_size = 600
self.weight_widget.window_size = 600
```

## 测试集成

1. 运行修改后的 `integrated_control_page.py`
2. 检查温度、流量、重量图表是否正常显示
3. 验证实时数据更新是否正常
4. 测试实验开始/停止功能
5. 测试数据清除功能

## 注意事项

1. **向后兼容性**：确保现有的实验功能不受影响
2. **性能**：新的绘图组件可能对性能有轻微影响，建议测试
3. **数据格式**：确保 `current_data` 的数据格式与绘图组件期望的格式一致
4. **错误处理**：添加适当的错误处理，确保绘图错误不影响主要功能

## 回滚方案

如果集成后出现问题，可以通过以下步骤回滚：

1. 恢复原有的 `PlotDockWidget` 相关代码
2. 删除新的绘图组件导入
3. 恢复原有的数据更新方法
4. 重新测试功能

## 优势

使用新的绘图组件后，您将获得：

1. **模块化设计**：绘图功能独立，易于维护
2. **统一接口**：所有绘图组件使用相同的接口
3. **更好的性能**：优化的绘图更新机制
4. **易于扩展**：可以轻松添加新的绘图类型
5. **代码复用**：绘图组件可以在其他页面中重复使用
