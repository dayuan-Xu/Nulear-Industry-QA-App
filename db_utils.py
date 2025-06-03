# 该模块定义数据库操作。
import os
from psycopg_pool import ConnectionPool
from models.KB import KnowledgeBase
from models.chat import Chat

_connection_pool = None
def get_connection_pool():
    global _connection_pool
    # 单例模式，确保整个应用生命周期内只创建一个连接池实例
    if _connection_pool is None:
        # 使用环境变量获取数据库连接信息，避免硬编码
        db_user = os.getenv("DB_USER", "postgres")
        db_password = os.getenv("DB_PASSWORD", "postgres")
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "5442")
        db_name = os.getenv("DB_NAME", "postgres")
        ssl_mode = os.getenv("DB_SSL_MODE", "disable")

        DB_URI = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}?sslmode={ssl_mode}"

        # 协议：postgresql:// 表示使用 PostgreSQL 协议。
        # 用户信息：postgres:postgres 表示用户名为 postgres，密码也为 postgres。
        # 主机：@localhost 表示数据库位于本地机器。
        # 端口：:5442 表示数据库服务运行在 5442 端口（默认是 5432）。
        # 数据库名：/postgres 表示连接的数据库名为 postgres。
        # SSL 模式：?sslmode=disable 表示禁用 SSL 加密连接。
        try:
            connection_kwargs = {
                "autocommit": True,
                "prepare_threshold": 0,
            }
            _connection_pool = ConnectionPool(
                conninfo=DB_URI,
                max_size=20,
                kwargs=connection_kwargs,
            )
        except Exception as e:
            raise RuntimeError("无法初始化数据库连接池") from e
    return _connection_pool
def verify_user(user):
    pool = get_connection_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT password FROM users WHERE email = %s", (user.email,))
            result = cur.fetchone()
            if result and result[0] == user.password:
                return True
    return False

def get_KBs(email: str):
    pool = get_connection_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT kb_id, name, doc_number, created_time 
                FROM knowledge_bases 
                WHERE user_id = (SELECT id FROM users WHERE email = %s)
            """, (email,))
            rows = cur.fetchall()
            return [KnowledgeBase(kb_id=row[0], name=row[1], doc_number=row[2], created_time=row[3]) for row in rows]

def get_chats(email: str):
    pool = get_connection_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT thread_id, thread_title 
                FROM chats 
                WHERE user_id = (SELECT id FROM users WHERE email = %s)
            """, (email,))
            rows = cur.fetchall()
            return [Chat(thread_id=row[0], thread_title=row[1]) for row in rows]

def insert_chat(new_chat):
    # 访问数据库，插入新对话thread_id和thread_title
    pass

def delete_chat(thread_id: str) -> int:
    # 访问 Postgres 数据库，删除
    # 1、用户的对话表中这一项
    # 2、checkpoints 表中所有 thread_id = 形参 的条目，并返回涉及条目数。
    pool = get_connection_pool()
    deleted_rows = 0
    with pool.connection() as conn:  # 从连接池获取一个连接
        with conn.cursor() as cur:
            # 执行删除操作
            cur.execute("DELETE FROM checkpoints WHERE thread_id = %s RETURNING *", (thread_id,))
            deleted_rows = len(cur.fetchall())  # 统计影响的行数

    return deleted_rows

def update_chat_title(chat, new_title):
    # 访问数据库，根据thread_id和st.session_state.new_chat_title更新对话标题————一个二值表thread_id和thread_title
    pass

