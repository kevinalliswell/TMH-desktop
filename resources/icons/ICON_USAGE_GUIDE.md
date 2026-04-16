# TMH 图标使用指南

## 概述

本目录包含了TMH系统的各种图标文件，包括从原始LOGO转换的图标和专门设计的增强版图标。

## 图标类型

### 1. 标准图标 (tmh_logo_icon)
- **来源**: 从 `TMH_USTB_LOGO.png` 直接转换
- **特点**: 保持原始LOGO的完整设计
- **适用场景**: 官方文档、网站、正式发布版本

### 2. 圆角图标 (tmh_logo_rounded)
- **来源**: 标准图标 + 圆角处理
- **特点**: 现代感强，适合移动端和现代UI
- **适用场景**: 移动应用、现代桌面环境

### 3. 正方形图标 (tmh_logo_square)
- **来源**: 标准图标 + 正方形适配
- **特点**: 填满整个正方形区域
- **适用场景**: 需要填满空间的场景

### 4. 增强版图标 (tmh_enhanced_icon)
- **来源**: 专门设计，突出TMH功能特点
- **特点**: 包含温度计、流量计、湿度计等元素
- **适用场景**: 应用程序图标、系统托盘

## 文件格式

### Windows ICO
- `tmh_logo_icon.ico` - 标准版ICO文件
- `tmh_enhanced_icon.ico` - 增强版ICO文件
- **用途**: Windows应用程序图标

### PNG 文件
- `tmh_logo_icon_16x16.png` 到 `tmh_logo_icon_512x512.png`
- `tmh_logo_rounded_32x32.png` 到 `tmh_logo_rounded_512x512.png`
- `tmh_logo_square_32x32.png` 到 `tmh_logo_square_512x512.png`
- `tmh_enhanced_icon_16x16.png` 到 `tmh_enhanced_icon_512x512.png`
- **用途**: 通用图标格式，支持透明度

### macOS ICNS
- `tmh_logo_icon.icns` - 标准版ICNS文件
- `tmh_enhanced_icon.icns` - 增强版ICNS文件
- **用途**: macOS应用程序图标

## 尺寸说明

| 尺寸 | 用途 |
|------|------|
| 16x16 | 系统托盘、小图标 |
| 24x24 | 工具栏按钮 |
| 32x32 | 桌面快捷方式 |
| 48x48 | 中等尺寸显示 |
| 64x64 | 高分辨率显示 |
| 128x128 | 大尺寸显示 |
| 256x256 | 高分辨率桌面 |
| 512x512 | 最高分辨率 |

## 在代码中使用

### PySide6/Qt 应用
```python
from PySide6.QtGui import QIcon, QPixmap

# 设置窗口图标
icon = QIcon("resources/icons/tmh_logo_icon.ico")
window.setWindowIcon(icon)

# 设置应用程序图标
app.setWindowIcon(icon)
```

### 网页中使用
```html
<!-- 网站图标 -->
<link rel="icon" type="image/png" sizes="32x32" href="tmh_logo_icon_32x32.png">
<link rel="icon" type="image/png" sizes="16x16" href="tmh_logo_icon_16x16.png">

<!-- Apple Touch Icon -->
<link rel="apple-touch-icon" sizes="180x180" href="tmh_logo_icon_256x256.png">
```

## 预览图

- `tmh_logo_preview.png` - 包含所有尺寸的预览图
- 用于快速查看所有图标效果

## 生成脚本

### 从LOGO转换
```bash
python convert_logo_to_icons.py
```

### 生成增强版图标
```bash
python create_enhanced_icon.py
```

### 测试图标效果
```bash
python test_logo_icons.py
```

## 建议

1. **应用程序图标**: 推荐使用 `tmh_enhanced_icon.ico`
2. **网站图标**: 推荐使用 `tmh_logo_icon` 系列
3. **移动应用**: 推荐使用 `tmh_logo_rounded` 系列
4. **系统集成**: 根据系统要求选择合适格式

## 注意事项

1. 所有图标都支持透明度
2. 建议在不同背景下测试图标效果
3. 小尺寸图标已进行优化处理
4. 保持图标的原始比例和设计完整性
