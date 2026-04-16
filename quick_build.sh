#!/bin/bash
echo "TMH 快速打包脚本"
echo "============================"

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到Python，请先安装Python"
    exit 1
fi

# 安装依赖
echo "安装构建依赖..."
pip3 install pyinstaller
pip3 install -r requirements.txt

# 执行打包
echo "开始打包..."
python3 build_release.py

echo
echo "打包完成！查看 dist 目录获取结果"
