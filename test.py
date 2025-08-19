import sys
print(sys.path)
from qdrant_client import QdrantClient

client = QdrantClient(host="localhost", port=6333)

try:
    collections = client.get_collections()
    print("Qdrant 连接成功！当前集合列表：", collections)
except Exception as e:
    print("连接失败：", e)
