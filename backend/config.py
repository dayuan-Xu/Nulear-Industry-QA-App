import os
from pathlib import Path
from dotenv import load_dotenv

# ========== 调试：打印当前工作目录和 .env 路径 ==========
print(f"🟢 当前工作目录: {Path.cwd()}")
env_path = Path(__file__).parent.parent / '.env'
print(f"🟢 尝试加载 .env 文件: {env_path} (存在? {env_path.exists()})")

# 强制加载 .env，覆盖已有环境变量
load_dotenv(dotenv_path=env_path, override=True)

class Config:
    # 数据库配置（读取环境变量，若不存在则使用硬编码默认值）
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5442")
    DB_NAME = os.getenv("DB_NAME", "postgres")
    DB_SSL_MODE = os.getenv("DB_SSL_MODE", "disable")

    # ========== 打印最终读取到的配置 ==========
    print(f"🔧 最终数据库配置: {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME} (SSL={DB_SSL_MODE})")
    print(f"🔧 DB_HOST 原始值: {repr(os.getenv('DB_HOST'))}")

    # 文件存储路径
    BASE_DIR = Path(__file__).parent.parent
    ALL_USERS_FILES_DIR = BASE_DIR / "all_users_files"

    # API 配置
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("API_PORT", "8001"))