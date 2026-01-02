# 该模块提供 文件解析、集合删除功能,用到Qdrant数据库
import os
from time import sleep
from httpx import ReadTimeout
from qdrant_client.http.exceptions import ResponseHandlingException
from tqdm import tqdm
from pathlib import Path
from qdrant_client import QdrantClient
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client.http.models import Distance, VectorParams
from load_file_2_Doc import load_txt,load_pdf_simply,load_pdf_with_Azure,load_md,load_docx_simply,load_pptx_simply
from service_models.KB import KnowledgeBase
from tenacity import retry, stop_after_attempt, wait_fixed
from pydantic import SecretStr

# 读取一些全局变量
PAID_OPENAI_API_KEY = os.getenv('PAID_OPENAI_API_KEY')
FREE_OPENAI_API_KEY = os.getenv('FREE_OPENAI_API_KEY',"sk-h232CWVa1CKk0MI03s22pSR1B9HZrKFGqsiSmdb9xtaImb4W")
OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL')
QDRANT_HOST = os.getenv('QDRANT_HOST','127.0.0.1')
QDRANT_PORT = int(os.getenv('QDRANT_PORT', "6333"))
UNSTRUCTURED_API_KEY=os.getenv('UNSTRUCTURED_API_KEY')

if not PAID_OPENAI_API_KEY:
    raise ValueError("付费OpenAI API密钥未设置，请检查环境变量")
# 创建embeddings实例
embeddings = OpenAIEmbeddings(
    model="text-embedding-ada-002",
    api_key=SecretStr(PAID_OPENAI_API_KEY) if PAID_OPENAI_API_KEY else None
)

# Qdrant数据库客户端，用于创建向量库实例、删除collection
client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT,timeout=60*2,check_compatibility=False)

vector_stores={ }
def get_vector_store(collection_name):
    global vector_stores # 修改全局变量需要使用global声明
    if collection_name in vector_stores:
        return vector_stores[collection_name]
    else:
        # 创建vector_store实例前，必须确保该集合存在于向量数据库中。
        create_collection_if_not_exists(collection_name)
        vector_store = QdrantVectorStore(
            client=client,
            collection_name=collection_name,
            embedding=embeddings,
        )
        vector_stores[collection_name] = vector_store
        return vector_store
def create_collection_if_not_exists(collection_name, max_retries=5, delay=5):
    for attempt in range(max_retries):
        try:
            # 尝试检查集合是否存在
            if client.collection_exists(collection_name):
                return True

            print(f"第 {attempt + 1} 次尝试创建集合 {collection_name}")
            flag = client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
            )

            if flag:
                print("集合创建成功")
                return True
            else:
                print("集合创建失败")

        except (ReadTimeout, ResponseHandlingException, Exception) as e:
            print(f"⚠️ 第 {attempt + 1} 次操作失败：{e}")

            # 特殊处理连接错误
            if "10054" in str(e) or "远程主机强迫关闭" in str(e):
                print(f"🔄 检测到网络连接问题，等待 {delay} 秒后重试...")

            if attempt < max_retries - 1:
                print(f"等待 {delay} 秒后重试...")
                sleep(delay)
            else:
                print("❌ 达到最大重试次数，放弃操作")
                return False
    return False

def delete_collection(KB,KB_dir:Path):
    collection_name=get_collection_name(KB_dir,KB)
    if client.collection_exists(collection_name):
        client.delete_collection(collection_name)
        # print(f"集合 {collection_name} 已删除")
        return True
    else:
        # print(f"集合 {collection_name} 不存在，无需删除")
        return False
def get_collection_name(KB_dir:Path,KB:KnowledgeBase):
    # 从用户知识库路径（绝对路径）KB_dir和KB.kb_id中获取集合名
    # str(KB_dir)=C:/QA-App/all_users_files/user2117543200@qq.com/测试知识库
    # KB.kb_id=499
    # 那么返回值为 user2117543200@qq.com_KB_499
    KB_dir_str=str(KB_dir)
    parts = KB_dir_str.split(os.sep)
    if len(parts) < 5:
        print(f"KB_dir: {KB_dir}")
        print('的格式不正确，导致切分错误，格式应为 f"./all_users_files/user{user_email}/{kb_name}"')
        print("但是实际却为parts:", parts)
        return None
    user_and_email = parts[-2]
    # 组合 user_email 和 kb 和 kb_id 为集合名
    # print(f"从 {KB_dir} \n得到的集合名称为: {user_and_email}_KB_{KB.kb_id}")
    return f"{user_and_email}_KB_{KB.kb_id}"

