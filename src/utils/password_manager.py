import hashlib
import json
import os
from typing import Optional

from src.utils.path_manager import PathManager


class PasswordManager:
    """密码管理工具"""
    
    def __init__(self, config_file: str = PathManager.get_config_path('password_config.json')):
        self.config_file = config_file
        self.admin_password = "1952"  # 默认密码
        self.load_config()
        
    def load_config(self):
        """加载配置"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.admin_password = config.get("admin_password", "1952")
        except Exception as e:
            print(f"加载密码配置失败: {e}")
            
    def save_config(self):
        """保存配置"""
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump({"admin_password": self.admin_password}, f)
        except Exception as e:
            print(f"保存密码配置失败: {e}")
            
    def verify_password(self, password: str) -> bool:
        """验证密码"""
        return password == self.admin_password
        
    def change_password(self, old_password: str, new_password: str) -> bool:
        """修改密码"""
        if self.verify_password(old_password):
            self.admin_password = new_password
            self.save_config()
            return True
        return False 