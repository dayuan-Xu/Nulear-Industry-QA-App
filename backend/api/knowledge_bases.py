from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Query
from fastapi.responses import FileResponse
from typing import List, Optional, Dict
import shutil
from pathlib import Path
import uuid
import os
from datetime import datetime
from backend.models.schemas import KnowledgeBaseCreate, KnowledgeBaseUpdate, FileRename, ParseProgress
from backend.services.kb_service import KnowledgeBaseService
from backend.services.file_service import FileService
from db_utils import get_user_id
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/knowledge-bases", tags=["knowledge-bases"])
kb_service = KnowledgeBaseService()
file_service = FileService()

# 存储解析进度（实际项目中应使用Redis或数据库）
parse_progress_store: Dict[str, Dict[str, ParseProgress]] = {}


@router.post("/")
async def create_knowledge_base(
        user_email: str,
        kb_data: KnowledgeBaseCreate,
        background_tasks: BackgroundTasks
):
    """创建知识库"""
    try:
        logger.info(f"创建知识库请求: 用户={user_email}, 名称={kb_data.name}")

        # 检查是否重名
        if kb_service.check_kb_name_exists(user_email, kb_data.name):
            raise HTTPException(status_code=400, detail="知识库名称重复")

        # 创建知识库（数据库）
        kb = kb_service.create_knowledge_base(user_email, kb_data.name)

        # 在文件系统中创建目录
        kb_dir = file_service.create_kb_directory(user_email, kb_data.name)

        # 创建向量数据库集合
        try:
            from indexing import create_collection_if_not_exists, get_collection_name
            create_collection_if_not_exists(get_collection_name(kb_dir, kb))
            logger.info(f"向量数据库集合创建成功: {kb.name}")
        except Exception as e:
            logger.warning(f"向量数据库集合创建失败（可能未启用）: {e}")
            # 不阻止知识库创建，只是记录警告

        # 如果是第一个知识库，更新用户配置
        if kb_service.get_user_kb_count(user_email) == 1:
            kb_service.update_user_default_config(user_email)

        return {
            "message": "知识库创建成功",
            "knowledge_base": {
                "kb_id": kb.kb_id,
                "name": kb.name,
                "doc_number": kb.doc_number,
                "created_time": kb.created_time,
                "local_created_time": kb.local_created_time,
                "user_email": user_email
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建知识库失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建知识库失败: {str(e)}")


@router.get("/user/{user_email}")
async def get_user_knowledge_bases(user_email: str):
    """获取用户的所有知识库"""
    try:
        kbs = kb_service.get_user_knowledge_bases(user_email)

        # 转换为字典格式，包含本地时间
        kb_dicts = []
        for kb in kbs:
            kb_dict = {
                "kb_id": kb.kb_id,
                "name": kb.name,
                "doc_number": kb.doc_number,
                "created_time": kb.created_time,
                "local_created_time": kb.local_created_time,
                "user_email": user_email
            }
            kb_dicts.append(kb_dict)

        return {"knowledge_bases": kb_dicts}
    except Exception as e:
        logger.error(f"获取知识库失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取知识库失败: {str(e)}")


@router.get("/{kb_id}")
async def get_knowledge_base(kb_id: str):
    """获取知识库详情"""
    try:
        kb = kb_service.get_knowledge_base(kb_id)
        if not kb:
            raise HTTPException(status_code=404, detail="知识库不存在")

        return {
            "knowledge_base": {
                "kb_id": kb.kb_id,
                "name": kb.name,
                "doc_number": kb.doc_number,
                "created_time": kb.created_time,
                "local_created_time": kb.local_created_time,
                "user_email": kb.user_email
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取知识库失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取知识库失败: {str(e)}")


@router.put("/{kb_id}/name")
async def rename_knowledge_base(kb_id: str, kb_update: KnowledgeBaseUpdate):
    """重命名知识库"""
    try:
        # 检查新名称是否重复
        kb = kb_service.get_knowledge_base(kb_id)
        if not kb:
            raise HTTPException(status_code=404, detail="知识库不存在")

        if kb_service.check_kb_name_exists(kb.user_email, kb_update.name, exclude_kb_id=int(kb_id)):
            raise HTTPException(status_code=400, detail="知识库名称重复")

        # 重命名知识库
        updated_kb = kb_service.rename_knowledge_base(kb_id, kb_update.name)

        # 重命名文件系统目录
        file_service.rename_kb_directory(kb.user_email, kb.name, kb_update.name)

        return {
            "message": "知识库重命名成功",
            "knowledge_base": {
                "kb_id": updated_kb.kb_id,
                "name": updated_kb.name,
                "doc_number": updated_kb.doc_number,
                "created_time": updated_kb.created_time,
                "local_created_time": updated_kb.local_created_time,
                "user_email": updated_kb.user_email
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重命名知识库失败: {e}")
        raise HTTPException(status_code=500, detail=f"重命名知识库失败: {str(e)}")


@router.delete("/{kb_id}")
async def delete_knowledge_base(kb_id: str):
    """删除知识库"""
    try:
        kb = kb_service.get_knowledge_base(kb_id)
        if not kb:
            raise HTTPException(status_code=404, detail="知识库不存在")

        # 删除数据库记录
        success = kb_service.delete_knowledge_base(kb_id)
        if not success:
            raise HTTPException(status_code=500, detail="删除数据库记录失败")

        # 删除文件系统目录
        file_service.delete_kb_directory(kb.user_email, kb.name)

        # 删除向量数据库集合
        try:
            from indexing import delete_collection
            delete_collection(kb)
            logger.info(f"向量数据库集合删除成功: {kb.name}")
        except Exception as e:
            logger.warning(f"向量数据库集合删除失败（可能未启用）: {e}")
            # 不阻止知识库删除，只是记录警告

        return {"message": "知识库删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除知识库失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除知识库失败: {str(e)}")


@router.get("/{kb_id}/files")
async def get_kb_files(kb_id: str):
    """获取知识库下的所有文件"""
    try:
        kb = kb_service.get_knowledge_base(kb_id)
        if not kb:
            raise HTTPException(status_code=404, detail="知识库不存在")

        files = file_service.list_kb_files(kb.user_email, kb.name)
        return {"files": files}
    except Exception as e:
        logger.error(f"获取文件列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取文件列表失败: {str(e)}")


@router.post("/{kb_id}/files/upload")
async def upload_file(
        kb_id: str,
        file: UploadFile = File(...),
        background_tasks: BackgroundTasks = None
):
    """上传文件到知识库"""
    try:
        kb = kb_service.get_knowledge_base(kb_id)
        if not kb:
            raise HTTPException(status_code=404, detail="知识库不存在")

        # 保存文件
        saved_file = file_service.save_uploaded_file(kb.user_email, kb.name, file)

        # 更新文档计数
        kb_service.update_kb_document_count(kb_id, kb.doc_number + 1)

        return {
            "message": "文件上传成功",
            "file": saved_file
        }
    except FileExistsError as e:
        logger.warning(f"文件已存在: {e}")
        raise HTTPException(status_code=400, detail=f"文件已存在: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"上传文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"上传文件失败: {str(e)}")

# 其他API函数保持类似的结构，处理异常和日志记录

# ... 其他函数保持类似修改 ...