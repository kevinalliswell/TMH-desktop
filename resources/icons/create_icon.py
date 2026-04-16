#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TMH 系统图标生成脚本
生成不同尺寸的应用图标
"""

from PIL import Image, ImageDraw, ImageFont
import os
from pathlib import Path

class TMHIconGenerator:
    def __init__(self):
        self.output_dir = Path(__file__).parent
        self.sizes = [16, 24, 32, 48, 64, 128, 256, 512]
        
        # 颜色方案 - 工业风格
        self.colors = {
            'primary': '#2C3E50',      # 深蓝灰色
            'secondary': '#E74C3C',    # 红色 - 象征高温
            'accent': '#F39C12',       # 橙色 - 象征金属光泽
            'background': '#ECF0F1',   # 浅灰色背景
            'text': '#FFFFFF'          # 白色文字
        }

    def create_base_icon(self, size):
        """创建基础图标"""
        # 创建圆角正方形背景
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # 绘制圆角背景
        corner_radius = size // 8
        self._draw_rounded_rectangle(
            draw, (0, 0, size, size), 
            corner_radius, self.colors['primary']
        )
        
        # 绘制高炉背景图案
        self._draw_blast_furnace_background(draw, size)
        
        # 绘制TMH文字 - 所有尺寸都显示
        if size >= 16:
            self._draw_text(draw, size)
        
        # 绘制装饰元素
        self._draw_decorative_elements(draw, size)
        
        return img

    def _draw_rounded_rectangle(self, draw, bbox, radius, fill):
        """绘制圆角矩形"""
        x1, y1, x2, y2 = bbox
        
        # 绘制圆角
        draw.pieslice([x1, y1, x1 + 2*radius, y1 + 2*radius], 180, 270, fill=fill)
        draw.pieslice([x2 - 2*radius, y1, x2, y1 + 2*radius], 270, 360, fill=fill)
        draw.pieslice([x1, y2 - 2*radius, x1 + 2*radius, y2], 90, 180, fill=fill)
        draw.pieslice([x2 - 2*radius, y2 - 2*radius, x2, y2], 0, 90, fill=fill)
        
        # 绘制矩形部分
        draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
        draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)

    def _draw_blast_furnace_background(self, draw, size):
        """绘制高炉背景图案 - 参考真实高炉造型"""
        if size < 32:
            return  # 小尺寸图标不绘制复杂背景
        
        # 使用半透明的线条，不影响TMH文字的突出显示
        line_color = (*self._hex_to_rgb(self.colors['accent']), 60)  # 稍微提高透明度以便可见
        fill_color = (*self._hex_to_rgb(self.colors['accent']), 20)  # 很淡的填充色
        line_width = max(size // 128, 1)
        
        center_x = size // 2
        center_y = size // 2
        
        # 根据参考图设计高炉轮廓
        # 高炉总高度
        furnace_height = size // 1.8
        
        # 关键尺寸
        base_width = size // 6        # 底座宽度
        belly_width = size // 4.5     # 炉腰最宽处
        throat_width = size // 8      # 炉喉宽度
        top_width = size // 6         # 炉顶宽度
        
        # 关键Y坐标点（从上到下）
        furnace_top = center_y - furnace_height // 2
        throat_y = furnace_top + furnace_height // 8      # 炉喉位置
        belly_y = center_y + furnace_height // 6          # 炉腰位置  
        furnace_bottom = center_y + furnace_height // 2
        
        if size >= 64:
            # 绘制真实高炉轮廓
            points = []
            
            # 左侧轮廓点（从上到下）
            points.extend([
                (center_x - top_width // 2, furnace_top),        # 炉顶左
                (center_x - throat_width // 2, throat_y),        # 炉喉左
                (center_x - belly_width // 2, belly_y),          # 炉腰左
                (center_x - base_width // 2, furnace_bottom),    # 底座左
            ])
            
            # 右侧轮廓点（从下到上）
            points.extend([
                (center_x + base_width // 2, furnace_bottom),    # 底座右
                (center_x + belly_width // 2, belly_y),          # 炉腰右
                (center_x + throat_width // 2, throat_y),        # 炉喉右
                (center_x + top_width // 2, furnace_top),        # 炉顶右
            ])
            
            # 绘制高炉轮廓（填充）
            if size >= 128:
                draw.polygon(points, fill=fill_color[:3], outline=line_color[:3], width=line_width)
            else:
                draw.polygon(points, outline=line_color[:3], width=line_width)
            
            # 绘制炉顶细节
            if size >= 128:
                # 炉顶管道
                pipe_width = size // 32
                pipe_height = size // 16
                draw.rectangle([
                    center_x - pipe_width // 2, 
                    furnace_top - pipe_height,
                    center_x + pipe_width // 2, 
                    furnace_top
                ], fill=line_color[:3])
                
                # 炉腰标志线
                belly_line_length = belly_width // 2
                draw.line([
                    center_x - belly_line_length, belly_y,
                    center_x + belly_line_length, belly_y
                ], fill=line_color[:3], width=line_width)
        
        elif size >= 32:
            # 简化版本 - 基本轮廓
            # 绘制简化的高炉形状
            left_points = [
                (center_x - top_width // 2, furnace_top),
                (center_x - throat_width // 2, throat_y),
                (center_x - belly_width // 2, belly_y),
                (center_x - base_width // 2, furnace_bottom)
            ]
            
            right_points = [
                (center_x + top_width // 2, furnace_top),
                (center_x + throat_width // 2, throat_y),
                (center_x + belly_width // 2, belly_y),
                (center_x + base_width // 2, furnace_bottom)
            ]
            
            # 绘制左右轮廓线
            for i in range(len(left_points) - 1):
                draw.line([left_points[i], left_points[i+1]], fill=line_color[:3], width=line_width)
                draw.line([right_points[i], right_points[i+1]], fill=line_color[:3], width=line_width)
            
            # 绘制顶部和底部
            draw.line([left_points[0], right_points[0]], fill=line_color[:3], width=line_width)
            draw.line([left_points[-1], right_points[-1]], fill=line_color[:3], width=line_width)

    def _draw_text(self, draw, size):
        """绘制TMH文字 - 突出显示"""
        # 根据图标大小调整字体大小，让TMH更突出
        if size >= 256:
            font_size = size // 4  # 大尺寸图标使用更大字体
        elif size >= 128:
            font_size = size // 3.5
        elif size >= 64:
            font_size = size // 3
        elif size >= 32:
            font_size = size // 2.5
        else:
            font_size = max(size // 2, 8)
            
        try:
            # 尝试使用粗体字体
            font = ImageFont.truetype("arialbd.ttf", font_size)  # 粗体Arial
        except:
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except:
                font = ImageFont.load_default()
        
        text = "TMH"
        
        # 计算文字位置 - 居中显示
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        x = (size - text_width) // 2
        y = (size - text_height) // 2
        
        # 绘制多层阴影效果，增强立体感
        shadow_offset = max(size // 64, 1)
        for i in range(3, 0, -1):
            shadow_x = x + shadow_offset * i
            shadow_y = y + shadow_offset * i
            alpha = 60 - i * 15  # 逐渐减淡的阴影
            draw.text((shadow_x, shadow_y), text, font=font, fill=(0, 0, 0, alpha))
        
        # 绘制外描边
        stroke_width = max(size // 128, 1)
        if size >= 32:
            for dx in range(-stroke_width, stroke_width + 1):
                for dy in range(-stroke_width, stroke_width + 1):
                    if dx != 0 or dy != 0:
                        draw.text((x + dx, y + dy), text, font=font, fill=self.colors['primary'])
        
        # 绘制主文字 - 使用更亮的颜色
        draw.text((x, y), text, font=font, fill=self.colors['text'])
        
        # 为大尺寸图标添加高光效果
        if size >= 64:
            highlight_y = y - font_size // 8
            draw.text((x, highlight_y), text, font=font, fill=(255, 255, 255, 100))

    def _draw_decorative_elements(self, draw, size):
        """绘制装饰元素 - 简洁的设计，不抢夺TMH的视觉焦点"""
        margin = size // 16
        
        # 只在较大尺寸添加微妙的装饰元素
        if size >= 128:
            # 在四个角添加小的装饰点，代表测试点
            dot_size = size // 32
            alpha = 100  # 半透明
            
            # 左上角
            draw.ellipse(
                [margin, margin, margin + dot_size, margin + dot_size],
                fill=(*self._hex_to_rgb(self.colors['accent']), alpha)
            )
            
            # 右上角
            draw.ellipse(
                [size - margin - dot_size, margin, size - margin, margin + dot_size],
                fill=(*self._hex_to_rgb(self.colors['secondary']), alpha)
            )
            
            # 左下角
            draw.ellipse(
                [margin, size - margin - dot_size, margin + dot_size, size - margin],
                fill=(*self._hex_to_rgb(self.colors['secondary']), alpha)
            )
            
            # 右下角
            draw.ellipse(
                [size - margin - dot_size, size - margin - dot_size, size - margin, size - margin],
                fill=(*self._hex_to_rgb(self.colors['accent']), alpha)
            )
        
        elif size >= 64:
            # 中等尺寸只在底部添加简单的装饰线
            line_width = size // 32
            line_length = size // 3
            line_x = (size - line_length) // 2
            line_y = size - margin - line_width
            
            draw.rectangle(
                [line_x, line_y, line_x + line_length, line_y + line_width],
                fill=self.colors['accent']
            )
    
    def _hex_to_rgb(self, hex_color):
        """将十六进制颜色转换为RGB元组"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def create_ico_file(self):
        """创建Windows ICO文件"""
        images = []
        for size in [16, 24, 32, 48, 64, 128, 256]:
            img = self.create_base_icon(size)
            images.append(img)
        
        ico_path = self.output_dir / "tmh_icon.ico"
        images[0].save(ico_path, format='ICO', sizes=[(img.width, img.height) for img in images])
        print(f"✓ ICO文件已创建: {ico_path}")
        return ico_path

    def create_png_files(self):
        """创建PNG文件"""
        png_files = []
        for size in self.sizes:
            img = self.create_base_icon(size)
            png_path = self.output_dir / f"tmh_icon_{size}x{size}.png"
            img.save(png_path, format='PNG')
            png_files.append(png_path)
            print(f"✓ PNG文件已创建: {png_path}")
        
        # 创建标准尺寸的主图标
        main_icon = self.create_base_icon(256)
        main_path = self.output_dir / "tmh_icon.png"
        main_icon.save(main_path, format='PNG')
        print(f"✓ 主图标已创建: {main_path}")
        
        return png_files

    def create_icns_file(self):
        """创建macOS ICNS文件 (需要pillow-heif或其他库支持)"""
        try:
            from PIL import IcnsImagePlugin
            
            # 创建不同尺寸的图标
            images = {}
            icns_sizes = [16, 32, 64, 128, 256, 512]
            
            for size in icns_sizes:
                img = self.create_base_icon(size)
                images[f'{size}x{size}'] = img
            
            # 保存为ICNS (这里简化处理，实际可能需要特殊库)
            icns_path = self.output_dir / "tmh_icon.icns"
            main_img = self.create_base_icon(512)
            main_img.save(icns_path, format='ICNS')
            print(f"✓ ICNS文件已创建: {icns_path}")
            return icns_path
            
        except Exception as e:
            print(f"⚠ ICNS文件创建失败 (需要额外依赖): {e}")
            return None

    def generate_all_icons(self):
        """生成所有格式的图标"""
        print("开始生成TMH应用图标...")
        print(f"输出目录: {self.output_dir}")
        
        # 确保输出目录存在
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成ICO文件 (Windows)
        ico_file = self.create_ico_file()
        
        # 生成PNG文件
        png_files = self.create_png_files()
        
        # 生成ICNS文件 (macOS)
        icns_file = self.create_icns_file()
        
        print("\n图标生成完成！")
        print(f"- Windows ICO: {ico_file}")
        print(f"- PNG文件数量: {len(png_files)}")
        if icns_file:
            print(f"- macOS ICNS: {icns_file}")
        
        return {
            'ico': ico_file,
            'png': png_files,
            'icns': icns_file
        }

def main():
    """主函数"""
    # 检查Pillow库
    try:
        from PIL import Image
    except ImportError:
        print("错误: 需要安装Pillow库")
        print("运行: pip install Pillow")
        return
    
    generator = TMHIconGenerator()
    generator.generate_all_icons()

if __name__ == "__main__":
    main()
