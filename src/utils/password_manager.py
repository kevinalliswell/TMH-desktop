import hashlib
import json
import os
import secrets

from src.utils.logger import get_logger
from src.utils.path_manager import PathManager

logger = get_logger(__name__)

_PBKDF2_ITERATIONS = 600_000
_DEFAULT_PASSWORD = "1952"


def _hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    """Hash a password with PBKDF2-HMAC-SHA256. Returns (hash_hex, salt_hex)."""
    if salt is None:
        salt = secrets.token_bytes(32)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, _PBKDF2_ITERATIONS)
    return dk.hex(), salt.hex()


def _verify_hash(password: str, stored_hash: str, stored_salt: str) -> bool:
    """Verify a password against a stored hash using constant-time comparison."""
    salt = bytes.fromhex(stored_salt)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, _PBKDF2_ITERATIONS)
    return secrets.compare_digest(dk.hex(), stored_hash)


class PasswordManager:
    """密码管理工具"""

    def __init__(self, config_file: str | None = None):
        if config_file is None:
            config_file = PathManager.get_config_path('password_config.json')
        self.config_file = config_file
        self._password_hash: str = ""
        self._password_salt: str = ""
        # Initialize with default password hash
        self._password_hash, self._password_salt = _hash_password(_DEFAULT_PASSWORD)
        self.load_config()

    def load_config(self) -> None:
        """加载配置，自动迁移明文密码到哈希格式"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)

                if "password_hash" in config and "password_salt" in config:
                    # New hashed format
                    self._password_hash = config["password_hash"]
                    self._password_salt = config["password_salt"]
                elif "admin_password" in config:
                    # Legacy plaintext format — auto-migrate
                    plaintext = config["admin_password"]
                    self._password_hash, self._password_salt = _hash_password(plaintext)
                    logger.info("密码配置已从明文格式迁移到哈希格式")
                    self.save_config()
        except Exception as e:
            logger.error(f"加载密码配置失败: {e}")

    def save_config(self) -> None:
        """保存配置（仅存储哈希和盐值）"""
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump({
                    "password_hash": self._password_hash,
                    "password_salt": self._password_salt,
                }, f, indent=2)
        except Exception as e:
            logger.error(f"保存密码配置失败: {e}")

    def verify_password(self, password: str) -> bool:
        """验证密码"""
        return _verify_hash(password, self._password_hash, self._password_salt)

    def change_password(self, old_password: str, new_password: str) -> bool:
        """修改密码"""
        if self.verify_password(old_password):
            self._password_hash, self._password_salt = _hash_password(new_password)
            self.save_config()
            return True
        return False
