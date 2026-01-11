from rank_bm25 import BM25Okapi
from typing import Tuple, List
import numpy as np
from threading import Lock
import jieba
class BM25Singleton:
    """全局单例：每个collection只构建一次BM25索引"""
    _instances: dict = {}
    _lock = Lock()
    
    def __new__(cls, collection_name: str):
        if collection_name not in cls._instances:
            with cls._lock:
                if collection_name not in cls._instances:
                    instance = super().__new__(cls)
                    instance.collection_name = collection_name
                    instance._build_index()
                    cls._instances[collection_name] = instance
        return cls._instances[collection_name]
    
    def _build_index(self):
        """构建BM25索引（仅首次调用）"""
        from indexing import get_vector_store  # 替换为实际模块名
        
        vector_store = get_vector_store(self.collection_name)
        all_docs = vector_store.similarity_search(self.collection_name, k=1000)
        
        # 支持中英文混合分词
        import jieba
        corpus = []
        for doc in all_docs:
            chinese_tokens = jieba.lcut(doc.page_content)
            english_tokens = doc.page_content.lower().split()
            corpus.append(chinese_tokens + english_tokens)
        
        self.bm25 = BM25Okapi(corpus)
        self.all_docs = all_docs
    
    def retrieve(self, query: str, k: int = 4) -> Tuple[List, np.ndarray]:
        """检索返回 docs 和 scores"""
        query_tokens = jieba.lcut(query) + query.lower().split()
        scores = self.bm25.get_scores(query_tokens)
        top_indices = np.argsort(scores)[::-1][:k]
        docs = [self.all_docs[i] for i in top_indices]
        return docs, scores[top_indices]