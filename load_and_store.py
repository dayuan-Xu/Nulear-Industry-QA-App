# 该模块负责加载、切分不同类型的测试文件，之后存储到向量数据库中的指定集合。


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

# 1、加载嵌入模型
from langchain_openai import OpenAIEmbeddings

embeddings = OpenAIEmbeddings(model="text-embedding-ada-002", )
embeddings.openai_api_key = OPENAI_API_KEY
embeddings.openai_api_base = OPENAI_BASE_URL

# 2、加载Qdrant数据库
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams

client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT,timeout=10)
# 检查测试集合是否存在，如果不存在则创建它；否则将它作为目标集合。
if client.collection_exists(COLLECTION_NAME)==False:
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
    )
    print(f"测试集合{COLLECTION_NAME} 已成功创建！")

# 一个本地向量数据库（与目标集合相关联）
vector_store = QdrantVectorStore(
    client=client,
    collection_name=COLLECTION_NAME,
    embedding=embeddings,
)

from typing_extensions import List
from langchain_core.documents import Document

def  store(docs: List[Document]):
    # 该方法只把已经切分好的docs存储到向量数据库中，没切分好的话不应该调用该函数
    vector_store.add_documents(documents=docs)


# 3、加载、切分和存储不同类型的文件：PDF文件、TXT文件、DOCX文件、PPTX文件
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_unstructured import UnstructuredLoader

def index_txt(file_path:str):
    # 该函数对一个TXT文件实现加载、切分、存储，要求加载为List[Document]后再存储。

    # 建立文本切分器
    text_splitter = RecursiveCharacterTextSplitter(
        separators=[
            "\n\n",  # 空行，常作为不同章节的分割标志
            "\n",  # 换行符，常作为段落之间或文本与公式之间的分割标志
            " ",  # 空格，常作为英文单词之间分割标志
            ".",
            ",",
            "\u200b",  # Zero-width space (零宽空格): （不可见）
            "\uff0c",  # Fullwidth comma (全角逗号): ，
            "\u3001",  # Ideographic comma (顿号): 、
            "\uff0e",  # Fullwidth full stop (全角句号): ．
            "\u3002",  # Ideographic full stop (句号): 。
            "",
        ],
        chunk_size=300, chunk_overlap=50, add_start_index=True
    )
    # 存储所有文档对象
    all_docs = []
    # 读文件，显式指定编码为 utf-8
    try:
        with open(file_path, encoding='utf-8') as f:
            content = ""
            while True:
                chunk = f.read(10000)  # 每次读取10000字节
                if not chunk:
                    break
                content += chunk
                # 每读取一定量的内容进行切分
                if len(content) > 100000:  # 根据需要调整阈值
                    texts = text_splitter.create_documents([content])
                    all_docs.extend(texts)
                    content = ""
    except UnicodeDecodeError:
        print(f"文件 {file_path} 使用的编码不是 utf-8，尝试使用 GBK 编码...")
        with open(file_path, encoding='gbk', errors='replace') as f:
            content = ""
            while True:
                chunk = f.read(10000)  # 每次读取10000字节
                if not chunk:
                    break
                content += chunk
                # 每读取一定量的内容进行切分
                if len(content) > 100000:  # 根据需要调整阈值
                    texts = text_splitter.create_documents([content])
                    all_docs.extend(texts)
                    content = ""

    # 处理剩余的内容
    if content:
        texts = text_splitter.create_documents([content])
        all_docs.extend(texts)
    # 存储到向量数据库中
    store(all_docs)

def index_pdf_simply(file_path:str):
    # 该函数对一个PDF文件实现简单的文本提取（不能识别布局），文本切分和存储。
    loader = PyPDFLoader(file_path)
    docs = loader.load()
    #查看docs的长度
    print("测试用的PDF文件的页数为:", len(docs),"\n")
    print(docs[3].page_content)
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
        chunk_size=300, chunk_overlap=50, add_start_index=True
        )
    #切分docs
    all_splits=text_splitter.split_documents(docs)
    # 存储到向量数据库中
    store(all_splits)
    print("测试用的PDF文件导入完成！")

def index_pdf_advanced(file_path:str):
    # 该方法对一个PDF文件实现布局识别和内容存储。
    # 该方法通过线上调用Unstructured库的付费API解析该pdf文件
    # 优点：能够分类识别pdf文件内容的布局，能够识别表格结构、图片中的文本。
    # 缺点：对于公式、两行的表头识别可能不准确（与pdf文件本身清晰度有关），对于跨栏段落无法识别为一个整体
    # 1、初始化加载器
    loader = UnstructuredLoader(
        file_path=file_path,
        strategy="hi_res",
        partition_via_api=True,
        api_key=UNSTRUCTURED_API_KEY,
    )
    # 2、获取结构并处理列表，仍然是一个List[Document]
    docs = []
    # 其中每个Document对应PDF页面中的一个结构，
    # 比如标题Title（节标题或者图表标题）、页眉Header、页码PageNumber、表格Table、图像Image、
    #     叙述性文本NarrativeText（正文段落或者图表名）、公式Formula以及无法识别类别的UncategorizedText
    for doc in loader.lazy_load():
        docs.append(doc)

    # 3、简单处理docs
    # 对类别为Table的doc的page_content进行重构:将表格的标题加入表格内容中
    for doc in docs:
        if doc.metadata.get("category") == "Table":
            tableTitleDoc = \
            [doc1 for doc1 in docs if doc1.metadata.get("element_id") == doc.metadata.get("parent_id")][0]
            if (tableTitleDoc != None):
                tableTitleDoc.page_content = tableTitleDoc.page_content + "\n" + doc.page_content
                doc.page_content = tableTitleDoc.page_content
                docs.remove(tableTitleDoc)
    # 删除符合以下条件的doc：
    # 类别为Header或者PageNumber或者UncategorizedText的
    # 类别为Title但是没有任何其他doc的metadata.get("parent_id")等于它的metadata.get("element_id")的
    for doc in docs:
        if doc.metadata.get("category") in ["Header", "PageNumber", "UncategorizedText"] or \
                (doc.metadata.get("category") == "Title" and
                 not any(d.metadata.get("parent_id") == doc.metadata.get("element_id") for d in docs)):
            docs.remove(doc)

    # 4、将所有结构存储到向量数据库中
    store(docs)

def index_md(file_path:str):
    # 该函数对一个MD文件实现加载、切分、存储，要求加载为List[Document]后再存储。
    pass
def index_docx(file_path:str):
    # 该函数对一个DOCX文件实现加载、切分、存储，要求加载为List[Document]后再存储。
    pass
def index_pptx(file_path:str):
    # 该函数对一个PPTX文件实现加载、切分、存储，要求加载为List[Document]后再存储。
    pass

if __name__ == "__main__":
    index_txt("test_files/核工业百科.txt");# 加载存储txt文件
    #index_pdf_advanced("test_files/1.10MW 高温堆热启动时蒸汽发生器.pdf")# 加载存储pdf文件

