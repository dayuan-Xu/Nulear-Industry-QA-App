import requests
from typing import Dict, List, Optional, Any, Union
import streamlit as st
from pathlib import Path


class ApiClient:
    def __init__(self):
        self.base_url = "http://localhost:8001"  # FastAPI后端地址

    def create_knowledge_base(self, user_email: str, kb_name: str) -> Dict:
        """创建知识库"""
        response = requests.post(
            f"{self.base_url}/api/knowledge-bases/",
            params={"user_email": user_email},
            json={"name": kb_name}
        )
        response.raise_for_status()
        return response.json()

    def get_user_knowledge_bases(self, user_email: str) -> List[Dict]:
        """获取用户的所有知识库"""
        response = requests.get(f"{self.base_url}/api/knowledge-bases/user/{user_email}")
        response.raise_for_status()
        return response.json()["knowledge_bases"]

    def rename_knowledge_base(self, kb_id: int, new_name: str) -> Dict:
        """重命名知识库"""
        response = requests.put(
            f"{self.base_url}/api/knowledge-bases/{kb_id}/name",
            json={"name": new_name}
        )
        response.raise_for_status()
        return response.json()

    def delete_knowledge_base(self, kb_id: int) -> Dict:
        """删除知识库"""
        response = requests.delete(f"{self.base_url}/api/knowledge-bases/{kb_id}")
        response.raise_for_status()
        return response.json()

    def get_kb_files(self, kb_id: int) -> List[Dict]:
        """获取知识库下的文件"""
        response = requests.get(f"{self.base_url}/api/knowledge-bases/{kb_id}/files")
        response.raise_for_status()
        return response.json()["files"]

    def upload_file(self, kb_id: int, file_path: Union[str, Path]) -> Dict:
        """
        上传文件到知识库
        file_path: 可以是字符串路径或 Path 对象
        """
        # 统一转换为 Path 对象
        if isinstance(file_path, str):
            file_path = Path(file_path)

        # 获取文件名
        file_name = file_path.name

        with open(file_path, "rb") as f:
            response = requests.post(
                f"{self.base_url}/api/knowledge-bases/{kb_id}/files/upload",
                files={"file": (file_name, f)}
            )
        return response.json()

    def parse_file(self, kb_id: int, file_name: str) -> Dict:
        """解析文件"""
        response = requests.post(
            f"{self.base_url}/api/knowledge-bases/{kb_id}/files/{file_name}/parse"
        )
        response.raise_for_status()
        return response.json()

    def parse_all_files(self, kb_id: int) -> Dict:
        """解析所有文件"""
        response = requests.post(
            f"{self.base_url}/api/knowledge-bases/{kb_id}/files/parse-all"
        )
        response.raise_for_status()
        return response.json()

    def get_parse_progress(self, kb_id: int) -> Dict:
        """获取解析进度"""
        response = requests.get(f"{self.base_url}/api/knowledge-bases/{kb_id}/parse-progress")
        response.raise_for_status()
        return response.json()

    def rename_file(self, kb_id: int, file_name: str, new_name: str) -> Dict:
        """重命名文件"""
        response = requests.put(
            f"{self.base_url}/api/knowledge-bases/{kb_id}/files/{file_name}/rename",
            json={"new_name": new_name}
        )
        response.raise_for_status()
        return response.json()

    def delete_file(self, kb_id: int, file_name: str) -> Dict:
        """删除文件"""
        response = requests.delete(
            f"{self.base_url}/api/knowledge-bases/{kb_id}/files/{file_name}"
        )
        response.raise_for_status()
        return response.json()

    def search_file(self, kb_id: int, file_name: str) -> Optional[Dict]:
        """搜索文件"""
        response = requests.get(
            f"{self.base_url}/api/knowledge-bases/{kb_id}/search-file",
            params={"file_name": file_name}
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()["file"]


# 全局API客户端实例
api_client = ApiClient()