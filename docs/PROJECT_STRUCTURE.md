# TMH 项目结构说明

## 项目概述
TMH (Temperature, Mass Flow, Humidity) 是一个专业的铁矿石冶金性能综合检测与控制系统，版本 1.1.250907。

## 目录结构

```
TMH1.0.250907/
├── src/                           # 源代码目录
│   ├── app.py                    # 应用程序主入口
│   ├── __init__.py               # Python包初始化文件
│   ├── services/                 # 业务服务模块
│   │   ├── comm_settings.py      # 通信设置服务
│   │   ├── database.py          # 数据库服务
│   │   ├── enhanced_experiment_modes.py  # 增强实验模式
│   │   ├── experiment_data.py    # 实验数据服务
│   │   ├── experiment_file.py    # 实验文件管理
│   │   ├── experiment_modes.py   # 实验模式管理
│   │   ├── experiment_type_manager.py  # 实验类型管理
│   │   ├── gb13240_calculator.py # GB13240标准计算器
│   │   ├── gb13241_calculator.py # GB13241标准计算器
│   │   └── gb13242_calculator.py # GB13242标准计算器
│   ├── device_clients/           # 设备客户端模块
│   │   ├── balance_client.py     # 天平设备客户端
│   │   ├── base_device.py        # 设备基类
│   │   ├── data_handler.py       # 数据处理器
│   │   ├── device_health_monitor.py  # 设备健康监控
│   │   ├── device_manager.py     # 设备管理器
│   │   ├── mfcCMQProtocol.py     # MFC通信协议
│   │   ├── multi_mfc_client.py   # 多路MFC客户端
│   │   └── temp_client.py        # 温度设备客户端
│   ├── ui/                       # 用户界面模块
│   │   ├── main_window.py        # 主窗口
│   │   ├── dialogs/              # 对话框
│   │   │   ├── experiment_dialog.py      # 实验对话框
│   │   │   ├── experiment_mode_dialog.py # 实验模式对话框
│   │   │   └── rdi_analysis_dialog.py   # RDI分析对话框
│   │   ├── experiment/            # 实验控制
│   │   │   └── experiment_controller.py  # 实验控制器
│   │   ├── pages/                # 页面组件
│   │   │   ├── about_page.py     # 关于页面
│   │   │   ├── communication_settings_page.py  # 通信设置页面
│   │   │   ├── experiment_mode_settings_page.py # 实验模式设置页面
│   │   │   ├── experiment_settings_page.py      # 实验设置页面
│   │   │   ├── help_page.py      # 帮助页面
│   │   │   ├── history_query_page.py    # 历史查询页面
│   │   │   └── integrated_control_page.py       # 集成控制页面
│   │   ├── ui_components/        # UI组件
│   │   │   ├── chart_tabs.py     # 图表标签页
│   │   │   ├── control_panel.py   # 控制面板
│   │   │   ├── experiment_status.py       # 实验状态
│   │   │   ├── monitor_panel.py   # 监控面板
│   │   │   ├── pg_plot_widgets.py        # PyQtGraph绘图组件
│   │   │   ├── sidebar.py        # 侧边栏
│   │   │   ├── status_bar.py     # 状态栏
│   │   │   └── title_bar.py      # 标题栏
│   │   └── widgets/              # 自定义控件
│   ├── utils/                    # 工具模块
│   │   ├── config_loader.py      # 配置加载器
│   │   ├── data_saver.py         # 数据保存器
│   │   ├── jason_manager.py     # JSON管理器
│   │   ├── logger.py             # 日志管理器
│   │   ├── password_manager.py   # 密码管理器
│   │   ├── path_manager.py       # 路径管理器
│   │   ├── performance_monitor.py        # 性能监控器
│   │   ├── report_generation.py  # 报告生成器
│   │   ├── safety_controller.py  # 安全控制器
│   │   └── security_validator.py        # 安全验证器
│   └── web_server/               # Web服务器模块
│       └── templates/             # Web模板
├── configs/                      # 配置文件目录
│   ├── comm_config.json          # 通信配置
│   ├── exp_settings.config       # 实验设置配置
│   ├── exp_settings.configs      # 实验设置配置（备用）
│   ├── experiment_modes.json     # 实验模式配置
│   ├── health_monitor.json       # 健康监控配置
│   └── software.info             # 软件信息
├── data/                         # 数据存储目录
│   ├── device_data.db            # 设备数据数据库
│   ├── experiments.db            # 实验数据库
│   ├── test_device_data.db       # 测试设备数据数据库
│   └── experiments/               # 实验数据文件
├── docs/                         # 项目文档
├── exports/                      # 导出文件
├── logs/                         # 日志文件
├── resources/                    # 资源文件
├── tests/                        # 测试文件
├── backup-src/                   # 源代码备份
├── build/                        # 构建输出
├── dist/                         # 分发文件
├── release/                      # 发布文件
├── requirements.txt              # Python依赖包
├── README.md                     # 项目说明文档
├── CHANGELOG.md                  # 更新日志
├── CONTRIBUTING.md               # 贡献指南
├── PROJECT_STRUCTURE.md          # 项目结构说明（本文件）
├── build_release.py              # 构建脚本
├── demo_run.py                   # 演示运行脚本
├── demo_ui.py                    # 演示UI脚本
├── quick_build.bat               # Windows快速构建脚本
├── quick_build.sh                # Linux/macOS快速构建脚本
└── test_font_adjustment.py       # 字体调整测试脚本
```

