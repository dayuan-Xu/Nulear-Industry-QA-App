import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class Config:
    # 数据库配置
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5442")
    DB_NAME = os.getenv("DB_NAME", "postgres")
    DB_SSL_MODE = os.getenv("DB_SSL_MODE", "disable")

    # 文件存储配置
    BASE_DATA_DIR = os.getenv("BASE_DATA_DIR", "all_users_files")

    # API配置
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("API_PORT", "8000"))

    # 向量数据库配置
    QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
    QDRANT_COLLECTION_PREFIX = os.getenv("QDRANT_COLLECTION_PREFIX", "kb_")

    @classmethod
    def get_db_uri(cls):
        return f"postgresql://{cls.DB_USER}:{cls.DB_PASSWORD}@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}?sslmode={cls.DB_SSL_MODE}"