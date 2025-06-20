# 该模块定义数据库操作。
import atexit
import os
from psycopg_pool import ConnectionPool
from models.KB import KnowledgeBase
from models.chat import Chat
from datetime import timezone
import pytz

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
                max_size=8,
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
def get_KBs(user_id):
    #print("get_KBs开始执行")
    pool = get_connection_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM knowledge_bases WHERE user_id = %s", (user_id,))
            rows = cur.fetchall()
            #print(f"get_KBs找到了{len(rows)}行结果")
            return [KnowledgeBase(kb_id=row[0], name=row[1], doc_number=row[2], created_time=row[3]) for row in rows]

def insert_KB(name,user_id):
    pool = get_connection_pool()
    try :
        with pool.connection() as connection:
            with connection.cursor() as cur:
                cur.execute("""
                    INSERT INTO knowledge_bases (name, user_id) VALUES (%s, %s)
                """, (name, user_id))
                connection.commit()
                return 1
    except Exception as e:
        print(f"Error inserting new KB:{e}")
def update_KB_name(kb_id: int, new_name: str):
    pool = get_connection_pool()
    try:
        with pool.connection() as connection:
            with connection.cursor() as cur:
                cur.execute("""
                    UPDATE knowledge_bases SET name = %s WHERE kb_id = %s
                """, (new_name, kb_id))
                connection.commit()
                return True
    except Exception as e:
        print(f"Error updating KB name:{e}")
        return False
def update_KB(kb_id: int, new_doc_number:int):
    pool = get_connection_pool()
    try:
        with pool.connection() as connection:
            with connection.cursor() as cur:
                cur.execute("""
                    UPDATE knowledge_bases SET doc_number = %s WHERE kb_id = %s
                """, (new_doc_number, kb_id))
                connection.commit()
                return True
    except Exception as e:
        print(f"Error updating KB doc_number:{e}")
        return False
def delete_KB(kb_id: int):
    pool = get_connection_pool()
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM knowledge_bases WHERE kb_id = %s", (kb_id,))
                conn.commit()
                return True
    except Exception as e:
        # 可根据具体异常做更细粒度的处理
        print(f"Error deleting KB: {e}")
        return False
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

def format_utc_to_local(utc_time):
    """
    接收一个 datetime 对象（可能无时区信息）
    返回格式化为本地时间（CST）的字符串
    """
    if utc_time.tzinfo is None:
        # 如果没有时区信息，默认设为 UTC 时间
        utc_time = utc_time.replace(tzinfo=timezone.utc)

    # 转换为北京时间
    shanghai_tz = pytz.timezone("Asia/Shanghai")
    local_time = utc_time.astimezone(shanghai_tz)

    # 格式化输出
    return local_time.strftime("%Y-%m-%d %H:%M:%S")

def close_connection_pool():
    global _connection_pool
    if _connection_pool is not None:
        _connection_pool.close()
        print("Database connection pool closed.")




'''
为什么模块中顶层的函数调用 register_close_handler() 会在每次导入模块时都执行，而变量定义 _connection_pool_registered = False 却只执行一次？
🧠 回答核心：
因为模块在首次导入时会被完整执行一次；之后再次导入时，Python 只会从 sys.modules 缓存中加载整个模块对象， 但是：
✅ 如果是“纯表达式”或“函数调用”，即使写在模块顶层，也会在每次导入时被重新执行。
❌ 如果是“变量赋值”、“函数定义”、“类定义”等，则只会执行一次。

1. Python 的模块缓存机制（sys.modules）
当你第一次导入一个模块时，Python 会：
执行整个模块文件中的所有代码
把这个模块对象缓存到 sys.modules
后续再导入该模块时，Python 不再执行模块文件，而是直接从 sys.modules 中取出已有的模块对象
2. 顶层语句 ≠ 都不会重复执行
不是所有顶层语句都不会重复执行！
实际上，只有“定义性语句”（如变量定义、函数定义）不会重复执行
而像“函数调用”这种“执行性语句”，即使写在模块顶层，也会在每次导入时被执行！
'''
_connection_pool_registered = False

def register_close_handler():
    global _connection_pool_registered
    # print("===========注册关闭处理器执行了一次===========")
    if not _connection_pool_registered:
        import atexit
        atexit.register(close_connection_pool)
        _connection_pool_registered = True
    if _connection_pool_registered:
        #print("全局标志变量已经设为True，数据库模块已经注册过关闭处理函数了，所以不会重复注册关闭钩子")
        pass

register_close_handler()

if __name__ == "__main__":
    pass
else:
    # print("数据库操作模块被导入了一次")
    pass