## 核心模块说明

### 1. 应用程序入口 (src/app.py)
- 应用程序的主入口点
- 初始化QApplication和MainWindow
- 启动GUI应用程序

### 2. 服务模块 (src/services/)
- **comm_settings.py**: 通信设置管理
- **database.py**: 数据库操作服务
- **experiment_*.py**: 实验相关服务
- **gb13240/13241/13242_calculator.py**: 国家标准计算器

### 3. 设备客户端 (src/device_clients/)
- **base_device.py**: 设备基类，定义通用接口
- **device_manager.py**: 设备管理器，统一管理所有设备
- **data_handler.py**: 数据处理器，处理设备数据
- **device_health_monitor.py**: 设备健康监控
- **balance_client.py**: 天平设备客户端
- **temp_client.py**: 温度设备客户端
- **multi_mfc_client.py**: 多路质量流量控制器客户端
- **mfcCMQProtocol.py**: MFC通信协议实现

### 4. 用户界面 (src/ui/)
- **main_window.py**: 主窗口实现
- **pages/**: 各种功能页面
- **dialogs/**: 对话框组件
- **ui_components/**: 可复用的UI组件
- **experiment/**: 实验控制相关UI

### 5. 工具模块 (src/utils/)
- **logger.py**: 日志管理
- **config_loader.py**: 配置加载
- **path_manager.py**: 路径管理
- **data_saver.py**: 数据保存
- **report_generation.py**: 报告生成
- **safety_controller.py**: 安全控制
- **performance_monitor.py**: 性能监控

## 配置文件说明

### configs/comm_config.json
通信配置文件，包含串口参数、设备地址等通信相关设置。

### configs/exp_settings.config
实验设置配置文件，定义实验参数、采样率、持续时间等。

### configs/experiment_modes.json
实验模式配置文件，定义各种实验类型的参数和流程。

### configs/health_monitor.json
健康监控配置文件，定义设备监控参数和阈值。

## 数据存储

### 数据库文件
- **device_data.db**: 存储设备实时数据
- **experiments.db**: 存储实验记录和结果
- **test_device_data.db**: 测试用数据库

### 实验数据文件
- **data/experiments/**: 存储实验数据文件(.exp格式)

## 构建和部署

### 构建脚本
- **build_release.py**: Python构建脚本
- **quick_build.bat**: Windows快速构建
- **quick_build.sh**: Linux/macOS快速构建

### 输出目录
- **build/**: PyInstaller构建输出
- **dist/**: 最终分发文件
- **release/**: 发布版本文件

## 开发指南

### 添加新设备
1. 继承 `BaseDevice` 类
2. 实现必要的接口方法
3. 在 `DeviceManager` 中注册新设备
4. 更新配置文件

### 添加新页面
1. 在 `src/ui/pages/` 中创建新页面类
2. 继承适当的基类
3. 在 `MainWindow` 中注册新页面
4. 更新侧边栏导航

### 添加新服务
1. 在 `src/services/` 中创建服务类
2. 实现必要的业务逻辑
3. 在需要的地方导入和使用

## 注意事项

1. **代码规范**: 遵循PEP 8 Python代码规范
2. **日志记录**: 使用统一的日志管理器记录重要操作
3. **错误处理**: 完善的异常处理机制
4. **资源管理**: 正确管理文件、数据库连接等资源
5. **线程安全**: 多线程环境下的数据安全
6. **配置管理**: 使用配置文件管理参数，避免硬编码

## 版本信息

- **当前版本**: 1.1.250907
- **Python版本要求**: 3.8+
- **主要依赖**: PySide6, PyQtGraph, pandas, numpy, pyserial, psutil
- **支持平台**: Windows, Linux, macOS
