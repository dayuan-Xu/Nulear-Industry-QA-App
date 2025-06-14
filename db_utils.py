# 该模块定义数据库操作。
import atexit
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
def get_user_id(email):
    # 访问数据库，根据email获取用户id
    pool = get_connection_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE email = %s", (email,))
            result = cur.fetchone()
            if result:
                return result[0]
    return None
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

def insert_chat(new_chat: Chat,user_id:str):
    # 访问数据库chats:thread_id(主码）、thread_title、creadted_time（timestamp without time zone)、user_id，插入新对话thread_id和thread_title
    pool = get_connection_pool()
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO chats (thread_id, thread_title, created_time, user_id) VALUES (%s, %s, NOW(), %s)",
                            (new_chat["thread_id"], new_chat["thread_title"], user_id))
                conn.commit()  # 提交事务
                return 1  # 插入成功
    except Exception as e:
        # 可根据具体异常做更细粒度的处理
        print(f"Error inserting chat: {e}")

def delete_chat(thread_id: str) -> int:
    pool = get_connection_pool()
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                # 删除 chats 表中的记录
                cur.execute("DELETE FROM chats WHERE thread_id = %s", (thread_id,))
                # 删除 checkpoints 表中的记录
                cur.execute("DELETE FROM checkpoints WHERE thread_id = %s", (thread_id,))
                conn.commit()  # 提交事务
                return 1  # 成功
    except Exception as e:
        # 可根据具体异常做更细粒度的处理
        print(f"Error deleting chat: {e}")
        return 0  # 失败

def update_chat_title(chat, new_title):
    # 访问数据库chat表，根据thread_id（主码）和st.session_state.new_chat_title更新thread_title
    pool = get_connection_pool()
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE chats SET thread_title = %s WHERE thread_id = %s", (new_title, chat["thread_id"]))
                conn.commit()  # 提交事务
                return 1  # 成功
    except Exception as e:
        # 可根据具体异常做更细粒度的处理
        print(f"Error updating chat title: {e}")
        return 0  # 失败


def close_connection_pool():
    global _connection_pool
    if _connection_pool is not None:
        _connection_pool.close()
        print("Database connection pool closed.")
# 注册退出钩子
atexit.register(close_connection_pool)