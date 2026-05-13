import os
import yaml
import pymysql
from utils.context import GlobalContext


class DbClient:
    """MySQL数据库客户端，支持模板渲染和连接池"""
    
    _connections = {}  # 连接池：{env: connection}
    
    def __init__(self, context: GlobalContext, env: str = "dev"):
        self.context = context
        self.env = env
        self._config = self._load_config()
    
    def _load_config(self) -> dict:
        """加载数据库配置文件"""
        config_path = os.path.join(os.path.dirname(__file__), "../config/database.yml")
        with open(config_path, "r", encoding="utf-8") as f:
            configs = yaml.safe_load(f)
        
        if self.env not in configs:
            raise ValueError(f"环境 {self.env} 不存在于配置文件中")
        
        return configs[self.env]
    
    def _get_connection(self):
        """获取或创建数据库连接"""
        if self.env not in self._connections:
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
            self._connections[self.env] = conn
        return self._connections[self.env]
    
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
        """关闭数据库连接"""
        if self.env in self._connections:
            self._connections[self.env].close()
            del self._connections[self.env]
    
    @staticmethod
    def close_all():
        """关闭所有连接"""
        for conn in DbClient._connections.values():
            conn.close()
        DbClient._connections.clear()