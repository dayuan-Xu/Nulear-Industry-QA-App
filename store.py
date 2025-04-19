# 该模块负责指定目录的所有文件加载、存储到向量数据库中对应的集合。
# index(kb_dir:str)
# kb_dir:用户的某个知识库在服务器上的文件夹路径，内部是一系列文件。

# 0、加载和读取
from dotenv import load_dotenv
import os
load_dotenv(override=True)
OPENAI_API_KEY = os.getenv('FREE_OPENAI_API_KEY')
OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL')
QDRANT_HOST = os.getenv('QDRANT_HOST')
QDRANT_PORT = int(os.getenv('QDRANT_PORT', "6333"))
COLLECTION_NAME = os.getenv('INDEXING_COLLECTION_NAME')
UNSTRUCTURED_API_KEY=os.getenv('UNSTRUCTURED_API_KEY')

# 1、加载嵌入模型，提供给向量数据库使用。
from langchain_openai import OpenAIEmbeddings
embeddings = OpenAIEmbeddings(model="text-embedding-ada-002", )
embeddings.openai_api_key = OPENAI_API_KEY
embeddings.openai_api_base = OPENAI_BASE_URL

# 2、加载Qdrant数据库客户端，用于操作集合。
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams
client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT,timeout=10)


from tqdm import tqdm
from load_file import load_txt,load_pdf_simply,load_pdf_with_Azure,load_md,load_docx_simply,load_pptx_simply
# 索引化流程：
# user0创建一个知识库kb0-->服务器在all_users_files/user0文件夹下创建一个kb0文件夹
# 用户上传文件到该知识库，后端调用index()函数，该函数会遍历该知识库下的所有文件，并调用不同的加载函数，将文件加载到向量数据库中。
def index(kb_dir:str):
    # 1、从kb_dir中获取collection_name
    # 已知入参kb_dir格式为all_users_files/{user_email}/{kb_name}，那么就将user_email_kb_name设置为集合名并返回，写一个函数实现该逻辑
    collection_name = get_collection_name_from_kb_dir(kb_dir)
    if collection_name is None:
        print("无法从指定的路径中获取集合名，请检查路径格式是否正确")
        return
    create_collection_if_not_exists(client, collection_name)

    # 2、获取与集合绑定的向量数据库
    vector_store = QdrantVectorStore(
        client=client,
        collection_name=collection_name,
        embedding=embeddings,
    )
    # 3、遍历目录下的所有新文件，使用tqdm库显示进度条，遍历到文件时加载并存储。
    print(f"正在遍历知识库 {kb_dir} 下的文件...")
    for file in tqdm(os.listdir(kb_dir)):
        file_path = os.path.join(kb_dir, file)
        if os.path.isfile(file_path):
            print(f"正在处理文件 {file_path}...")
            # 3.1获取该文件的类型
            file_type = os.path.splitext(file_path)[1]
            # 3.2根据文件类型switch调用对应的加载函数（txt、pdf、md、docx、pptx）
            if file_type == ".txt":
                docs = load_txt(file_path)
            elif file_type == ".pdf":
                docs = load_pdf_simply(file_path)
            elif file_type == ".md":
                docs = load_md(file_path)
            elif file_type == ".docx":
                docs = load_docx_simply(file_path)
            elif file_type == ".pptx":
                docs = load_pptx_simply(file_path)
            else:
                print(f"不支持该文件的类型：{file_type},已经跳过该文件")
            # 3.3对于docs列表，以每5个元素为一块进行存储，使用tdqm显示进度条
            for i in tqdm(range(0, len(docs), 5)):
                # 获取当前块的文档（确保不会超出列表长度）
                if i + 5 > len(docs):
                    docs_chunk = docs[i:]
                else:
                    docs_chunk = docs[i:i + 5]
                # 将文档块存储到向量数据库中
                vector_store.add_documents(docs_chunk)


# 从用户知识库路径中获取集合名
def get_collection_name_from_kb_dir(kb_dir: str) -> str:
    # 分割路径以获取 user_email 和 kb_name
    parts = kb_dir.split(os.sep)
    if len(parts) < 3:
        print("kb_dir:", kb_dir,end="\n")
        print("kb_dir 格式不正确，导致切分错误，应为 all_users_files/{user_email}/{kb_name}")
        print("但是实际却为parts:", parts)
        return None
    user_email = parts[1]
    kb_name = parts[2]
    # 组合 user_email 和 kb_name 为集合名
    collection_name = f"{user_email}_{kb_name}"
    return collection_name

# 检查集合是否存在，如果不存在则创建它
def create_collection_if_not_exists(client: QdrantClient, collection_name: str):
    if client.collection_exists(collection_name)==False:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
        )
        print(f"集合{collection_name} 已成功创建！")


if __name__ == "__main__":
    client.delete_collection(collection_name="user2117543200@qq.com_kb0")
    print("集合user2117543200@qq.com_kb0已删除\n================================================================")
    index(r"all_users_files\user2117543200@qq.com\kb0")

