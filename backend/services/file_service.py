# backend/services/file_service.py
import threading
import time
from pathlib import Path
from typing import Dict, Optional, List
import logging
from fastapi import UploadFile
from datetime import datetime

logger = logging.getLogger(__name__)

# ========== 全局解析进度存储（移到这里！） ==========
parse_progress_store: Dict[str, Dict[str, Dict]] = {}


class FileService:
    # ... 保持现有所有方法不变 ...
    def __init__(self):
        from backend.config import Config
        self.base_dir = Config.ALL_USERS_FILES_DIR

    def _get_user_dir(self, user_email: str) -> Path:
        return self.base_dir / f"user{user_email}"

    def _get_kb_dir(self, user_email: str, kb_name: str) -> Path:
        return self._get_user_dir(user_email) / kb_name

    def create_kb_directory(self, user_email: str, kb_name: str) -> Path:
        kb_dir = self._get_kb_dir(user_email, kb_name)
        kb_dir.mkdir(parents=True, exist_ok=True)
        return kb_dir

    def rename_kb_directory(self, user_email: str, old_name: str, new_name: str) -> Path:
        old_dir = self._get_kb_dir(user_email, old_name)
        new_dir = self._get_kb_dir(user_email, new_name)
        if old_dir.exists():
            old_dir.rename(new_dir)
        return new_dir

    def delete_kb_directory(self, user_email: str, kb_name: str) -> bool:
        import shutil
        kb_dir = self._get_kb_dir(user_email, kb_name)
        if kb_dir.exists():
            shutil.rmtree(kb_dir)
            return True
        return False

    def list_kb_files(self, user_email: str, kb_name: str) -> List[Dict]:
        kb_dir = self._get_kb_dir(user_email, kb_name)
        if not kb_dir.exists():
            return []
        files = []
        for file_path in kb_dir.iterdir():
            if file_path.is_file():
                stat = file_path.stat()
                creation_time = datetime.fromtimestamp(stat.st_ctime)
                formatted_time = creation_time.strftime("%Y-%m-%d %H:%M:%S")
                files.append({
                    "name": file_path.name,
                    "display_name": file_path.name[1:] if file_path.name.startswith("&") else file_path.name,
                    "path": str(file_path),
                    "upload_time": formatted_time,
                    "is_parsed": file_path.name.startswith("&"),
                    "size": stat.st_size
                })
        return files

    def save_uploaded_file(self, user_email: str, kb_name: str, uploaded_file: UploadFile,
                           original_filename: str = None) -> Dict:
        kb_dir = self._get_kb_dir(user_email, kb_name)
        kb_dir.mkdir(parents=True, exist_ok=True)

        if original_filename:
            safe_filename = Path(original_filename).name
        else:
            safe_filename = Path(uploaded_file.filename).name

        file_path = kb_dir / safe_filename
        if file_path.exists():
            raise FileExistsError(f"文件 {safe_filename} 已存在")

        content = uploaded_file.file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        stat = file_path.stat()
        creation_time = datetime.fromtimestamp(stat.st_ctime)
        formatted_time = creation_time.strftime("%Y-%m-%d %H:%M:%S")
        return {
            "name": file_path.name,
            "display_name": safe_filename,
            "path": str(file_path),
            "upload_time": formatted_time,
            "is_parsed": False,
            "size": stat.st_size
        }

    def rename_file(self, user_email: str, kb_name: str, old_name: str, new_name: str) -> Dict:
        kb_dir = self._get_kb_dir(user_email, kb_name)
        old_path = kb_dir / old_name
        if old_name.startswith("&"):
            new_name_with_prefix = "&" + new_name
        else:
            new_name_with_prefix = new_name
        new_path = kb_dir / new_name_with_prefix
        if new_path.exists():
            raise FileExistsError(f"文件 {new_name} 已存在")
        old_path.rename(new_path)
        stat = new_path.stat()
        creation_time = datetime.fromtimestamp(stat.st_ctime)
        formatted_time = creation_time.strftime("%Y-%m-%d %H:%M:%S")
        return {
            "name": new_path.name,
            "display_name": new_path.name[1:] if new_path.name.startswith("&") else new_path.name,
            "path": str(new_path),
            "upload_time": formatted_time,
            "is_parsed": new_path.name.startswith("&"),
            "size": stat.st_size
        }

    def delete_file(self, user_email: str, kb_name: str, file_name: str):
        kb_dir = self._get_kb_dir(user_email, kb_name)
        file_path = kb_dir / file_name
        if file_path.exists():
            file_path.unlink()

    def get_file_path(self, user_email: str, kb_name: str, file_name: str) -> Path:
        return self._get_kb_dir(user_email, kb_name) / file_name

    def search_file(self, user_email: str, kb_name: str, search_name: str) -> Optional[Dict]:
        files = self.list_kb_files(user_email, kb_name)
        for file in files:
            if file["display_name"] == search_name:
                return file
        return None

    def rename_file_after_parse(self, user_email: str, kb_name: str, file_name: str) -> bool:
        file_path = self.get_file_path(user_email, kb_name, file_name)
        if not file_path.exists():
            logger.error(f"文件不存在，无法重命名: {file_path}")
            return False
        new_name = "&" + file_path.name
        new_path = file_path.with_name(new_name)
        try:
            file_path.rename(new_path)
            return True
        except Exception as e:
            logger.error(f"❌ 重命名失败: {e}")
            return False


