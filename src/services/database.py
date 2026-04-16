# src/services/database.py
import sqlite3
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
import json

from src.utils.path_manager import PathManager
from src.utils.logger import get_logger

database_path = PathManager.get_data_path('experiments.db')

logger = get_logger(__name__)


@dataclass
class ExperimentData:
    """实验数据模型"""
    experiment_id: str
    experiment_name: str
    sample_name: str
    sample_weight: float
    start_time: str
    end_time: str = None
    description: str = ""
    operator: str = ""
    experiment_type: str = ""
    analysis_results_json: Optional[str] = None
    timestamps: List[str] = None
    temperatures: List[float] = None
    weights: List[float] = None
    weight_losses: List[float] = None
    gas_flows: Dict[str, List[float]] = None

    def __post_init__(self):
        """初始化可选字段"""
        if self.timestamps is None:
            self.timestamps = []
        if self.temperatures is None:
            self.temperatures = []
        if self.weights is None:
            self.weights = []
        if self.weight_losses is None:
            self.weight_losses = []
        if self.gas_flows is None:
            self.gas_flows = {
                "CO": [], "CO2": [], "N2": [], "H2": []
            }


@dataclass
class ExperimentConfig:
    """实验配置"""
    target_temperature: float = 900.0
    temperature_tolerance: float = 10.0
    temperature_stability: float = 5.0
    min_experiment_duration: int = 180  # minutes
    target_gas_flow: float = 15.0
    flow_tolerance: float = 0.5


