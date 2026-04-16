@echo off
REM 气体流量稳定性测试批处理脚本
REM 适用于Windows系统

echo ========================================
echo TMH气体流量稳定性测试工具
echo ========================================
echo.

REM 检查Python是否可用
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 找不到Python，请确保Python已安装并添加到PATH
    pause
    exit /b 1
)

echo 当前工作目录: %CD%
echo Python版本:
python --version
echo.

REM 显示菜单
:menu
echo 请选择测试选项:
echo 1. 快速测试 (1分钟)
echo 2. 标准测试 (5分钟)
echo 3. 扩展测试 (30分钟)
echo 4. 演示模式
echo 5. 自定义测试
echo 6. 查看帮助
echo 0. 退出
echo.

set /p choice=请输入选项 (0-6): 

if "%choice%"=="1" goto quick_test
if "%choice%"=="2" goto standard_test
if "%choice%"=="3" goto extended_test
if "%choice%"=="4" goto demo_test
if "%choice%"=="5" goto custom_test
if "%choice%"=="6" goto show_help
if "%choice%"=="0" goto exit
echo 无效选项，请重新选择
goto menu

:quick_test
echo.
echo 运行快速测试...
echo 注意: 需要连接真实MFC设备
python run_gas_flow_stability_test.py --scenario quick_test
goto end_test

:standard_test
echo.
echo 运行标准测试...
echo 注意: 需要连接真实MFC设备
python run_gas_flow_stability_test.py --scenario standard_test
goto end_test

:extended_test
echo.
echo 运行扩展测试...
echo 警告: 此测试将持续30分钟，需要连接真实MFC设备
set /p confirm=确认继续? (y/N): 
if /i not "%confirm%"=="y" goto menu
python run_gas_flow_stability_test.py --scenario extended_test
goto end_test

:demo_test
echo.
echo 运行演示模式...
python demo_gas_flow_test.py
goto end_test

:custom_test
echo.
echo 自定义测试配置
echo 可用的测试模式:
echo   comprehensive - 综合测试
echo   endurance    - 耐久性测试
echo.
set /p test_mode=请输入测试模式: 
set /p duration=请输入持续时间(秒): 

echo.
echo 运行自定义测试: %test_mode%，持续时间: %duration% 秒
echo 注意: 需要连接真实MFC设备
python run_gas_flow_stability_test.py --mode %test_mode% --duration %duration%
goto end_test

:show_help
echo.
echo ========================================
echo 测试说明
echo ========================================
echo.
echo 快速测试: 验证基本功能，适合日常检查
echo 标准测试: 全面测试稳定性，适合验收测试
echo 扩展测试: 长时间稳定性验证，适合压力测试
echo 演示模式: 展示测试功能，不生成正式报告
echo.
echo 测试结果保存在 reports 目录中
echo 支持文本和JSON两种格式的报告
echo.
echo 注意事项:
echo - 默认使用模拟模式，不连接实际设备
echo - 如需连接设备，请移除脚本中的 --no-device 参数
echo - 确保配置文件 gas_flow_test_config.json 存在
echo.
pause
goto menu

:end_test
echo.
echo ========================================
echo 测试完成
echo ========================================
if errorlevel 1 (
    echo 测试执行过程中出现错误
) else (
    echo 测试成功完成
    echo 报告文件已保存到 reports 目录
)
echo.
set /p return=按Enter返回主菜单...
goto menu

:exit
echo 感谢使用TMH气体流量稳定性测试工具！
pause
exit /b 0
