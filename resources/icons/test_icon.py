#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试图标生成脚本
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from create_icon import TMHIconGenerator

def test_icon():
    """生成测试图标"""
    generator = TMHIconGenerator()
    
    # 生成一个256x256的测试图标
    img = generator.create_base_icon(256)
    test_path = generator.output_dir / "test_tmh_icon.png"
    img.save(test_path, format='PNG')
    print(f"测试图标已生成: {test_path}")
    
    # 生成完整的图标集
    generator.generate_all_icons()

if __name__ == "__main__":
    test_icon()
