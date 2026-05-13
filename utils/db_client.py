import os
import yaml
import pymysql
from utils.context import GlobalContext


class DbClient:
    """MySQL数据库客户端，支持多数据库连接和模板渲染"""
    
    _connections = {}  # 连接池：{env: {db_name: connection}}
    
    def __init__(self, context: GlobalContext, env: str = "dev", db_name: str = "default"):
        self.context = context
        self.env = env
        self.db_name = db_name
        self._config = self._load_config()
    
    def _load_config(self) -> dict:
        """加载数据库配置文件"""
        config_path = os.path.join(os.path.dirname(__file__), "../config/database.yml")
        with open(config_path, "r", encoding="utf-8") as f:
            configs = yaml.safe_load(f)
        
        if self.env not in configs:
            raise ValueError(f"环境 {self.env} 不存在于配置文件中")
        
        env_config = configs[self.env]
        if self.db_name not in env_config:
            raise ValueError(f"数据库 {self.db_name} 不存在于环境 {self.env} 的配置中")
        
        return env_config[self.db_name]
    
    def _get_connection(self):
        """获取或创建数据库连接"""
        if self.env not in self._connections:
            self._connections[self.env] = {}
        
        if self.db_name not in self._connections[self.env]:
            cfg = self._config
            conn = pymysql.connect(
                host=cfg["host"],
                port=int(cfg["port"]),
                user=cfg["user"],
                password=cfg["password"],
                database=cfg["database"],
                charset="utf8mb4",
                cursorclass=pymysql.cursors.DictCursor
            )
            self._connections[self.env][self.db_name] = conn
        
        return self._connections[self.env][self.db_name]
    
    def render_sql(self, sql: str) -> str:
        """渲染SQL模板变量"""
        return self.context.render(sql)
    
    def execute(self, sql: str) -> list[dict]:
        """执行SQL查询，支持模板渲染"""
        # 1. 渲染模板变量
        rendered_sql = self.context.render(sql)
        
        # 2. 执行SQL
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(rendered_sql)
                conn.commit()
                return cursor.fetchall()
        except Exception as e:
            conn.rollback()
            raise
    
    def close(self):
        """关闭当前数据库连接"""
        if self.env in self._connections and self.db_name in self._connections[self.env]:
            self._connections[self.env][self.db_name].close()
            del self._connections[self.env][self.db_name]
    
    def close_all(self):
        """关闭当前环境下的所有数据库连接"""
        if self.env in self._connections:
            for conn in self._connections[self.env].values():
                conn.close()
            del self._connections[self.env]
    
    @staticmethod
    def close_all_connections():
        """关闭所有环境下的所有数据库连接"""
        for env_conns in DbClient._connections.values():
            for conn in env_conns.values():
                conn.close()
        DbClient._connections.clear()
