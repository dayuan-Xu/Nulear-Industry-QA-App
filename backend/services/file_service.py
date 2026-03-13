import shutil
from pathlib import Path
from fastapi import UploadFile
from typing import List, Dict, Optional
from datetime import datetime
import threading
import time
from indexing import index_file_backend


class FileService:
    def __init__(self):
        self.base_dir = Path(__file__).parent.parent.parent / "all_users_files"

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
        """搜索文件"""
        files = self.list_kb_files(user_email, kb_name)

        for file in files:
            if file["display_name"] == search_name:
                return file

        return None


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