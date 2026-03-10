from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class KnowledgeBase(BaseModel):
    """知识库模型（与数据库对应）"""
    kb_id: int
    name: str
    doc_number: int
    created_time: datetime
    user_email: Optional[str] = None
    user_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

    @property
    def local_created_time(self) -> str:
        """获取本地格式化的创建时间"""
        from db_utils import format_utc_to_local
        return format_utc_to_local(self.created_time)


class Chat(BaseModel):
    """聊天模型"""
    thread_id: str
    thread_title: str
    created_time: datetime

    model_config = ConfigDict(from_attributes=True)


class KnowledgeBaseCreate(BaseModel):
    """创建知识库请求模型"""
    name: str


class KnowledgeBaseUpdate(BaseModel):
    """更新知识库请求模型"""
    name: str


class FileRename(BaseModel):
    """文件重命名请求模型"""
    new_name: str


class ParseProgress(BaseModel):
    """解析进度模型"""
    file_name: str
    progress: int
    status: str = "processing"