#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TMH 1.1 应用打包发布脚本
支持 Windows、macOS 和 Linux 平台
使用 PyInstaller 进行打包
"""

import sys
import shutil
import subprocess
import platform
import argparse
from pathlib import Path
import zipfile
import json
from datetime import datetime


def _configure_utf8_stdio() -> None:
    """Prefer UTF-8 console output so GitHub Windows runners can print Chinese logs."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="backslashreplace")
        except Exception:
            pass


_configure_utf8_stdio()


class TMHBuilder:
    def __init__(self):
        self.project_root = Path(__file__).parent.absolute()
        self.src_dir = self.project_root / "src"
        self.dist_dir = self.project_root / "dist"
        self.build_dir = self.project_root / "build"
        self.release_dir = self.project_root / "release"
        
        # 应用信息
        # 从配置文件 configs/software.info 读取应用信息
        software_info_file = self.project_root / "configs" / "software.info"
        if not software_info_file.exists():
            raise FileNotFoundError(f"未找到配置文件: {software_info_file}")
        with open(software_info_file, "r", encoding="utf-8") as f:
            info = json.load(f)
        self.app_name = info.get("name", "TMH") if "name" in info else "TMH"
        self.app_version = info.get("version", "1.0.0")
        self.app_description = info.get("description", "")
        self.main_script = self.src_dir / "app.py"
        
        # 平台信息
        self.platform = platform.system().lower()
        self.arch = platform.machine().lower()
        
        print("TMH Builder 初始化完成")
        print(f"项目根目录: {self.project_root}")
        print(f"目标平台: {self.platform} ({self.arch})")
        print(f"应用版本: {self.app_version}")

    def check_dependencies(self):
        """检查构建依赖"""
        print("\n检查构建依赖...")
        
        # 检查 PyInstaller
        try:
            import PyInstaller
            print(f"✓ PyInstaller 已安装: {PyInstaller.__version__}")
        except ImportError:
            print("✗ PyInstaller 未安装，正在安装...")
            subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
            print("✓ PyInstaller 安装完成")
        
        # 检查主要依赖
        required_packages = [
            ("PySide6", "PySide6.QtCore"),
            ("pyqtgraph", "pyqtgraph"),
            ("numpy", "numpy"),
            ("pyserial", "serial"),
            ("psutil", "psutil")
        ]
        for package_name, import_name in required_packages:
            try:
                __import__(import_name)
                print(f"✓ {package_name} 已安装")
            except ImportError:
                print(f"✗ {package_name} 未安装，请先运行: pip install -r requirements.txt")
                return False
        
        return True

    def clean_build(self):
        """清理构建目录"""
        print("\n清理构建目录...")
        
        for dir_path in [self.dist_dir, self.build_dir]:
            if dir_path.exists():
                shutil.rmtree(dir_path)
                print(f"✓ 已清理: {dir_path}")
        
        # 清理 spec 文件
        spec_files = list(self.project_root.glob("*.spec"))
        for spec_file in spec_files:
            spec_file.unlink()
            print(f"✓ 已删除: {spec_file}")

    def create_spec_file(self):
        """创建 PyInstaller spec 文件"""
        print("\n创建 PyInstaller spec 文件...")
        
        spec_content = f'''# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

block_cipher = None

# 项目路径
project_root = Path(r"{self.project_root}")
src_dir = project_root / "src"

# 数据文件
datas = [
    (str(project_root / "configs"), "configs"),
    (str(project_root / "resources"), "resources"),
]

# 隐藏导入
hiddenimports = [
    "PySide6.QtCore",
    "PySide6.QtWidgets", 
    "PySide6.QtGui",
    "PySide6.QtCharts",
    "pyqtgraph",
    "numpy",
    "serial",
    "psutil",
    "sqlite3",
    "json",
    "logging",
    "threading",
    "queue",
    "datetime",
    "pathlib",
    "dataclasses",
    "enum",
    "collections",
    "contextlib",
    "abc",
    "statistics",
    "hashlib",
    "secrets",
    "re",
    "functools",
    "atexit",
    "traceback",
    "csv",
    "binascii",
    "random",
    "uuid",
    "typing",
    "typing_extensions",
    "webbrowser",
    "urllib",
    "urllib.parse",
    "email",
    "email.mime",
    "email.mime.text",
    "smtplib",
]

# 分析
a = Analysis(
    [str(src_dir / "app.py")],
    pathex=[str(project_root), str(src_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# PYZ
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# 可执行文件
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="{self.app_name}",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Windows 下不显示控制台
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / "resources" / "icons" / "tmh_icon_128x128.ico"),
)

# 收集文件
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="{self.app_name}",
)
'''
        
        spec_file = self.project_root / f"{self.app_name}.spec"
        with open(spec_file, 'w', encoding='utf-8') as f:
            f.write(spec_content)
        
        print(f"✓ Spec 文件已创建: {spec_file}")
        return spec_file

    def build_application(self, spec_file, debug=False):
        """构建应用程序"""
        print("\n开始构建应用程序...")
        
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--clean",
            "--noconfirm",
        ]
        
        if debug:
            cmd.append("--debug=all")
        
        cmd.append(str(spec_file))
        
        print(f"执行命令: {' '.join(cmd)}")
        
        try:
            subprocess.run(cmd, cwd=self.project_root, check=True, 
                          capture_output=False, text=True)
            print("✓ 应用程序构建完成")
            return True
        except subprocess.CalledProcessError as e:
            print(f"✗ 构建失败: {e}")
            return False

    def copy_additional_files(self):
        """复制额外需要的文件"""
        print("\n复制额外文件...")
        
        app_dir = self.dist_dir / self.app_name
        if not app_dir.exists():
            print(f"✗ 应用目录不存在: {app_dir}")
            return False
        
        # 复制配置文件
        configs_src = self.project_root / "configs"
        configs_dst = app_dir / "configs"
        if configs_src.exists():
            if configs_dst.exists():
                shutil.rmtree(configs_dst)
            shutil.copytree(configs_src, configs_dst)
            print(f"✓ 已复制配置文件: {configs_dst}")
        
        # 复制资源文件
        resources_src = self.project_root / "resources"
        resources_dst = app_dir / "resources"
        if resources_src.exists():
            if resources_dst.exists():
                shutil.rmtree(resources_dst)
            shutil.copytree(resources_src, resources_dst)
            print(f"✓ 已复制资源文件: {resources_dst}")
        
        # 样式文件已包含在resources目录中，无需单独复制
        styles_path = app_dir / "resources" / "styles"
        if styles_path.exists():
            qss_files = list(styles_path.glob("*.qss"))
            print(f"✓ 样式文件已包含在resources中，找到 {len(qss_files)} 个QSS文件")
        else:
            print(f"⚠ 样式文件目录不存在: {styles_path}")
        
        # 创建必要的目录
        required_dirs = ["data", "logs", "data/experiments", "data/uploads", "exports"]
        for dir_name in required_dirs:
            dir_path = app_dir / dir_name
            dir_path.mkdir(parents=True, exist_ok=True)
            print(f"✓ 已创建目录: {dir_path}")
        
        # 复制文档文件
        doc_files = ["README.md", "requirements.txt", "CHANGELOG.md"]
        for doc_file in doc_files:
            src_file = self.project_root / doc_file
            if src_file.exists():
                dst_file = app_dir / doc_file
                shutil.copy2(src_file, dst_file)
                print(f"✓ 已复制文档: {dst_file}")
        
        return True

    def create_installer_script(self):
        """创建安装脚本"""
        print("\n创建安装脚本...")
        
        app_dir = self.dist_dir / self.app_name
        
        if self.platform == "windows":
            # Windows 批处理安装脚本
            install_script = f'''@echo off
chcp 65001 >nul
echo TMH {self.app_version} 安装脚本
echo.

set "INSTALL_DIR=%PROGRAMFILES%\\TMH"
echo 安装目录: %INSTALL_DIR%
echo.

if not exist "%INSTALL_DIR%" (
    echo 创建安装目录...
    mkdir "%INSTALL_DIR%"
)

echo 复制文件...
xcopy /E /I /Y "{self.app_name}" "%INSTALL_DIR%"

echo 创建桌面快捷方式...
set "SHORTCUT=%USERPROFILE%\\Desktop\\TMH.lnk"
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT%'); $s.TargetPath = '%INSTALL_DIR%\\{self.app_name}.exe'; $s.WorkingDirectory = '%INSTALL_DIR%'; $s.Description = '{self.app_description}'; $s.Save()"

echo.
echo 安装完成！
echo 可执行文件位置: %INSTALL_DIR%\\{self.app_name}.exe
echo 桌面快捷方式: %SHORTCUT%
echo.
pause
'''
            
            script_file = app_dir.parent / "install.bat"
            with open(script_file, 'w', encoding='utf-8') as f:
                f.write(install_script)
                
        else:
            # Unix 安装脚本
            install_script = f'''#!/bin/bash
echo "TMH {self.app_version} 安装脚本"
echo

INSTALL_DIR="/opt/TMH"
echo "安装目录: $INSTALL_DIR"
echo

if [ ! -d "$INSTALL_DIR" ]; then
    echo "创建安装目录..."
    sudo mkdir -p "$INSTALL_DIR"
fi

echo "复制文件..."
sudo cp -r "{self.app_name}" "$INSTALL_DIR/"
sudo chmod +x "$INSTALL_DIR/{self.app_name}/{self.app_name}"

echo "创建系统链接..."
sudo ln -sf "$INSTALL_DIR/{self.app_name}/{self.app_name}" "/usr/local/bin/tmh"

echo "创建桌面快捷方式..."
DESKTOP_FILE="$HOME/Desktop/TMH.desktop"
cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=TMH
Comment={self.app_description}
Exec=$INSTALL_DIR/{self.app_name}/{self.app_name}
Icon=$INSTALL_DIR/{self.app_name}/resources/icons/tmh_logo_square_512x512.png
Terminal=false
Categories=Science;
EOF
chmod +x "$DESKTOP_FILE"

echo
echo "安装完成！"
echo "可执行文件位置: $INSTALL_DIR/{self.app_name}/{self.app_name}"
echo "命令行启动: tmh"
echo "桌面快捷方式: $DESKTOP_FILE"
echo
'''
            
            script_file = app_dir.parent / "install.sh"
            with open(script_file, 'w', encoding='utf-8') as f:
                f.write(install_script)
            script_file.chmod(0o755)
        
        print(f"✓ 安装脚本已创建: {script_file}")

    def create_release_package(self):
        """创建发布包"""
        print("\n创建发布包...")
        
        # 确保发布目录存在
        self.release_dir.mkdir(exist_ok=True)
        
        # 发布包名称
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        package_name = f"{self.app_name}_{self.app_version}_{self.platform}_{self.arch}_{timestamp}"
        
        # 创建压缩包
        package_file = self.release_dir / f"{package_name}.zip"
        
        with zipfile.ZipFile(package_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 添加应用目录
            app_dir = self.dist_dir / self.app_name
            for file_path in app_dir.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(self.dist_dir)
                    zipf.write(file_path, arcname)
            
            # 添加安装脚本
            for script_file in self.dist_dir.glob('install.*'):
                zipf.write(script_file, script_file.name)
        
        print(f"✓ 发布包已创建: {package_file}")
        print(f"  文件大小: {package_file.stat().st_size / 1024 / 1024:.1f} MB")
        
        # 创建发布信息文件
        release_info = {
            "app_name": self.app_name,
            "app_version": self.app_version,
            "app_description": self.app_description,
            "platform": self.platform,
            "architecture": self.arch,
            "build_time": datetime.now().isoformat(),
            "package_file": package_file.name,
            "package_size_mb": round(package_file.stat().st_size / 1024 / 1024, 1)
        }
        
        info_file = self.release_dir / f"{package_name}_info.json"
        with open(info_file, 'w', encoding='utf-8') as f:
            json.dump(release_info, f, indent=2, ensure_ascii=False)
        
        print(f"✓ 发布信息已创建: {info_file}")
        
        return package_file

    def _check_app_icons(self):
        """检查应用图标是否存在"""
        print("\n检查应用图标...")
        
        icon_file = self.project_root / "resources" / "icons" / "tmh_icon_128x128.ico"
        if icon_file.exists():
            print(f"✓ 应用图标已存在: {icon_file}")
            return True
        else:
            print(f"⚠ 应用图标不存在: {icon_file}")
            return False
    
    def verify_build(self):
        """验证构建结果"""
        print("\n验证构建结果...")
        
        app_dir = self.dist_dir / self.app_name
        if not app_dir.exists():
            print(f"✗ 应用目录不存在: {app_dir}")
            return False
        
        # 检查关键文件
        key_files = [
            self.app_name + (".exe" if self.platform == "windows" else ""),
            "configs",
            "resources",
            "resources/styles"
        ]
        
        missing_files = []
        for file_name in key_files:
            file_path = app_dir / file_name
            if not file_path.exists():
                missing_files.append(file_name)
            else:
                print(f"✓ 已找到: {file_name}")
        
        if missing_files:
            print(f"✗ 缺少关键文件: {', '.join(missing_files)}")
            return False
        
        # 检查样式文件
        styles_dir = app_dir / "resources" / "styles"
        if styles_dir.exists():
            qss_files = list(styles_dir.glob("*.qss"))
            if qss_files:
                print(f"✓ 找到 {len(qss_files)} 个样式文件")
            else:
                print("⚠ 样式目录存在但没有找到QSS文件")
        
        print("✓ 构建结果验证完成")
        return True

    def build(self, debug=False, clean=True):
        """完整构建流程"""
        print(f"\n开始构建 TMH {self.app_version}")
        print("=" * 50)
        
        try:
            # 1. 检查应用图标
            if not self._check_app_icons():
                print("⚠ 应用图标检查失败，但继续构建")
            
            # 2. 检查依赖
            if not self.check_dependencies():
                return False
            
            # 2. 清理构建目录
            if clean:
                self.clean_build()
            
            # 3. 创建 spec 文件
            spec_file = self.create_spec_file()
            
            # 4. 构建应用程序
            if not self.build_application(spec_file, debug):
                return False
            
            # 5. 复制额外文件
            if not self.copy_additional_files():
                return False
            
            # 6. 验证构建结果
            if not self.verify_build():
                print("⚠ 构建验证失败，但继续进行")
            
            # 7. 创建安装脚本
            self.create_installer_script()
            
            # 8. 创建发布包
            package_file = self.create_release_package()
            
            print("\n" + "=" * 50)
            print("✓ 构建完成！")
            print(f"应用目录: {self.dist_dir / self.app_name}")
            print(f"发布包: {package_file}")
            print("=" * 50)
            
            return True
            
        except Exception as e:
            print(f"\n✗ 构建失败: {e}")
            import traceback
            traceback.print_exc()
            return False

def main():
    parser = argparse.ArgumentParser(description="TMH 应用打包构建脚本")
    parser.add_argument("--debug", action="store_true", help="启用调试模式")
    parser.add_argument("--no-clean", action="store_true", help="不清理构建目录")
    
    args = parser.parse_args()
    
    builder = TMHBuilder()
    success = builder.build(debug=args.debug, clean=not args.no_clean)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
