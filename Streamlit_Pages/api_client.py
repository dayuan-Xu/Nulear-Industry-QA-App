import requests
from typing import Dict, List, Optional, Union
from pathlib import Path
import urllib.parse
import logging

logger = logging.getLogger(__name__)


class ApiClient:
    def __init__(self):
        self.base_url = "http://localhost:8001"

    def _handle_response(self, response: requests.Response) -> Dict:
        """统一处理响应"""
        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP {response.status_code}: {response.text}")
            try:
                error_detail = response.json().get("detail", str(e))
            except:
                error_detail = response.text or str(e)
            raise Exception(error_detail)
        except Exception as e:
            logger.error(f"响应处理失败: {e}")
            raise

    # ========== 知识库管理 ==========

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

    def rename_knowledge_base(self, kb_id: int, new_name: str) -> Dict:
        """重命名知识库"""
        response = requests.put(
            f"{self.base_url}/api/knowledge-bases/{kb_id}/name",
            json={"name": new_name}
        )
        return self._handle_response(response)

    def delete_knowledge_base(self, kb_id: int) -> Dict:
        """删除知识库"""
        response = requests.delete(f"{self.base_url}/api/knowledge-bases/{kb_id}")
        return self._handle_response(response)

    # ========== 文件管理 ==========

    def get_kb_files(self, kb_id: int) -> List[Dict]:
        """获取知识库下的所有文件"""
        response = requests.get(f"{self.base_url}/api/knowledge-bases/{kb_id}/files")
        data = self._handle_response(response)
        return data.get("files", [])

    def upload_file(self, kb_id: int, file_path: Union[str, Path], original_filename: str = None) -> Dict:
        """
        上传文件到知识库

        Args:
            kb_id: 知识库ID
            file_path: 临时文件路径
            original_filename: 原始文件名（必须传递！）
        """
        # 统一转换为Path对象
        if isinstance(file_path, str):
            file_path = Path(file_path)

        # 检查文件是否存在
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        # 使用原始文件名，如果没有提供则抛出异常
        if not original_filename:
            raise ValueError("必须提供原始文件名")

        file_name = original_filename
        logger.info(f"上传文件: kb_id={kb_id}, 文件名={file_name}")

        try:
            with open(file_path, "rb") as f:
                response = requests.post(
                    f"{self.base_url}/api/knowledge-bases/{kb_id}/files/upload",
                    files={"file": (file_name, f)},
                    timeout=30
                )
            return self._handle_response(response)
        except requests.exceptions.Timeout:
            logger.error("上传文件超时")
            raise Exception("上传文件超时，请稍后重试")
        except requests.exceptions.ConnectionError:
            logger.error("无法连接到后端服务")
            raise Exception("无法连接到后端服务，请检查网络")
        except Exception as e:
            logger.error(f"上传文件失败: {e}", exc_info=True)
            raise

    def rename_file(self, kb_id: int, file_name: str, new_name: str) -> Dict:
        """重命名文件"""
        response = requests.put(
            f"{self.base_url}/api/knowledge-bases/{kb_id}/files/{file_name}/rename",
            json={"new_name": new_name}
        )
        return self._handle_response(response)

    def delete_file(self, kb_id: int, file_name: str) -> Dict:
        """删除文件"""
        response = requests.delete(
            f"{self.base_url}/api/knowledge-bases/{kb_id}/files/{file_name}"
        )
        return self._handle_response(response)

    # ========== 文件下载 ==========

    def download_file_url(self, kb_id: int, file_name: str) -> str:
        """
        生成文件下载链接

        Args:
            kb_id: 知识库ID
            file_name: 文件名（可以是原始文件名或带&前缀的文件名）

        Returns:
            完整的下载URL
        """
        # URL编码文件名，处理中文和特殊字符
        encoded_name = urllib.parse.quote(file_name)
        return f"{self.base_url}/api/knowledge-bases/{kb_id}/files/{encoded_name}/download"

    def download_file(self, kb_id: int, file_name: str) -> Optional[bytes]:
        """
        直接下载文件内容

        Args:
            kb_id: 知识库ID
            file_name: 文件名

        Returns:
            文件二进制内容，失败返回None
        """
        try:
            url = self.download_file_url(kb_id, file_name)
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.error(f"下载文件失败: {e}")
            return None

    # ========== 文件解析 ==========

    def parse_file(self, kb_id: int, file_name: str) -> Dict:
        """解析单个文件"""
        response = requests.post(
            f"{self.base_url}/api/knowledge-bases/{kb_id}/files/{file_name}/parse"
        )
        return self._handle_response(response)

    def parse_all_files(self, kb_id: int) -> Dict:
        """解析所有文件"""
        response = requests.post(
            f"{self.base_url}/api/knowledge-bases/{kb_id}/files/parse-all"
        )
        return self._handle_response(response)

    def get_parse_progress(self, kb_id: int) -> Dict:
        """获取解析进度"""
        response = requests.get(f"{self.base_url}/api/knowledge-bases/{kb_id}/parse-progress")
        data = self._handle_response(response)
        return data.get("progress", {})

    # ========== 文件搜索 ==========

    def search_file(self, kb_id: int, file_name: str) -> Optional[Dict]:
        """搜索文件"""
        try:
            response = requests.get(
                f"{self.base_url}/api/knowledge-bases/{kb_id}/search-file",
                params={"file_name": file_name},
                timeout=10
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            data = response.json()
            return data.get("file")
        except requests.exceptions.Timeout:
            logger.error("搜索请求超时")
            raise Exception("搜索服务超时，请稍后重试")
        except requests.exceptions.ConnectionError:
            logger.error("无法连接到后端服务")
            raise Exception("无法连接到后端服务，请检查网络")
        except Exception as e:
            if "404" in str(e):
                return None
            logger.error(f"搜索文件失败: {e}")
            raise


# 全局单例实例
api_client = ApiClient()