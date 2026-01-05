#该模块负责使用PyPDFLoader提取测试pdf文件文本并存储到向量数据库中
#加载和存储数据一般在离线情况下本地进行，只需要两个组件：嵌入模型、向量数据库


# 0、加载和读取
from dotenv import load_dotenv
import os

load_dotenv(override=True)
OPENAI_API_KEY = os.getenv('FREE_OPENAI_API_KEY')
OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL')
QDRANT_HOST = os.getenv('QDRANT_HOST')
QDRANT_PORT = int(os.getenv('QDRANT_PORT', "6333"))
COLLECTION_NAME = os.getenv('COLLECTION_NAME')


# 1、加载嵌入模型
from langchain_openai import OpenAIEmbeddings

embeddings = OpenAIEmbeddings(model="text-embedding-ada-002", )
embeddings.openai_api_key = OPENAI_API_KEY
embeddings.openai_api_base = OPENAI_BASE_URL

# 2、加载向量数据库
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams

client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT,timeout=15)
# 检查测试集合是否存在，如果存在则删除(确保每次导入都是重新构建知识库)
if client.collection_exists(COLLECTION_NAME):
    client.delete_collection(collection_name=COLLECTION_NAME)
    print(f"测试集合{COLLECTION_NAME} 已成功删除！")
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
    )

vector_store = QdrantVectorStore(
    client=client,
    collection_name=COLLECTION_NAME,
    embedding=embeddings,
)

#3、加载、切分和存储（如果该数据库集合已经存在，就不再进行了）
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

file_path = "../test_files/1.10MW 高温堆热启动时蒸汽发生器.pdf"
loader = PyPDFLoader(file_path)
docs = loader.load()

text_splitter = RecursiveCharacterTextSplitter(
        separators=[
            "\n\n",    #空行，常作为不同章节的分割标志
            "\n",      #换行符，常作为段落之间或文本与公式之间的分割标志
            " ",       #空格，常作为英文单词之间分割标志
            ".",
            ",",
            "\u200b",  # Zero-width space (零宽空格): （不可见）
            "\uff0c",  # Fullwidth comma (全角逗号): ，
            "\u3001",  # Ideographic comma (顿号): 、
            "\uff0e",  # Fullwidth full stop (全角句号): ．
            "\u3002",  # Ideographic full stop (句号): 。
            "",
        ],
        chunk_size=500, chunk_overlap=200, add_start_index=True
    )
all_splits=text_splitter.split_documents(docs)
# 将docs存储到向量数据库中（也有可能是更新）
vector_store.add_documents(documents=all_splits)

print("测试用的PDF文件导入完成!")
