import requests
from typing import Dict, List, Optional, Any
import streamlit as st
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class ApiClient:
    def __init__(self):
        # 从环境变量或配置文件获取API地址
        self.base_url = "http://localhost:8000"  # FastAPI后端地址

    def _handle_response(self, response: requests.Response) -> Dict:
        """统一处理响应"""
        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP错误: {e}, 响应内容: {response.text}")
            # 尝试解析错误信息
            try:
                error_data = response.json()
                error_msg = error_data.get("detail", str(e))
            except:
                error_msg = str(e)
            raise Exception(error_msg)
        except Exception as e:
            logger.error(f"请求失败: {e}")
            raise

    def create_knowledge_base(self, user_email: str, kb_name: str) -> Dict:
        """创建知识库"""
        response = requests.post(
            f"{self.base_url}/api/knowledge-bases/",
            params={"user_email": user_email},
            json={"name": kb_name}
        )
        return self._handle_response(response)

    def get_user_knowledge_bases(self, user_email: str) -> List[Dict]:
        """获取用户的所有知识库"""
        response = requests.get(f"{self.base_url}/api/knowledge-bases/user/{user_email}")
        data = self._handle_response(response)
        return data.get("knowledge_bases", [])

    def rename_knowledge_base(self, kb_id: str, new_name: str) -> Dict:
        """重命名知识库"""
        response = requests.put(
            f"{self.base_url}/api/knowledge-bases/{kb_id}/name",
            json={"name": new_name}
        )
        return self._handle_response(response)

    def delete_knowledge_base(self, kb_id: str) -> Dict:
        """删除知识库"""
        response = requests.delete(f"{self.base_url}/api/knowledge-bases/{kb_id}")
        return self._handle_response(response)

    def get_kb_files(self, kb_id: str) -> List[Dict]:
        """获取知识库下的文件"""
        response = requests.get(f"{self.base_url}/api/knowledge-bases/{kb_id}/files")
        data = self._handle_response(response)
        return data.get("files", [])

    def upload_file(self, kb_id: str, file_path: Path) -> Dict:
        """上传文件"""
        with open(file_path, "rb") as f:
            response = requests.post(
                f"{self.base_url}/api/knowledge-bases/{kb_id}/files/upload",
                files={"file": (file_path.name, f)}
            )
        return self._handle_response(response)

    def parse_file(self, kb_id: str, file_name: str) -> Dict:
        """解析文件"""
        response = requests.post(
            f"{self.base_url}/api/knowledge-bases/{kb_id}/files/{file_name}/parse"
        )
        return self._handle_response(response)

    def parse_all_files(self, kb_id: str) -> Dict:
        """解析所有文件"""
        response = requests.post(
            f"{self.base_url}/api/knowledge-bases/{kb_id}/files/parse-all"
        )
        return self._handle_response(response)

    def get_parse_progress(self, kb_id: str) -> Dict:
        """获取解析进度"""
        response = requests.get(f"{self.base_url}/api/knowledge-bases/{kb_id}/parse-progress")
        data = self._handle_response(response)
        return data.get("progress", {})

    def rename_file(self, kb_id: str, file_name: str, new_name: str) -> Dict:
        """重命名文件"""
        response = requests.put(
            f"{self.base_url}/api/knowledge-bases/{kb_id}/files/{file_name}/rename",
            json={"new_name": new_name}
        )
        return self._handle_response(response)

    def delete_file(self, kb_id: str, file_name: str) -> Dict:
        """删除文件"""
        response = requests.delete(
            f"{self.base_url}/api/knowledge-bases/{kb_id}/files/{file_name}"
        )
        return self._handle_response(response)

    def search_file(self, kb_id: str, file_name: str) -> Optional[Dict]:
        """搜索文件"""
        try:
            response = requests.get(
                f"{self.base_url}/api/knowledge-bases/{kb_id}/search-file",
                params={"file_name": file_name}
            )
            data = self._handle_response(response)
            return data.get("file")
        except Exception as e:
            if "404" in str(e):
                return None
            raise


# 全局API客户端实例
api_client = ApiClient()