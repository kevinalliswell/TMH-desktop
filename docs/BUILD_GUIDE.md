# TMH 1.0.250818 构建指南

## 概述

TMH（铁矿石冶金性能综合检测系统）是一个基于PySide6的桌面应用程序。本指南将帮助您完成应用的构建和打包。

## 项目结构

```
TMH1.0.250818/
├── src/                    # 源代码
├── resources/              # 资源文件
│   └── icons/             # 应用图标
├── configs/               # 配置文件
├── build_release.py       # 主构建脚本
├── quick_build.bat        # Windows快速构建脚本
├── quick_build.sh         # Linux/macOS快速构建脚本
└── requirements.txt       # 依赖包列表
```

## 应用图标设计

### 图标特色
- **TMH文字**: 大号粗体字体，突出显示应用名称
- **高炉背景**: 根据真实高炉造型设计的背景图案，体现冶金检测主题
- **工业色彩**: 深蓝灰色主色调，橙色和红色点缀，体现专业工业风格
- **多尺寸支持**: 16x16 到 512x512 全系列尺寸

### 图标文件
- `tmh_icon.ico` - Windows图标文件
- `tmh_icon.png` - 主图标PNG格式
- `tmh_icon_[尺寸].png` - 各种尺寸的PNG图标

## 构建方法

### 方法一：快速构建（推荐）

#### Windows
```batch
# 双击运行或在命令行执行
quick_build.bat
```

#### Linux/macOS
```bash
# 在终端执行
chmod +x quick_build.sh
./quick_build.sh
```

### 方法二：手动构建

1. **安装依赖**
```bash
pip install -r requirements.txt
```

2. **生成图标**
```bash
cd resources/icons
python create_icon.py
```

3. **执行构建**
```bash
python build_release.py
```

### 方法三：高级选项

```bash
# 启用调试模式
python build_release.py --debug

# 不清理构建目录
python build_release.py --no-clean
```

## 构建输出

构建完成后，您将在以下目录找到结果：

- `dist/TMH/` - 应用程序目录
- `release/` - 打包的发布文件
  - `TMH_[版本]_[平台]_[时间戳].zip` - 压缩包
  - `TMH_[版本]_[平台]_[时间戳]_info.json` - 构建信息

## 安装和分发

### Windows
1. 解压发布包
2. 运行 `install.bat` 进行系统安装
3. 或直接运行 `dist/TMH/TMH.exe`

### Linux/macOS
1. 解压发布包
2. 运行 `install.sh` 进行系统安装
3. 或直接运行 `dist/TMH/TMH`

## 图标自定义

如需自定义图标：

1. 编辑 `resources/icons/create_icon.py`
2. 修改颜色方案、尺寸或设计元素
3. 重新运行构建脚本

### 颜色方案
```python
colors = {
    'primary': '#2C3E50',      # 深蓝灰色背景
    'secondary': '#E74C3C',    # 红色 - 象征高温
    'accent': '#F39C12',       # 橙色 - 象征金属光泽
    'background': '#ECF0F1',   # 浅灰色
    'text': '#FFFFFF'          # 白色文字
}
```

## 常见问题

### Q: 构建失败，提示缺少模块
A: 确保已安装所有依赖：`pip install -r requirements.txt`

### Q: 图标生成失败
A: 安装Pillow库：`pip install Pillow`

### Q: 打包后程序无法运行
A: 检查是否有缺失的依赖文件，使用调试模式构建获取详细信息

### Q: 如何修改应用版本
A: 编辑 `build_release.py` 中的 `app_version` 变量

## 开发建议

1. **测试构建**: 在正式发布前先进行测试构建
2. **版本管理**: 为每个版本打上Git标签
3. **文档更新**: 更新版本时同步更新相关文档
4. **依赖检查**: 定期检查和更新依赖包版本

## 技术支持

如遇到构建问题，请检查：
1. Python版本（推荐3.8+）
2. 所有依赖包是否正确安装
3. 系统权限是否充足
4. 磁盘空间是否足够

---
*TMH 1.0.250818 - 铁矿石冶金性能综合检测系统*
