# 监控面板字体大小自适应功能使用指南

## 功能概述
监控面板现在支持根据窗体最大化/正常状态自动调整字体大小，提供更好的视觉体验。

## 实现原理

### 1. 字体大小配置
在 `MonitorPanel` 类中预定义了两套字体大小配置：

```python
self.font_sizes = {
    'normal': {
        'tempValue': 20,    # 温度值 - 正常状态
        'weightValue': 18,  # 重量值 - 正常状态  
        'flowValue': 16,    # 流量值 - 正常状态
        'mainLabel': 14     # 主标签 - 正常状态
    },
    'maximized': {
        'tempValue': 28,    # 温度值 - 最大化状态
        'weightValue': 26,  # 重量值 - 最大化状态
        'flowValue': 24,    # 流量值 - 最大化状态
        'mainLabel': 16     # 主标签 - 最大化状态
    }
}
```

### 2. 自动调整机制
- **窗体状态监听**：主窗口通过 `changeEvent` 监听窗体状态变化
- **状态通知**：当检测到最大化/正常状态切换时，通知监控面板
- **字体调整**：监控面板根据状态调整所有数据标签的字体大小

## API 接口

### MonitorPanel 类新增方法

#### `adjust_font_size(is_maximized=False)`
根据窗体状态调整字体大小
- **参数**：`is_maximized (bool)` - True表示最大化，False表示正常
- **功能**：调整所有主要监控标签的字体大小

#### `set_window_maximized_state(is_maximized)`
外部调用接口，设置窗体最大化状态
- **参数**：`is_maximized (bool)` - 窗体是否最大化
- **功能**：延迟调整字体大小，确保布局完成后再调整

## 使用示例

### 手动调用
```python
# 获取监控面板实例
monitor_panel = self.integrated_control_page.monitor_panel

# 手动设置为最大化状态
monitor_panel.set_window_maximized_state(True)

# 手动设置为正常状态
monitor_panel.set_window_maximized_state(False)
```

### 自动响应
系统已自动配置，当用户：
- 点击最大化按钮
- 双击标题栏
- 使用快捷键切换窗体状态

监控面板会自动调整字体大小，无需手动干预。

## 字体大小级别

### 正常窗体状态
- 温度值：20px（最重要数据，红色）
- 重量值：18px（重要数据，青色）
- 流量值：16px（常用数据，粉色）
- 标签文字：14px

### 最大化窗体状态
- 温度值：28px（增大8px）
- 重量值：26px（增大8px）
- 流量值：24px（增大8px）
- 标签文字：16px（增大2px）

## 注意事项

1. **延迟调整**：使用 `QTimer.singleShot(100ms)` 延迟调整，确保布局计算完成
2. **状态缓存**：避免重复调整同样的状态
3. **异常处理**：包含完整的错误处理机制
4. **性能优化**：只调整必要的标签，避免不必要的操作

## 扩展指南

### 添加新的字体大小级别
可以在 `font_sizes` 字典中添加更多状态：

```python
self.font_sizes = {
    'normal': { ... },
    'maximized': { ... },
    'fullscreen': {  # 新增全屏状态
        'tempValue': 32,
        'weightValue': 30,
        'flowValue': 28,
        'mainLabel': 18
    }
}
```

### 自定义字体调整逻辑
可以重写 `adjust_font_size` 方法实现自定义逻辑：

```python
def adjust_font_size(self, is_maximized=False):
    # 自定义调整逻辑
    mode = 'maximized' if is_maximized else 'normal'
    # ... 实现自定义调整
```

## 视觉效果
- **正常状态**：紧凑显示，适合1200x800最小窗体
- **最大化状态**：大字体显示，充分利用大屏幕空间
- **平滑过渡**：字体切换即时生效，提供流畅体验
