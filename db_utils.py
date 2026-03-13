# 直接复制现有的 db_utils.py，但需要做一些调整以适应后端使用
import atexit
import os
from psycopg_pool import ConnectionPool
from backend.models.schemas import KnowledgeBase, Chat
from datetime import timezone
import pytz
import logging

logger = logging.getLogger(__name__)

_connection_pool = None


def get_connection_pool():
    global _connection_pool
    if _connection_pool is None:
        from backend.config import Config
        DB_URI = f"postgresql://{Config.DB_USER}:{Config.DB_PASSWORD}@{Config.DB_HOST}:{Config.DB_PORT}/{Config.DB_NAME}?sslmode={Config.DB_SSL_MODE}"

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
            logger.info("数据库连接池初始化成功")
        except Exception as e:
            logger.error(f"无法初始化数据库连接池: {e}")
            raise RuntimeError("无法初始化数据库连接池") from e
    return _connection_pool


def get_user_kbs(user_email: str):
    """获取用户的所有知识库"""
    user_id = get_user_id(user_email)
    if not user_id:
        return []

    pool = get_connection_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM knowledge_bases WHERE user_id = %s", (user_id,))
            rows = cur.fetchall()
            kbs = []
            for row in rows:
                kb = KnowledgeBase(
                    kb_id=row[0],
                    name=row[1],
                    doc_number=row[2],
                    created_time=row[3],
                    user_email=user_email,
                    user_id=user_id
                )
                kbs.append(kb)
            return kbs


def get_kb_by_id(kb_id: int):
    """根据ID获取知识库"""
    pool = get_connection_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                            SELECT 
                                kb.kb_id,        -- row[0]
                                kb.name,         -- row[1]  
                                kb.doc_number,   -- row[2]
                                kb.created_time, -- row[3]
                                u.email          -- row[4]  ← 这才是邮箱字符串
                            FROM knowledge_bases kb
                            JOIN users u ON kb.user_id = u.id
                            WHERE kb.kb_id = %s
                        """, (kb_id,))
            row = cur.fetchone()
            if row:
                return KnowledgeBase(
                    kb_id=row[0],
                    name=row[1],
                    doc_number=row[2],
                    created_time=row[3],
                    user_email=str(row[4]),
                    user_id=None  # 可以从其他查询获取
                )
            return None


def get_kb_by_name(user_email: str, kb_name: str):
    """根据名称获取知识库"""
    print(f"DEBUG: get_kb_by_name called with user_email={user_email}, kb_name={kb_name}")

    user_id = get_user_id(user_email)
    print(f"DEBUG: user_id = {user_id}")

    if not user_id:
        print(f"DEBUG: 用户 {user_email} 不存在")
        return None

    pool = get_connection_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            # 添加调试输出
            print(f"DEBUG: 执行查询: SELECT * FROM knowledge_bases WHERE user_id = {user_id} AND name = '{kb_name}'")

            cur.execute("SELECT * FROM knowledge_bases WHERE user_id = %s AND name = %s",
                        (user_id, kb_name))
            row = cur.fetchone()

            if row:
                print(f"DEBUG: 找到记录: {row}")
                return KnowledgeBase(
                    kb_id=row[0],
                    name=row[1],
                    doc_number=row[2],
                    created_time=row[3],
                    user_email=user_email,
                    user_id=user_id
                )
            else:
                print(f"DEBUG: 未找到记录")
                return None

def insert_KB(name: str, user_email: str):
    """创建知识库（修改版，接受user_email）"""
    user_id = get_user_id(user_email)
    if not user_id:
        raise ValueError(f"用户 {user_email} 不存在")

    pool = get_connection_pool()
    try:
        with pool.connection() as connection:
            with connection.cursor() as cur:
                # 使用 RETURNING 子句获取插入的记录信息
                cur.execute("""
                    INSERT INTO knowledge_bases (name, user_id)
                    VALUES (%s, %s)
                    RETURNING kb_id, name, doc_number, created_time
                """, (name, user_id))

                # 获取插入后的记录
                row = cur.fetchone()
                if row:
                    # 构造 KnowledgeBase 对象并返回
                    new_KB = KnowledgeBase(
                        kb_id=row[0],
                        name=row[1],
                        doc_number=row[2],
                        created_time=row[3],
                        user_email=user_email,
                        user_id=user_id
                    )
                    connection.commit()
                    return new_KB
                else:
                    connection.commit()
                    return None
    except Exception as e:
        logger.error(f"Error inserting new KB: {e}")
        raise


def update_KB_name(kb_id: int, new_name: str):
    """更新知识库名称"""
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
        logger.error(f"Error updating KB name:{e}")
        return False


def update_KB(kb_id: int, new_doc_number: int):
    """更新知识库文档数量"""
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
        logger.error(f"Error updating KB doc_number:{e}")
        return False


def delete_KB(kb_id: int):
    """删除知识库"""
    pool = get_connection_pool()
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM knowledge_bases WHERE kb_id = %s", (kb_id,))
                conn.commit()
                return True
    except Exception as e:
        logger.error(f"Error deleting KB: {e}")
        return False


# 以下是原有函数，保持不变
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
    """获取用户ID"""
    pool = get_connection_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE email = %s", (email,))
            result = cur.fetchone()
            if result:
                return result[0]
    return None


def get_chats(email: str):
    """获取用户的所有聊天"""
    pool = get_connection_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT thread_id, thread_title ,created_time 
                FROM chats 
                WHERE user_id = (SELECT id FROM users WHERE email = %s)
            """, (email,))
            rows = cur.fetchall()
            return [Chat(thread_id=row[0], thread_title=row[1], created_time=row[2]) for row in rows]


def insert_chat(new_chat: Chat, user_id: str):
    """插入新的聊天"""
    pool = get_connection_pool()
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO chats (thread_id, thread_title, created_time, user_id) VALUES (%s, %s, NOW(), %s)",
                    (new_chat["thread_id"], new_chat["thread_title"], user_id))
                conn.commit()  # 提交事务
                return 1  # 插入成功
    except Exception as e:
        logger.error(f"Error inserting chat: {e}")
        return 0


def delete_chat(thread_id: str) -> int:
    """删除聊天"""
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
        logger.error(f"Error deleting chat: {e}")
        return 0  # 失败


def update_chat_title(chat, new_title):
    """更新聊天标题"""
    pool = get_connection_pool()
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE chats SET thread_title = %s WHERE thread_id = %s", (new_title, chat["thread_id"]))
                conn.commit()  # 提交事务
                return 1  # 成功
    except Exception as e:
        logger.error(f"Error updating chat title: {e}")
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
    """关闭连接池"""
    global _connection_pool
    if _connection_pool is not None:
        _connection_pool.close()
        logger.info("Database connection pool closed.")


_connection_pool_registered = False


def register_close_handler():
    """注册关闭处理器"""
    global _connection_pool_registered
    if not _connection_pool_registered:
        atexit.register(close_connection_pool)
        _connection_pool_registered = True
        logger.info("数据库连接池关闭处理器已注册")


register_close_handler()