class ExperimentDatabase:
    """实验数据库管理"""

    def __init__(self, db_path: str = database_path):
        """初始化数据库管理器"""
        self.db_path = db_path
        # 确保数据库目录存在
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.init_database()

    def init_database(self):
        """初始化数据库"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 创建实验表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS experiments (
                    experiment_id TEXT PRIMARY KEY,
                    experiment_name TEXT NOT NULL,
                    sample_name TEXT NOT NULL,
                    sample_weight REAL NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    description TEXT,
                    operator TEXT,
                    experiment_type TEXT,
                    analysis_results_json TEXT,
                    created_at TEXT NOT NULL
                )
            """)

            # 检查并添加 analysis_results_json 列 (如果不存在)
            try:
                cursor.execute("PRAGMA table_info(experiments);")
                columns = [info[1] for info in cursor.fetchall()]
                if 'analysis_results_json' not in columns:
                    cursor.execute("ALTER TABLE experiments ADD COLUMN analysis_results_json TEXT;")
                    logger.info("Added missing 'analysis_results_json' column to 'experiments' table.")
            except sqlite3.Error as e:
                logger.error(f"Error checking/adding 'analysis_results_json' column: {e}")

            # 创建实时数据表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS experiment_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    experiment_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    experiment_duration TEXT,
                    temperature REAL NOT NULL,
                    weight REAL NOT NULL,
                    weight_loss REAL NOT NULL,
                    co_flow REAL NOT NULL,
                    co2_flow REAL NOT NULL,
                    n2_flow REAL NOT NULL,
                    h2_flow REAL NOT NULL,
                    experiment_status TEXT,
                    system_message TEXT,
                    FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id)
                )
            """)
            
            # 检查并添加新字段（如果不存在）
            try:
                cursor.execute("PRAGMA table_info(experiment_data);")
                columns = [info[1] for info in cursor.fetchall()]
                
                if 'experiment_duration' not in columns:
                    cursor.execute("ALTER TABLE experiment_data ADD COLUMN experiment_duration TEXT;")
                    logger.info("Added 'experiment_duration' column to 'experiment_data' table.")
                
                if 'experiment_status' not in columns:
                    cursor.execute("ALTER TABLE experiment_data ADD COLUMN experiment_status TEXT;")
                    logger.info("Added 'experiment_status' column to 'experiment_data' table.")
                
                if 'system_message' not in columns:
                    cursor.execute("ALTER TABLE experiment_data ADD COLUMN system_message TEXT;")
                    logger.info("Added 'system_message' column to 'experiment_data' table.")
                    
            except sqlite3.Error as e:
                logger.error(f"Error checking/adding new columns to 'experiment_data' table: {e}")

            # 创建索引 (确保表已存在后再创建索引)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_experiments_name
                ON experiments(experiment_name)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_experiment_data_timestamp
                ON experiment_data(experiment_id, timestamp)
            """)

    def create_experiment(self, data: ExperimentData) -> bool:
        """创建实验记录"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO experiments (
                        experiment_id, experiment_name, sample_name, sample_weight,
                        start_time, end_time, description, operator, experiment_type,
                        analysis_results_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    data.experiment_id,
                    data.experiment_name,
                    data.sample_name,
                    data.sample_weight,
                    data.start_time,
                    data.end_time,
                    data.description,
                    data.operator,
                    data.experiment_type,
                    data.analysis_results_json,
                    datetime.now().isoformat()
                ))
                return True
        except sqlite3.IntegrityError as e:
            logger.error(f"实验ID重复: {e}")
            return False
        except sqlite3.DatabaseError as e:
            logger.error(f"数据库操作失败: {e}")
            return False
        except Exception as e:
            logger.error(f"创建实验记录失败，错误信息：{e}")
            return False

    def update_experiment(self, experiment_id: str, end_time: str) -> bool:
        """更新实验记录的结束时间"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE experiments 
                    SET end_time = ?
                    WHERE experiment_id = ?
                """, (end_time, experiment_id))
                return True
        except Exception as e:
            logger.error(f"更新实验记录失败: {e}")
            return False

    def update_experiment_analysis_results(self, experiment_id: str, analysis_results: dict) -> bool:
        """更新实验记录的分析结果"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                analysis_results_json = json.dumps(analysis_results)
                logger.debug(f"Saving analysis_results_json to DB for exp {experiment_id}: >>>{analysis_results_json}<<<")
                cursor.execute("""
                    UPDATE experiments 
                    SET analysis_results_json = ?
                    WHERE experiment_id = ?
                """, (analysis_results_json, experiment_id))
                logger.info(f"成功更新实验 {experiment_id} 的分析结果到数据库。")
                return True
        except Exception as e:
            logger.error(f"更新实验 {experiment_id} 的分析结果失败: {e}")
            return False

    def add_experiment_data(self, experiment_id: str, data: dict) -> bool:
        """添加实验数据（增强版：超时设置和重试机制）"""
        max_retries = 3
        retry_delay = 0.5
        
        for attempt in range(max_retries):
            try:
                # 使用独立连接并设置超时，避免锁表
                with sqlite3.connect(self.db_path, timeout=10.0) as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO experiment_data (
                            experiment_id, timestamp, experiment_duration, temperature,
                            weight, weight_loss, co_flow, co2_flow,
                            n2_flow, h2_flow, experiment_status, system_message
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        experiment_id,
                        data['timestamp'],
                        data.get('experiment_duration', ''),
                        data['temperature'],
                        data['weight'],
                        data['weight_loss'],
                        data['co_flow'],
                        data['co2_flow'],
                        data['n2_flow'],
                        data['h2_flow'],
                        data.get('experiment_status', ''),
                        data.get('system_message', '')
                    ))
                    return True
            except sqlite3.OperationalError as e:
                if "locked" in str(e).lower() and attempt < max_retries - 1:
                    logger.warning(f"数据库被锁定，重试 ({attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"添加实验数据失败: {e}")
                    return False
            except Exception as e:
                logger.error(f"添加实验数据失败: {e}")
                return False
        
        return False

    def get_experiment(self, experiment_id: str) -> Optional[ExperimentData]:
        """获取实验记录"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM experiments 
                    WHERE experiment_id = ?
                """, (experiment_id,))
                row = cursor.fetchone()
                if row:
                    return ExperimentData(
                        experiment_id=row[0],
                        experiment_name=row[1],
                        sample_name=row[2],
                        sample_weight=row[3],
                        start_time=row[4],
                        end_time=row[5],
                        description=row[6],
                        operator=row[7],
                        experiment_type=row[8],
                        analysis_results_json=row[9]
                    )
                return None
        except Exception as e:
            logger.error(f"获取实验记录失败: {e}")
            return None

    def get_experiment_data(self, experiment_id: str) -> List[dict]:
        """获取实验数据"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 首先获取表结构信息
                cursor.execute("PRAGMA table_info(experiment_data);")
                columns_info = cursor.fetchall()
                column_names = [col[1] for col in columns_info]
                
                # 构建字段映射字典
                column_mapping = {name: idx for idx, name in enumerate(column_names)}
                
                cursor.execute("""
                    SELECT * FROM experiment_data 
                    WHERE experiment_id = ?
                    ORDER BY timestamp
                """, (experiment_id,))
                rows = cursor.fetchall()
                
                result = []
                for row in rows:
                    data_point = {}
                    
                    # 安全地获取每个字段
                    data_point['timestamp'] = row[column_mapping.get('timestamp', 2)] if len(row) > column_mapping.get('timestamp', 2) else ''
                    data_point['experiment_duration'] = row[column_mapping.get('experiment_duration', 3)] if len(row) > column_mapping.get('experiment_duration', 3) else ''
                    data_point['temperature'] = float(row[column_mapping.get('temperature', 4)]) if len(row) > column_mapping.get('temperature', 4) and row[column_mapping.get('temperature', 4)] is not None else 0.0
                    data_point['weight'] = float(row[column_mapping.get('weight', 5)]) if len(row) > column_mapping.get('weight', 5) and row[column_mapping.get('weight', 5)] is not None else 0.0
                    data_point['weight_loss'] = float(row[column_mapping.get('weight_loss', 6)]) if len(row) > column_mapping.get('weight_loss', 6) and row[column_mapping.get('weight_loss', 6)] is not None else 0.0
                    data_point['co_flow'] = float(row[column_mapping.get('co_flow', 7)]) if len(row) > column_mapping.get('co_flow', 7) and row[column_mapping.get('co_flow', 7)] is not None else 0.0
                    data_point['co2_flow'] = float(row[column_mapping.get('co2_flow', 8)]) if len(row) > column_mapping.get('co2_flow', 8) and row[column_mapping.get('co2_flow', 8)] is not None else 0.0
                    data_point['n2_flow'] = float(row[column_mapping.get('n2_flow', 9)]) if len(row) > column_mapping.get('n2_flow', 9) and row[column_mapping.get('n2_flow', 9)] is not None else 0.0
                    data_point['h2_flow'] = float(row[column_mapping.get('h2_flow', 10)]) if len(row) > column_mapping.get('h2_flow', 10) and row[column_mapping.get('h2_flow', 10)] is not None else 0.0
                    data_point['experiment_status'] = row[column_mapping.get('experiment_status', 11)] if len(row) > column_mapping.get('experiment_status', 11) else ''
                    data_point['system_message'] = row[column_mapping.get('system_message', 12)] if len(row) > column_mapping.get('system_message', 12) else ''
                    
                    result.append(data_point)
                
                logger.debug(f"成功获取实验 {experiment_id} 的 {len(result)} 个数据点")
                return result
                
        except Exception as e:
            logger.error(f"获取实验数据失败: {e}")
            return []

    def get_all_experiments(self) -> List[ExperimentData]:
        """获取所有实验记录"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM experiments 
                    ORDER BY start_time DESC
                """)
                rows = cursor.fetchall()
                experiments = []
                for row in rows:
                    experiments.append(ExperimentData(
                        experiment_id=row[0],
                        experiment_name=row[1],
                        sample_name=row[2],
                        sample_weight=row[3],
                        start_time=row[4],
                        end_time=row[5],
                        description=row[6],
                        operator=row[7],
                        experiment_type=row[8],
                        analysis_results_json=row[9]
                    ))
                return experiments
        except Exception as e:
            logger.error(f"获取实验记录失败: {e}")
            return []

    def delete_experiment(self, experiment_id: str) -> bool:
        """删除实验记录"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # 删除实验数据
                cursor.execute("""
                    DELETE FROM experiment_data 
                    WHERE experiment_id = ?
                """, (experiment_id,))
                # 删除实验记录
                cursor.execute("""
                    DELETE FROM experiments 
                    WHERE experiment_id = ?
                """, (experiment_id,))
                return True
        except Exception as e:
            logger.error(f"删除实验记录失败: {e}")
            return False

    def validate_database_integrity(self) -> dict:
        """验证数据库完整性"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 检查实验表
                cursor.execute("SELECT COUNT(*) FROM experiments")
                experiment_count = cursor.fetchone()[0]
                
                # 检查数据表
                cursor.execute("SELECT COUNT(*) FROM experiment_data")
                data_count = cursor.fetchone()[0]
                
                # 检查孤立的数据记录
                cursor.execute("""
                    SELECT COUNT(*) FROM experiment_data 
                    WHERE experiment_id NOT IN (SELECT experiment_id FROM experiments)
                """)
                orphaned_data = cursor.fetchone()[0]
                
                # 检查表结构
                cursor.execute("PRAGMA table_info(experiments)")
                experiment_columns = [col[1] for col in cursor.fetchall()]
                
                cursor.execute("PRAGMA table_info(experiment_data)")
                data_columns = [col[1] for col in cursor.fetchall()]
                
                return {
                    'experiment_count': experiment_count,
                    'data_count': data_count,
                    'orphaned_data': orphaned_data,
                    'experiment_columns': experiment_columns,
                    'data_columns': data_columns,
                    'is_valid': orphaned_data == 0
                }
                
        except Exception as e:
            logger.error(f"验证数据库完整性失败: {e}")
            return {'is_valid': False, 'error': str(e)}

    def repair_database(self) -> bool:
        """修复数据库问题"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 删除孤立的数据记录
                cursor.execute("""
                    DELETE FROM experiment_data 
                    WHERE experiment_id NOT IN (SELECT experiment_id FROM experiments)
                """)
                deleted_orphans = cursor.rowcount
                
                # 重建索引
                cursor.execute("DROP INDEX IF EXISTS idx_experiments_name")
                cursor.execute("DROP INDEX IF EXISTS idx_experiment_data_timestamp")
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_experiments_name
                    ON experiments(experiment_name)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_experiment_data_timestamp
                    ON experiment_data(experiment_id, timestamp)
                """)
                
                # 执行VACUUM优化
                cursor.execute("VACUUM")
                
                logger.info(f"数据库修复完成，删除了 {deleted_orphans} 条孤立记录")
                return True
                
        except Exception as e:
            logger.error(f"修复数据库失败: {e}")
            return False
