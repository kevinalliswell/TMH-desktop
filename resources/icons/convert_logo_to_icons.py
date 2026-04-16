#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TMH_USTB_LOGO 转图标脚本
将 TMH_USTB_LOGO.png 转换为各种尺寸的图标文件
支持 ICO、PNG、ICNS 格式
"""

from PIL import Image, ImageDraw, ImageFilter, ImageFont
import os
import math
from pathlib import Path

class LogoToIconConverter:
    def __init__(self):
        self.output_dir = Path(__file__).parent
        self.logo_path = Path(__file__).parent.parent / "TMH_USTB_LOGO.png"
        self.sizes = [16, 24, 32, 48, 64, 128, 256, 512]
        
        # 检查源文件是否存在
        if not self.logo_path.exists():
            raise FileNotFoundError(f"源LOGO文件不存在: {self.logo_path}")
        
        print(f"源LOGO文件: {self.logo_path}")
        print(f"输出目录: {self.output_dir}")

    def load_and_prepare_logo(self):
        """加载并预处理LOGO图片"""
        try:
            # 加载原始图片
            original_img = Image.open(self.logo_path)
            print(f"原始图片尺寸: {original_img.size}")
            print(f"原始图片模式: {original_img.mode}")
            
            # 转换为RGBA模式以支持透明度
            if original_img.mode != 'RGBA':
                original_img = original_img.convert('RGBA')
            
            return original_img
        except Exception as e:
            raise Exception(f"加载LOGO文件失败: {e}")

    def create_icon_from_logo(self, size, original_img):
        """从LOGO创建指定尺寸的图标"""
        # 创建透明背景
        icon = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        
        # 计算缩放比例，保持宽高比
        original_width, original_height = original_img.size
        scale = min(size / original_width, size / original_height)
        
        # 计算缩放后的尺寸
        new_width = int(original_width * scale)
        new_height = int(original_height * scale)
        
        # 缩放图片
        scaled_img = original_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # 计算居中位置
        x = (size - new_width) // 2
        y = (size - new_height) // 2
        
        # 将缩放后的图片粘贴到图标中心
        icon.paste(scaled_img, (x, y), scaled_img)
        
        # 为小尺寸图标添加优化
        if size <= 32:
            icon = self._optimize_small_icon(icon, size)
        
        return icon

    def _optimize_small_icon(self, icon, size):
        """优化小尺寸图标"""
        # 对于小尺寸图标，进行锐化处理以提高清晰度
        if size <= 16:
            # 应用轻微锐化
            icon = icon.filter(ImageFilter.UnsharpMask(radius=0.5, percent=150, threshold=3))
        elif size <= 32:
            # 应用轻微锐化
            icon = icon.filter(ImageFilter.UnsharpMask(radius=0.3, percent=120, threshold=3))
        
        return icon

    def create_rounded_icon(self, size, original_img):
        """创建圆角图标版本"""
        # 创建透明背景
        icon = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(icon)
        
        # 计算缩放比例
        original_width, original_height = original_img.size
        scale = min(size / original_width, size / original_height) * 0.9  # 留出边距
        new_width = int(original_width * scale)
        new_height = int(original_height * scale)
        
        # 缩放图片
        scaled_img = original_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # 计算居中位置
        x = (size - new_width) // 2
        y = (size - new_height) // 2
        
        # 创建圆角遮罩
        mask = Image.new('L', (size, size), 0)
        mask_draw = ImageDraw.Draw(mask)
        corner_radius = size // 8
        mask_draw.rounded_rectangle([0, 0, size, size], corner_radius, fill=255)
        
        # 应用圆角遮罩
        icon.paste(scaled_img, (x, y), scaled_img)
        icon.putalpha(mask)
        
        return icon

    def create_square_icon(self, size, original_img):
        """创建正方形图标版本"""
        # 创建正方形画布
        icon = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        
        # 计算缩放比例，填满整个正方形
        scale = size / max(original_img.size)
        new_width = int(original_img.width * scale)
        new_height = int(original_img.height * scale)
        
        # 缩放图片
        scaled_img = original_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # 居中粘贴
        x = (size - new_width) // 2
        y = (size - new_height) // 2
        icon.paste(scaled_img, (x, y), scaled_img)
        
        return icon

    def create_ico_file(self, original_img):
        """创建Windows ICO文件"""
        images = []
        ico_sizes = [16, 24, 32, 48, 64, 128, 256]
        
        for size in ico_sizes:
            icon = self.create_icon_from_logo(size, original_img)
            images.append(icon)
        
        ico_path = self.output_dir / "tmh_logo_icon.ico"
        images[0].save(ico_path, format='ICO', sizes=[(img.width, img.height) for img in images])
        print(f"✓ ICO文件已创建: {ico_path}")
        return ico_path

    def create_png_files(self, original_img):
        """创建PNG文件"""
        png_files = []
        
        # 标准版本
        for size in self.sizes:
            icon = self.create_icon_from_logo(size, original_img)
            png_path = self.output_dir / f"tmh_logo_icon_{size}x{size}.png"
            icon.save(png_path, format='PNG')
            png_files.append(png_path)
            print(f"✓ PNG文件已创建: {png_path}")
        
        # 圆角版本
        for size in [32, 48, 64, 128, 256, 512]:
            icon = self.create_rounded_icon(size, original_img)
            png_path = self.output_dir / f"tmh_logo_rounded_{size}x{size}.png"
            icon.save(png_path, format='PNG')
            png_files.append(png_path)
            print(f"✓ 圆角PNG文件已创建: {png_path}")
        
        # 正方形版本
        for size in [32, 48, 64, 128, 256, 512]:
            icon = self.create_square_icon(size, original_img)
            png_path = self.output_dir / f"tmh_logo_square_{size}x{size}.png"
            icon.save(png_path, format='PNG')
            png_files.append(png_path)
            print(f"✓ 正方形PNG文件已创建: {png_path}")
        
        # 创建主图标
        main_icon = self.create_icon_from_logo(256, original_img)
        main_path = self.output_dir / "tmh_logo_icon.png"
        main_icon.save(main_path, format='PNG')
        print(f"✓ 主图标已创建: {main_path}")
        
        return png_files

    def create_icns_file(self, original_img):
        """创建macOS ICNS文件"""
        try:
            from PIL import IcnsImagePlugin
            
            images = {}
            icns_sizes = [16, 32, 64, 128, 256, 512]
            
            for size in icns_sizes:
                icon = self.create_icon_from_logo(size, original_img)
                images[f'{size}x{size}'] = icon
            
            icns_path = self.output_dir / "tmh_logo_icon.icns"
            main_img = self.create_icon_from_logo(512, original_img)
            main_img.save(icns_path, format='ICNS')
            print(f"✓ ICNS文件已创建: {icns_path}")
            return icns_path
            
        except Exception as e:
            print(f"⚠ ICNS文件创建失败: {e}")
            return None

    def create_preview_image(self, original_img):
        """创建预览图片，展示所有尺寸的图标"""
        # 创建预览画布
        preview_width = 800
        preview_height = 600
        preview = Image.new('RGB', (preview_width, preview_height), (240, 240, 240))
        draw = ImageDraw.Draw(preview)
        
        # 添加标题
        try:
            title_font = ImageFont.truetype("arial.ttf", 24)
        except:
            title_font = ImageFont.load_default()
        
        draw.text((20, 20), "TMH Logo 图标预览", fill=(0, 0, 0), font=title_font)
        
        # 显示不同尺寸的图标
        x, y = 20, 60
        sizes_to_show = [16, 32, 48, 64, 128, 256]
        
        for size in sizes_to_show:
            if x + size + 20 > preview_width:
                x = 20
                y += size + 40
            
            # 创建图标
            icon = self.create_icon_from_logo(size, original_img)
            
            # 粘贴到预览图
            preview.paste(icon, (x, y), icon)
            
            # 添加尺寸标签
            try:
                label_font = ImageFont.truetype("arial.ttf", 12)
            except:
                label_font = ImageFont.load_default()
            
            draw.text((x, y + size + 5), f"{size}x{size}", fill=(0, 0, 0), font=label_font)
            
            x += size + 20
        
        # 保存预览图
        preview_path = self.output_dir / "tmh_logo_preview.png"
        preview.save(preview_path, format='PNG')
        print(f"✓ 预览图已创建: {preview_path}")
        return preview_path

    def convert_logo_to_icons(self):
        """主转换函数"""
        print("开始将TMH_USTB_LOGO转换为图标...")
        
        # 加载原始图片
        original_img = self.load_and_prepare_logo()
        
        # 创建预览图
        preview_path = self.create_preview_image(original_img)
        
        # 生成ICO文件
        ico_file = self.create_ico_file(original_img)
        
        # 生成PNG文件
        png_files = self.create_png_files(original_img)
        
        # 生成ICNS文件
        icns_file = self.create_icns_file(original_img)
        
        print("\n转换完成！")
        print(f"- 预览图: {preview_path}")
        print(f"- Windows ICO: {ico_file}")
        print(f"- PNG文件数量: {len(png_files)}")
        if icns_file:
            print(f"- macOS ICNS: {icns_file}")
        
        return {
            'preview': preview_path,
            'ico': ico_file,
            'png': png_files,
            'icns': icns_file
        }

def main():
    """主函数"""
    try:
        from PIL import Image
    except ImportError:
        print("错误: 需要安装Pillow库")
        print("运行: pip install Pillow")
        return
    
    try:
        converter = LogoToIconConverter()
        converter.convert_logo_to_icons()
    except Exception as e:
        print(f"转换失败: {e}")

if __name__ == "__main__":
    main()