# ========== 后台解析任务（使用 parse_progress_store） ==========
def parse_file_background(kb_id: int, user_email: str, kb_name: str, file_name: str):
    """后台解析单个文件"""
    from indexing import index_file_backend
    from backend.services.kb_service import KnowledgeBaseService  # 函数内导入，避免循环

    global parse_progress_store

    logger.info(f"开始后台解析: kb_id={kb_id}, file={file_name}")
    logger.info(f"全局进度存储 ID: {id(parse_progress_store)}")  # 调试

    kb_id_str = str(kb_id)
    if kb_id_str not in parse_progress_store:
        parse_progress_store[kb_id_str] = {}
    parse_progress_store[kb_id_str][file_name] = {
        "progress": 0,
        "status": "processing",
        "file_name": file_name
    }

    fs = FileService()
    kb_service = KnowledgeBaseService()

    try:
        kb = kb_service.get_knowledge_base(kb_id)
        if not kb:
            raise ValueError(f"知识库不存在: {kb_id}")

        kb_dir = fs._get_kb_dir(user_email, kb_name)
        file_path = fs.get_file_path(user_email, kb_name, file_name)

        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        for index, total in index_file_backend(file_path, kb_dir, kb):
            progress = int((index + 1) / total * 100)
            parse_progress_store[kb_id_str][file_name]["progress"] = progress

        parse_progress_store[kb_id_str][file_name]["progress"] = 100
        parse_progress_store[kb_id_str][file_name]["status"] = "completed"

        fs.rename_file_after_parse(user_email, kb_name, file_name)
        logger.info(f"文件解析完成: {file_name}")

    except Exception as e:
        logger.error(f"解析失败: {e}", exc_info=True)
        if kb_id_str in parse_progress_store and file_name in parse_progress_store[kb_id_str]:
            parse_progress_store[kb_id_str][file_name]["status"] = "failed"
            parse_progress_store[kb_id_str][file_name]["error"] = str(e)


def parse_all_files_background(kb_id: int, user_email: str, kb_name: str):
    """批量解析所有未解析文件"""
    fs = FileService()
    files = fs.list_kb_files(user_email, kb_name)
    for file_info in files:
        if not file_info["is_parsed"]:
            parse_file_background(
                kb_id,
                user_email,   # ✅ 传递
                kb_name,      # ✅ 传递
                file_info["name"]
            )