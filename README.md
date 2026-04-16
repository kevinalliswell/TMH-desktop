# TMH-LPF-900 铁矿石冶金性能综合检测与控制系统

[![CI](https://img.shields.io/github/actions/workflow/status/kevinalliswell/TMH-desktop/ci.yml?branch=main&label=CI)](https://github.com/kevinalliswell/TMH-desktop/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/kevinalliswell/TMH-desktop?display_name=tag)](https://github.com/kevinalliswell/TMH-desktop/releases)
[![Python](https://img.shields.io/badge/Python-3.10%2B-green.svg)](https://www.python.org/)
[![PySide6](https://img.shields.io/badge/UI-PySide6-41CD52.svg)](https://doc.qt.io/qtforpython/)

## 项目简介

TMH-LPF-900 是一个专业的铁矿石冶金性能综合检测与控制系统，由北京科技大学开发。系统集成了温度控制、气体质量流量控制、电子天平称重等功能，为铁矿石冶金性能检测提供精确的数据采集、实验控制和分析解决方案。

### 主要特性

- **实时数据采集** — 多路温度（9通道）、4路气体流量（H2/N2/CO2/CO）、电子天平实时监测
- **国标实验模式** — 内置 GB/T 13240、GB/T 13241、GB/T 13242 标准实验流程
- **自定义实验** — 支持创建、编辑自定义实验模式，灵活配置各阶段参数
- **数据可视化** — 基于 pyqtgraph 的实时图表，温度/流量/重量多标签页切换
- **历史数据管理** — SQLite 数据库存储，支持查询、导出和报告生成
- **设备自动重连** — 指数退避重连策略，保障长时间实验稳定运行
- **标准协议包** — 自研 `tmh_comm` 通信协议包，支持 Modbus-CPL（MFC）、Modbus-RTU（温控）、RS232-ASCII（天平）

## 系统架构

```
TMH-LPF-900
├── 桌面应用程序 (PySide6)
│   ├── 集成控制页面 — 实时监控 + 实验控制
│   ├── 实验模式配置 — 标准/自定义实验管理
│   ├── 历史数据查询 — 数据检索、导出、报告
│   └── 通信设置页面 — 串口参数、从机地址、采样配置
├── 设备通信层
│   ├── tmh_comm 协议包 (Modbus-CPL / Modbus-RTU / RS232)
│   ├── DeviceManager — 设备注册、启停、协调
│   ├── BaseDevice — 抽象基类（线程、重连、队列）
│   └── DataHandler — 数据处理、信号分发、数据库写入
├── 业务服务层
│   ├── AppRuntime — 应用生命周期管理
│   ├── CommSettings — 通信配置加载/保存/校验
│   ├── ExperimentRuntime — 实验流程引擎
│   └── GB 分析计算器 (13240 / 13241 / 13242)
└── 数据存储
    ├── SQLite 数据库 (data/)
    └── JSON 配置文件 (configs/)
```

## 快速开始

### 系统要求

| 项目 | 最低要求 | 推荐配置 |
|------|---------|---------|
| 操作系统 | Windows 10 | Windows 11 |
| Python | 3.10+ | 3.12 |
| 内存 | 4 GB | 8 GB |
| 硬盘空间 | 2 GB | 10 GB |
| 串口 | 2 个 | 3 个以上 |
| 显示器 | 1280×720 | 1920×1080 |

### 安装方法

#### 方法一：从源码运行

```bash
# 克隆仓库
git clone https://github.com/kevinalliswell/TMH-desktop.git
cd TMH-desktop

# 安装依赖
python -m pip install -r requirements.txt

# 安装本地协议包
python -m pip install ./packages/tmh_comm

# 运行应用程序
python src/app.py
```

#### 方法二：使用构建脚本打包

**Windows:**
```batch
quick_build.bat
```

**Linux/macOS:**
```bash
chmod +x quick_build.sh
./quick_build.sh
```

构建完成后可执行文件位于 `dist/` 目录。

### 首次使用

1. **启动应用程序** — 运行 `python src/app.py` 或双击打包后的可执行文件
2. **配置通信参数** — 进入「通信设置」页面，为温控仪、MFC、天平分别配置串口和参数
3. **选择实验模式** — 在集成控制页面右侧选择实验模式（标准或自定义）
4. **开始实验** — 天平去皮 → 设置初重 → 开始实验

## 功能模块

### 1. 集成控制页面

左侧实时监控面板显示温度、流量、重量等关键参数，右侧控制面板提供实验操作入口。支持手动控制气体流量和查看实时图表。

### 2. 实验模式配置

- **标准模式**: 内置 GB/T 13241（还原性）、GB/T 13242（低温粉化）、GB/T 13240（膨胀指数）
- **自定义模式**: 支持创建全新模式或复制标准模式后编辑
- **阶段类型**: 升温 (HEATING)、恒温 (STABILIZING)、还原 (REDUCING)、冷却 (COOLING)

### 3. 历史数据查询

- 按实验名称、日期范围查询历史实验
- 以图表形式回放实验数据
- 导出实验数据，生成 HTML 格式报告

### 4. 通信设置

- **分标签页配置**: 温度控制器、气体流量计、电子天平各一个标签页
- **串口参数**: 端口、波特率、数据位、校验位、停止位
- **从机地址 / 流量缩放**: MFC 和温控器各自的从机地址配置
- **串口刷新**: 支持运行时重新扫描可用 COM 口
- **恢复默认**: 一键恢复所有参数为出厂默认值
- **脏状态提示**: 页面切换或关闭时自动提示未保存的修改

### 5. 分析算法

| 标准 | 功能 |
|------|------|
| GB/T 13240 | 球团矿自由膨胀指数测定 |
| GB/T 13241 | 铁矿石还原性测定 |
| GB/T 13242 | 铁矿石低温粉化试验 |

## 设备连接

### 默认串口参数

| 设备 | 串口 | 波特率 | 数据位 | 停止位 | 校验位 | 接口 |
|------|------|--------|--------|--------|--------|------|
| MFC 流量计 | COM1 | 9600 | 8 | 1 | 偶校验 | RS-485 |
| 温度控制器 | COM2 | 9600 | 8 | 1 | 无校验 | RS-485 |
| 电子天平 | COM3 | 1200 | 8 | 1 | 偶校验 | RS-232 |

### MFC 从机地址

| 通道 | 气体 | 默认地址 |
|------|------|---------|
| MFC #1 | H2 | 1 |
| MFC #2 | N2 | 2 |
| MFC #3 | CO2 | 3 |
| MFC #4 | CO | 4 |

## 项目结构

```
TMH/
├── src/                        # 源代码
│   ├── app.py                  # 应用程序入口
│   ├── services/               # 业务服务
│   │   ├── app_runtime.py      # 应用生命周期管理
│   │   ├── comm_settings.py    # 通信配置管理
│   │   ├── experiment_data.py  # 实验数据服务
│   │   ├── experiment_file.py  # 实验文件管理
│   │   ├── experiment_modes.py # 实验模式管理
│   │   ├── gb13240_calculator.py
│   │   ├── gb13241_calculator.py
│   │   └── gb13242_calculator.py
│   ├── device_clients/         # 设备客户端
│   │   ├── base_device.py      # 设备基类（线程、重连）
│   │   ├── multi_mfc_client.py # MFC 流量计客户端
│   │   ├── temp_client.py      # 温度控制器客户端
│   │   ├── balance_client.py   # 电子天平客户端
│   │   ├── device_manager.py   # 设备管理器
│   │   └── data_handler.py     # 数据处理器
│   ├── ui/                     # 用户界面
│   │   ├── main_window.py      # 主窗口
│   │   ├── pages/              # 页面
│   │   ├── dialogs/            # 对话框
│   │   └── ui_components/      # UI 组件
│   └── utils/                  # 工具类
│       ├── logger.py           # 日志管理
│       ├── path_manager.py     # 路径管理
│       └── password_manager.py # 密码管理
├── packages/                   # 本地 Python 包
│   └── tmh_comm/               # 通信协议包
│       └── src/tmh_comm/
│           ├── protocols/      # 协议实现
│           └── standard.py     # 标准数据帧
├── configs/                    # 配置文件
│   ├── comm_config.json        # 通信参数
│   ├── experiment_modes.json   # 实验模式定义
│   ├── exp_settings.config     # 实验设置
│   └── software.info           # 软件版本信息
├── resources/                  # 资源文件
│   ├── icons/                  # 图标
│   └── help.html               # 帮助文档
├── data/                       # 实验数据
├── exports/                    # 导出文件
├── logs/                       # 运行日志
├── docs/                       # 项目文档
├── tests/                      # 测试文件
├── build_release.py            # 构建脚本
├── quick_build.bat             # Windows 快速构建
├── quick_build.sh              # Linux/macOS 快速构建
└── requirements.txt            # Python 依赖
```

## 开发指南

### 开发环境设置

```bash
# 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS

# 安装依赖
python -m pip install -r requirements-dev.txt ./packages/tmh_comm

# 运行测试
pytest
```

### 关键依赖

| 包名 | 用途 |
|------|------|
| PySide6 | Qt GUI 框架 |
| pyqtgraph | 实时数据图表 |
| pyserial | 串口通信 |
| pymodbus | Modbus 协议 |
| psutil | 系统性能监控 |

## GitHub 协作

- 开发规范见 `CONTRIBUTING.md`
- 仓库设置检查清单见 `docs/GITHUB_SETUP_CHECKLIST.md`
- 版本号以 `configs/software.info` 为准，发布标签格式为 `v<version>`

## 版本历史

### v1.1.251121 (2025-11-21)
- 重构通信设置页面：控件引用集中管理、信号连接分离、串口刷新、恢复默认、脏状态跟踪
- 优化设备客户端：移除冗余协议文件，统一使用 tmh_comm 协议包
- 修复温控器从机地址保存后不生效的问题
- 修复天平波特率校验逻辑不可靠的问题

### v1.1.250907 (2025-09-07)
- 优化数据采集性能
- 改进用户界面体验
- 修复已知问题

### v1.0.250818 (2025-08-18)
- 初始版本发布
- 基础功能实现
- 设备通信支持
- 数据采集功能

## 联系方式

- **开发者**: 史进朋 (Shi Jinpeng)
- **所属单位**: 北京科技大学 冶金与生态工程学院
- **技术支持**: shijinpeng06@126.com
- **官网**: https://www.ustb.edu.cn

---

**TMH-LPF-900 — 让冶金检测更智能、更高效**
