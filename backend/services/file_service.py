import logging
import shutil
from pathlib import Path
from fastapi import UploadFile
from typing import List, Dict, Optional
from datetime import datetime
import threading
import time
from indexing import index_file_backend

logger = logging.getLogger(__name__)

class FileService:
    def __init__(self):
        self.base_dir = Path(__file__).parent.parent.parent / "all_users_files"

    def _get_user_dir(self, user_email: str) -> Path:
        """获取用户文件目录：all_users_files/user{email}"""
        # 移除邮箱中的特殊字符，只保留用户名部分
        # 这里假设邮箱格式为 username@domain.com，取@之前的部分
        user_part = user_email.split('@')[0]
        user_dir = self.base_dir / f"user{user_part}"

        # 确保目录存在
        try:
            user_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"创建用户目录失败: {user_dir}, 错误: {e}")

        return user_dir

    def _get_kb_dir(self, user_email: str, kb_name: str) -> Path:
        """获取知识库文件目录：all_users_files/user{email}/{kb_name}"""
        user_dir = self._get_user_dir(user_email)
        kb_dir = user_dir / kb_name

        # 确保目录存在
        try:
            kb_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"创建知识库目录失败: {kb_dir}, 错误: {e}")

        return kb_dir

    def create_kb_directory(self, user_email: str, kb_name: str) -> Path:
        """创建知识库目录"""
        kb_dir = self.base_dir / f"user{user_email}" / kb_name
        kb_dir.mkdir(parents=True, exist_ok=True)
        return kb_dir

    def rename_kb_directory(self, user_email: str, old_name: str, new_name: str) -> Path:
        """重命名知识库目录"""
        old_dir = self.base_dir / f"user{user_email}" / old_name
        new_dir = self.base_dir / f"user{user_email}" / new_name

        if old_dir.exists():
            old_dir.rename(new_dir)

        return new_dir

    def delete_kb_directory(self, user_email: str, kb_name: str) -> bool:
        """删除知识库目录"""
        kb_dir = self.base_dir / f"user{user_email}" / kb_name

        if kb_dir.exists():
            shutil.rmtree(kb_dir)
            return True
        return False

    def list_kb_files(self, user_email: str, kb_name: str) -> List[Dict]:
        """列出知识库下的所有文件"""
        kb_dir = self.base_dir / f"user{user_email}" / kb_name

        if not kb_dir.exists():
            return []

        files = []
        for file_path in kb_dir.iterdir():
            if file_path.is_file():
                creation_time = datetime.fromtimestamp(file_path.stat().st_ctime)
                formatted_time = creation_time.strftime("%Y-%m-%d %H:%M:%S")

                files.append({
                    "name": file_path.name,
                    "display_name": file_path.name[1:] if file_path.name.startswith("&") else file_path.name,
                    "path": str(file_path),
                    "upload_time": formatted_time,
                    "is_parsed": file_path.name.startswith("&"),
                    "size": file_path.stat().st_size
                })

        return files

    def save_uploaded_file(self, user_email: str, kb_name: str, uploaded_file: UploadFile) -> Dict:
        """保存上传的文件"""
        kb_dir = self.base_dir / f"user{user_email}" / kb_name

        # 确保目录存在
        kb_dir.mkdir(parents=True, exist_ok=True)

        # 构建文件路径
        file_path = kb_dir / uploaded_file.filename

        # 防止覆盖
        if file_path.exists():
            raise FileExistsError(f"文件 {uploaded_file.filename} 已存在")

        # 保存文件
        with open(file_path, "wb") as f:
            f.write(uploaded_file.file.read())

        # 获取文件信息
        creation_time = datetime.fromtimestamp(file_path.stat().st_ctime)
        formatted_time = creation_time.strftime("%Y-%m-%d %H:%M:%S")

        return {
            "name": uploaded_file.filename,
            "path": str(file_path),
            "upload_time": formatted_time,
            "size": file_path.stat().st_size
        }

    def rename_file(self, user_email: str, kb_name: str, old_name: str, new_name: str) -> Dict:
        """重命名文件"""
        kb_dir = self.base_dir / f"user{user_email}" / kb_name

        # 构建路径
        old_path = kb_dir / old_name
        new_path = kb_dir / new_name

        # 如果原文件已解析，新文件名也要带&
        if old_name.startswith("&"):
            new_name_with_prefix = "&" + new_name
            new_path = kb_dir / new_name_with_prefix
        else:
            new_name_with_prefix = new_name

        # 检查新文件是否存在
        if new_path.exists():
            raise FileExistsError(f"文件 {new_name} 已存在")

        # 重命名
        old_path.rename(new_path)

        # 获取新文件信息
        creation_time = datetime.fromtimestamp(new_path.stat().st_ctime)
        formatted_time = creation_time.strftime("%Y-%m-%d %H:%M:%S")

        return {
            "name": new_path.name,
            "display_name": new_path.name[1:] if new_path.name.startswith("&") else new_path.name,
            "path": str(new_path),
            "upload_time": formatted_time
        }

    def delete_file(self, user_email: str, kb_name: str, file_name: str):
        """删除文件"""
        kb_dir = self.base_dir / f"user{user_email}" / kb_name
        file_path = kb_dir / file_name

        if file_path.exists():
            file_path.unlink()

    def get_file_path(self, user_email: str, kb_name: str, file_name: str) -> Path:
        """获取文件路径"""
        kb_dir = self.base_dir / f"user{user_email}" / kb_name
        return kb_dir / file_name

    def search_file(self, user_email: str, kb_name: str, search_name: str) -> Optional[Dict]:
        """
        在知识库中搜索文件
        - 返回文件信息字典（如果找到）
        - 返回 None（如果未找到）
        - 不会抛出异常（异常由上层处理）
        """
        logger = logging.getLogger(__name__)
        logger.info(f"搜索文件: 用户={user_email}, 知识库={kb_name}, 搜索词={search_name}")

        try:
            # 1. 获取知识库目录
            kb_dir = self._get_kb_dir(user_email, kb_name)

            # 2. 检查目录是否存在
            if not kb_dir.exists():
                logger.warning(f"知识库目录不存在: {kb_dir}")
                return None

            # 3. 获取所有文件
            files = self.list_kb_files(user_email, kb_name)
            logger.info(f"找到 {len(files)} 个文件")

            if not files:
                logger.info("知识库为空，没有文件")
                return None

            # 4. 精确匹配搜索
            for file in files:
                display_name = file.get("display_name", "")
                if display_name == search_name:
                    logger.info(f"找到精确匹配: {display_name}")
                    return file

            # 5. 模糊匹配（可选）
            for file in files:
                display_name = file.get("display_name", "")
                if search_name.lower() in display_name.lower():
                    logger.info(f"找到模糊匹配: {display_name}")
                    return file

            logger.info(f"未找到匹配的文件: {search_name}")
            return None

        except PermissionError as e:
            logger.error(f"权限错误，无法访问目录: {e}")
            return None
        except OSError as e:
            logger.error(f"系统错误，无法访问目录: {e}")
            return None
        except Exception as e:
            logger.error(f"搜索文件时发生未知错误: {e}", exc_info=True)
            return None  # 返回 None，由上层决定是 404 还是 500


def parse_file_background(kb, file_name):
    """后台解析文件"""

    def parse_thread():
        # 这里调用原有的index_file_backend函数
        # 实际实现需要更新进度到parse_progress_store
        pass

    thread = threading.Thread(target=parse_thread)
    thread.start()


def parse_all_files_background(kb):
    """后台批量解析文件"""

    def parse_all_thread():
        # 批量解析逻辑
        pass

    thread = threading.Thread(target=parse_all_thread)
    thread.start()