import logging

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Query
from fastapi.responses import FileResponse
from typing import List, Optional, Dict
from pydantic import BaseModel
import shutil
from pathlib import Path
import uuid
import os
from datetime import datetime
from backend.models.schemas import KnowledgeBaseCreate, KnowledgeBaseUpdate, FileRename
from backend.services.kb_service import KnowledgeBaseService
from backend.services.file_service import FileService, parse_file_background, parse_all_files_background

router = APIRouter(prefix="/api/knowledge-bases", tags=["knowledge-bases"])
kb_service = KnowledgeBaseService()
file_service = FileService()
logger = logging.getLogger(__name__)

class ParseProgress(BaseModel):
    file_name: str
    progress: int
    status: str = "processing"


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
        # 检查是否重名
        if kb_service.check_kb_name_exists(user_email, kb_data.name):
            raise HTTPException(status_code=400, detail="知识库名称重复")

        # 创建知识库
        kb = kb_service.create_knowledge_base(user_email, kb_data.name)

        # 在文件系统中创建目录
        kb_dir = file_service.create_kb_directory(user_email, kb_data.name)

        # 创建向量数据库集合
        from indexing import create_collection_if_not_exists, get_collection_name
        create_collection_if_not_exists(get_collection_name(kb_dir, kb))

        # 如果是第一个知识库，更新用户配置
        if kb_service.get_user_kb_count(user_email) == 1:
            kb_service.update_user_default_config(user_email)

        return {
            "message": "知识库创建成功",
            "knowledge_base": kb
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建知识库失败: {str(e)}")


@router.get("/user/{user_email}")
async def get_user_knowledge_bases(user_email: str):
    """获取用户的所有知识库"""
    try:
        kbs = kb_service.get_user_knowledge_bases(user_email)
        return {"knowledge_bases": kbs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取知识库失败: {str(e)}")


@router.get("/{kb_id}")
async def get_knowledge_base(kb_id: int):
    """获取知识库详情"""
    try:
        kb = kb_service.get_knowledge_base(kb_id)
        if not kb:
            raise HTTPException(status_code=404, detail="知识库不存在")
        return {"knowledge_base": kb}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取知识库失败: {str(e)}")


@router.put("/{kb_id}/name")
async def rename_knowledge_base(kb_id: int, kb_update: KnowledgeBaseUpdate):
    """重命名知识库"""
    try:
        # 检查新名称是否重复
        kb = kb_service.get_knowledge_base(kb_id)
        if kb_service.check_kb_name_exists(kb.user_email, kb_update.name, exclude_kb_id=kb_id):
            raise HTTPException(status_code=400, detail="知识库名称重复")

        # 重命名知识库
        updated_kb = kb_service.rename_knowledge_base(kb_id, kb_update.name)

        # 重命名文件系统目录
        file_service.rename_kb_directory(kb.user_email, kb.name, kb_update.name)

        return {
            "message": "知识库重命名成功",
            "knowledge_base": updated_kb
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重命名知识库失败: {str(e)}")


@router.delete("/{kb_id}")
async def delete_knowledge_base(kb_id: int):
    """
    删除知识库：
    1. 查询知识库是否存在
    2. 删除数据库记录
    3. 删除文件系统目录
    4. 删除向量数据库集合（可选，失败不影响主流程）
    """
    logger = logging.getLogger(__name__)
    logger.info(f"开始删除知识库: kb_id={kb_id}")

    # 1. 获取知识库信息
    kb = kb_service.get_knowledge_base(kb_id)
    if not kb:
        logger.warning(f"知识库不存在: kb_id={kb_id}")
        raise HTTPException(status_code=404, detail="知识库不存在")

    logger.info(f"找到知识库: {kb.name}, 所属用户: {kb.user_email}")

    # 2. 删除数据库记录（必须成功，否则回滚）
    try:
        db_success = kb_service.delete_knowledge_base(kb_id)
        if not db_success:
            logger.error(f"数据库删除失败: kb_id={kb_id}")
            raise HTTPException(status_code=500, detail="数据库删除失败")
        logger.info(f"数据库记录删除成功: kb_id={kb_id}")
    except Exception as e:
        logger.error(f"数据库删除异常: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"数据库删除异常: {str(e)}")

    # 3. 删除文件系统目录（如果失败，记录日志但不中断）
    try:
        fs_success = file_service.delete_kb_directory(kb.user_email, kb.name)
        if fs_success:
            logger.info(f"文件系统目录删除成功: {kb.user_email}/{kb.name}")
        else:
            logger.warning(f"文件系统目录不存在或删除失败: {kb.user_email}/{kb.name}")
    except Exception as e:
        logger.error(f"文件系统删除异常: {e}", exc_info=True)
        # 不抛出异常，继续执行

    # 4. 删除向量数据库集合（如果失败，仅记录日志）
    try:
        from backend.utils.indexing import delete_collection
        delete_collection(kb)
        logger.info(f"向量集合删除成功: {kb.name}")
    except ImportError:
        logger.debug("向量数据库模块未导入，跳过删除")
    except Exception as e:
        logger.warning(f"向量集合删除失败（已忽略）: {e}")

    logger.info(f"知识库删除完成: kb_id={kb_id}")
    return {"message": "知识库删除成功", "kb_id": kb_id}


@router.get("/{kb_id}/files")
async def get_kb_files(kb_id: int):
    """获取知识库下的所有文件"""
    try:
        kb = kb_service.get_knowledge_base(kb_id)
        if not kb:
            raise HTTPException(status_code=404, detail="知识库不存在")

        files = file_service.list_kb_files(kb.user_email, kb.name)
        return {"files": files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取文件列表失败: {str(e)}")


@router.post("/{kb_id}/files/upload")
async def upload_file(
        kb_id: int,
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传文件失败: {str(e)}")


@router.post("/{kb_id}/files/{file_name}/parse")
async def parse_file(
    kb_id: int,
    file_name: str,
    background_tasks: BackgroundTasks
):
    """
    解析单个文件
    """
    logger.info(f"请求解析文件: kb_id={kb_id}, file={file_name}")

    # 1. 验证知识库
    kb = kb_service.get_knowledge_base(kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    # 2. 验证文件是否存在
    file_path = file_service.get_file_path(kb.user_email, kb.name, file_name)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    # 3. 检查是否已解析
    if file_name.startswith("&"):
        raise HTTPException(status_code=400, detail="文件已完成解析，无需重复解析")

    # 4. 启动后台任务（✅ 补全参数）
    background_tasks.add_task(
        parse_file_background,
        kb_id,
        kb.user_email,   # 必须传递
        kb.name,         # 必须传递
        file_name
    )

    return {"message": "解析任务已启动", "status": "accepted"}


@router.post("/{kb_id}/files/parse-all")
async def parse_all_files(
    kb_id: int,
    background_tasks: BackgroundTasks
):
    """批量解析所有未解析的文件"""
    kb = kb_service.get_knowledge_base(kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    background_tasks.add_task(
        parse_all_files_background,
        kb_id,
        kb.user_email,   # ✅ 补全
        kb.name
    )

    return {"message": "批量解析任务已启动", "status": "accepted"}


@router.get("/{kb_id}/parse-progress")
async def get_parse_progress(kb_id: int):
    """获取解析进度"""
    try:
        if kb_id not in parse_progress_store:
            return {"progress": {}}

        return {"progress": parse_progress_store[kb_id]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取解析进度失败: {str(e)}")


@router.put("/{kb_id}/files/{file_name}/rename")
async def rename_file(kb_id: int, file_name: str, rename_data: FileRename):
    """重命名文件"""
    try:
        kb = kb_service.get_knowledge_base(kb_id)
        if not kb:
            raise HTTPException(status_code=404, detail="知识库不存在")

        new_name = rename_data.new_name
        if new_name.startswith("&"):
            raise HTTPException(status_code=400, detail="文件名不能以&开头")

        # 重命名文件
        result = file_service.rename_file(kb.user_email, kb.name, file_name, new_name)

        return {
            "message": "文件重命名成功",
            "old_name": file_name,
            "new_name": result["name"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重命名文件失败: {str(e)}")


@router.delete("/{kb_id}/files/{file_name}")
async def delete_file(kb_id: int, file_name: str):
    """删除文件"""
    try:
        kb = kb_service.get_knowledge_base(kb_id)
        if not kb:
            raise HTTPException(status_code=404, detail="知识库不存在")

        # 删除文件
        file_service.delete_file(kb.user_email, kb.name, file_name)

        # 更新文档计数
        kb_service.update_kb_document_count(kb_id, kb.doc_number - 1)

        return {"message": "文件删除成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除文件失败: {str(e)}")


@router.get("/{kb_id}/files/{file_name}/download")
async def download_file(kb_id: int, file_name: str):
    """下载文件"""
    try:
        kb = kb_service.get_knowledge_base(kb_id)
        if not kb:
            raise HTTPException(status_code=404, detail="知识库不存在")

        # 获取文件路径
        file_path = file_service.get_file_path(kb.user_email, kb.name, file_name)

        # 获取前端显示的文件名（去掉&）
        display_name = file_name[1:] if file_name.startswith("&") else file_name

        return FileResponse(
            path=file_path,
            filename=display_name,
            media_type="application/octet-stream"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"下载文件失败: {str(e)}")


@router.get("/{kb_id}/search-file")
async def search_file(kb_id: int, file_name: str = Query(..., description="要搜索的文件名")):
    """
    在知识库中搜索文件
    - 返回 200 并携带文件信息（如果找到）
    - 返回 404（如果未找到）
    - 其他错误返回 500
    """
    logger = logging.getLogger(__name__)
    logger.info(f"搜索文件请求: kb_id={kb_id}, file_name={file_name}")

    try:
        # 1. 验证知识库是否存在
        kb = kb_service.get_knowledge_base(kb_id)
        if not kb:
            logger.warning(f"知识库不存在: kb_id={kb_id}")
            raise HTTPException(status_code=404, detail="知识库不存在")

        logger.info(f"知识库信息: {kb.name}, 用户: {kb.user_email}")

        # 2. 检查知识库目录是否存在
        try:
            kb_dir = file_service._get_kb_dir(kb.user_email, kb.name)
            if not kb_dir.exists():
                logger.warning(f"知识库目录不存在: {kb_dir}")
                raise HTTPException(status_code=404, detail="知识库文件目录不存在")
        except Exception as e:
            logger.error(f"获取知识库目录失败: {e}")
            raise HTTPException(status_code=500, detail=f"获取知识库目录失败: {str(e)}")

        # 3. 执行搜索
        try:
            result = file_service.search_file(kb.user_email, kb.name, file_name)

            if not result:
                logger.info(f"文件未找到: kb_id={kb_id}, file_name={file_name}")
                raise HTTPException(status_code=404, detail="文件未找到")

            logger.info(f"文件找到: {result.get('display_name')}")
            return {"file": result}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"搜索文件过程出错: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"搜索文件失败: {str(e)}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"搜索文件未处理异常: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"搜索服务异常: {str(e)}")