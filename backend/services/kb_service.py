from typing import List, Optional
from datetime import datetime
from backend.models.schemas import KnowledgeBase
from db_utils import (
    format_utc_to_local,
    delete_KB,
    insert_KB,
    update_KB,
    update_KB_name,
    get_user_kbs,
    get_kb_by_id,
    get_kb_by_name,
    get_user_id
)
import logging

logger = logging.getLogger(__name__)


class KnowledgeBaseService:
    def check_kb_name_exists(self, user_email: str, kb_name: str, exclude_kb_id: int = None) -> bool:
        """检查知识库名称是否重复"""
        try:
            existing_kb = get_kb_by_name(user_email, kb_name)
            if existing_kb:
                # 如果指定了要排除的kb_id（比如重命名时），检查是否是同一个知识库
                if exclude_kb_id and existing_kb.kb_id == exclude_kb_id:
                    return False
                return True
            return False
        except Exception as e:
            logger.error(f"检查知识库名称存在性失败: {e}")
            return True  # 出错时返回True，避免创建重复

    def create_knowledge_base(self, user_email: str, kb_name: str) -> KnowledgeBase:
        """创建知识库"""
        try:
            # 插入数据库
            kb = insert_KB(kb_name, user_email)
            if not kb:
                raise ValueError("创建知识库失败")
            return kb
        except Exception as e:
            logger.error(f"创建知识库失败: {e}")
            raise

    def get_user_knowledge_bases(self, user_email: str) -> List[KnowledgeBase]:
        """获取用户的所有知识库"""
        try:
            kbs = get_user_kbs(user_email)
            # 添加本地时间格式化
            for kb in kbs:
                if not hasattr(kb, 'local_created_time') or not kb.local_created_time:
                    kb.local_created_time = format_utc_to_local(kb.created_time)
            return kbs
        except Exception as e:
            logger.error(f"获取用户知识库失败: {e}")
            return []

    def get_knowledge_base(self, kb_id: str) -> Optional[KnowledgeBase]:
        """获取知识库详情"""
        try:
            kb = get_kb_by_id(kb_id)
            if kb:
                # 确保有本地时间格式化
                if not hasattr(kb, 'local_created_time') or not kb.local_created_time:
                    kb.local_created_time = format_utc_to_local(kb.created_time)
            return kb
        except Exception as e:
            logger.error(f"获取知识库详情失败: {e}")
            return None

    def rename_knowledge_base(self, kb_id: str, new_name: str) -> KnowledgeBase:
        """重命名知识库"""
        try:
            # 更新数据库
            success = update_KB_name(int(kb_id), new_name)
            if not success:
                raise ValueError("重命名知识库失败")

            # 获取更新后的知识库
            kb = self.get_knowledge_base(kb_id)
            if not kb:
                raise ValueError("获取更新后的知识库失败")
            return kb
        except Exception as e:
            logger.error(f"重命名知识库失败: {e}")
            raise

    def delete_knowledge_base(self, kb_id: str) -> bool:
        """删除知识库"""
        try:
            success = delete_KB(int(kb_id))
            return success
        except Exception as e:
            logger.error(f"删除知识库失败: {e}")
            return False

    def update_kb_document_count(self, kb_id: str, new_count: int) -> bool:
        """更新知识库文档计数"""
        try:
            success = update_KB(int(kb_id), new_count)
            return success
        except Exception as e:
            logger.error(f"更新知识库文档计数失败: {e}")
            return False

    def get_user_kb_count(self, user_email: str) -> int:
        """获取用户知识库数量"""
        try:
            kbs = self.get_user_knowledge_bases(user_email)
            return len(kbs)
        except Exception as e:
            logger.error(f"获取用户知识库数量失败: {e}")
            return 0

    def update_user_default_config(self, user_email: str):
        """更新用户默认配置（第一个知识库创建时）"""
        # 这里实现具体的配置更新逻辑
        # 可以根据需要调用其他数据库函数
        pass