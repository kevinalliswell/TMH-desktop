@echo off
chcp 65001 >nul
echo TMH 快速打包脚本
echo ============================

REM 检查Python环境
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Python，请先安装Python
    pause
    exit /b 1
)

REM 安装依赖
echo 安装构建依赖...
pip install pyinstaller
pip install -r requirements.txt

REM 执行打包
echo 开始打包...
python build_release.py

echo.
echo 打包完成！查看 dist 目录获取结果
pause
