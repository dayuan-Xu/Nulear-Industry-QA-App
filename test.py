import requests

try:
    response = requests.get("http://localhost:6333", timeout=5)
    print(f"Qdrant 服务状态: {response.status_code}")
except Exception as e:
    print(f"无法连接 Qdrant: {e}")