@retry(stop=stop_after_attempt(5), wait=wait_fixed(3))
def safe_add_documents(vector_store, docs):
    try:
        vector_store.add_documents(docs)
        print(f"✅ 成功插入 {len(docs)} 个Doc")
    except Exception as e:
        print(f"⚠️ 插入失败 (文档数: {len(docs)})。错误: {e}")
        # 特殊处理Qdrant特定错误
        if "timed out" in str(e):
            print("建议: 检查Qdrant服务状态或增大客户端超时时间")
        raise

def index_file_backend(file_path:Path,KB_dir:Path,KB:KnowledgeBase):
    # 获取与该知识库对应的向量库实例
    collection_name=get_collection_name(KB_dir,KB)
    vector_store = get_vector_store(collection_name)
    # 获取该文件后缀名
    file_type = os.path.splitext(file_path)[1]
    file_path=str(file_path)
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
        return
    print(f"已经成功把文件加载为Doc对象，长度为{len(docs)}")

    # 对于docs列表中每一Doc，逐个存储
    length=len(docs)
    for index in range(0,length):
        # 插入向量库
        safe_add_documents(vector_store,[docs[index]])
        # print(f"当前进度 {index+1}/{length} Doc ，即 {int((index+1)/length * 100)} %")
        # index为当前doc的索引，从0开始
        yield index , length

def index_KB_with_tqdm(KB_dir:Path, KB:KnowledgeBase):
    # 整个KB索引化流程：
    # 2117543200@qq.com创建一个知识库kb0-->服务器在all_users_files/user2117543200@qq.com/文件夹下创建一个kb0文件夹
    # 用户上传文件到该知识库，
    # 用户前端点击“全部解析"按钮，
    # 后端调用index_KB()函数，该函数会遍历该知识库下的所有文件，并调用相应的文件加载函数得到文本表示Docs，vector_store负责将Docs嵌入到与该知识库对应的collection中。

    # 1、从KB_dir中获取collection_name
    collection_name = get_collection_name(KB_dir,KB)
    if collection_name is None:
        print("无法从指定的路径中获取集合名，请检查路径格式是否正确")
        return
    # 检查集合是否存在，如果不存在则创建它
    create_collection_if_not_exists(collection_name)
    # 2、获取与集合绑定的向量数据库
    vector_store=get_vector_store(collection_name)

    # 3、遍历目录下的所有新文件，使用tqdm库显示进度条，遍历到文件时加载并存储。
    print(f"正在遍历知识库 {KB_dir} 下的文件\n================================================================")
    # 使用tqdm包裹生产器，在迭代时显示进度
    for file_path in tqdm(KB_dir.iterdir()):
        if file_path.is_file():
            print(f"正在处理文件 {file_path}...")
            # 3.1获取该文件的类型
            file_type = file_path.suffix
            # 3.2根据文件类型switch调用对应的加载函数（txt、pdf、md、docx、pptx）
            docs=None
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
            if docs is not None and len(docs)>0:
                # 3.3对于docs列表，以每5个doc为一组进行存储，使用tdqm显示进度条
                for i in tqdm(range(0, len(docs), 5)):
                    # 获取当前块的文档（确保不会超出列表长度）
                    if i + 5 > len(docs):
                        docs_chunk = docs[i:]
                    else:
                        docs_chunk = docs[i:i + 5]
                    # 将这一组存储到向量数据库中
                    vector_store.add_documents(docs_chunk)
                print(f"知识库 {KB_dir.name} 索引化结束\n")


if __name__ == "__main__":
    print(client.get_collections())
    print("======Qdrant客户端与服务端连接正常======")
    # 索引化默认用户的测试知识库中一个文件。
    for index,length in index_file_backend(
        Path(
            r"/all_users_files/user2117543200@qq.com/测试知识库/&4.10MW高温气冷实验堆蒸汽发生器传热管流体诱发振动分析.pdf"),
        Path(r"D:\Python\PyCharm_Workspace\QA-App\all_users_files\user2117543200@qq.com\测试知识库"),
        KnowledgeBase(49, "whatever")
    ):
        print("收到，要更新session_state中相应文件的的解析进度")

