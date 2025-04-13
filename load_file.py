# 该模块基于LangChain的Document loaders：https://python.langchain.com/docs/how_to/#document-loaders
# 各个函数加载指定路径下的文件，返回一个List[Document]
# 对于文件的加载要求：仅仅要求提取出文件中的文本内容即可，不要求将文件中的图表、表格等复杂结构也转化为文本。

# 要求各个函数将文件内容加载为List[Document]后输出前几个doc看看是否正确。

import os
from typing_extensions import List
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

def load_txt(file_path:str)->List[Document]:
    # 该函数对一个TXT文件实现加载并返回List[Document]

    # 1、建立文本切分器
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
    # 2、获取所有文档对象
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

    # 3、为每一个doc的元数据添加一个属性metadat["source"]=file_path
    for i in range(len(all_docs)):
        all_docs[i].metadata["source"]=file_path
    print("测试用的TXT文件的被切分成为:", len(all_docs), "份\n")
    # 输出前三个元素查看是否成功加载
    for i in range(3):
        print(all_docs[i])
    # 4、返回该List[Document]
    return all_docs

from langchain.document_loaders import PyPDFLoader
def load_pdf_simply(file_path:str)->List[Document]:
    # 该方法基于pypdf库加载pdf文件，只是对pdf文件文本的简单快速提取。

    # 1、初始化加载器
    loader = PyPDFLoader(file_path=file_path)
    # 2、获取Doc列表，类型为List[Document]，此时每个doc对应pdf文件中的一页，显然需要对其内容进行切分
    docs = loader.load()
    # 3、输出该pdf文件中的总页数
    print("该pdf文件总页数：",len(docs))
    # 4、输出查看该pdf文件第一页的元数据和具体内容
    for key, value in docs[0].metadata.items():#遍历docs[0].metadata中的每一个键值对
        print(f"{key}: {value}")
    print(docs[0].page_content)
    # 5、对pdf文件中的每一页进行切分，并返回一个List[Document]
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
        chunk_size=500, chunk_overlap=200, add_start_index=True
    )
    all_splits=text_splitter.split_documents(docs)
    return all_splits

from langchain_unstructured import UnstructuredLoader
import pandas as pd
from io import StringIO
def load_pdf_with_Unstructured(file_path:str):
    # 该方法测试pdf文件的布局解析，使用Unstructured提供的API接口。
    # 优点：能够正确识别pdf文件中不同的结构类别，从而可以编码实现专门从指定结构中提取文本: 比如可以从表格中正确提取数据，从富文本图像中正确提取文本。
    # 缺点：对于公式、两行内容的表头识别可能不准确（可能与pdf文件本身清晰度有关）；没有把跨左右两栏的一个段落识别为一个整体

    # 1、初始化加载器
    if "UNSTRUCTURED_API_KEY" not in os.environ:
        print("未设置UNSTRUCTURED_API_KEY环境变量，请先设置该环境变量！")
    loader = UnstructuredLoader(
        file_path=file_path,
        strategy="hi_res",
        partition_via_api=True,
    )

    # 2、获取Doc列表
    docs = []
    # 此时其中每个Document对应PDF页面中的一个结构类别，
    # 结构类别包括：标题Title（节标题或者图表标题）、页眉Header、页码PageNumber、表格Table、图像Image、
    # 叙述性文本NarrativeText（正文段落或者图表名）、公式Formula以及无法识别类别的UncategorizedText
    for doc in loader.lazy_load():
        docs.append(doc)

    # 3、输出该pdf文件中的结构总数
    print("该pdf文件中的结构总数: ",len(docs),end="\n")

    # 4、输出查看指定页的所有结构
    page1_docs = [doc for doc in docs if doc.metadata.get("page_number") == 3]
    for doc in page1_docs:
        for key,value in doc.metadata.items():
            if key in ["parent_id","category","element_id","text_as_html"]:
                print(f"{key}: {value}")
        print("page_content:",doc.page_content)
        print()

from typing import List
from langchain.schema import Document
from langchain.document_loaders import UnstructuredMarkdownLoader
def load_md(file_path:str)->List[Document]:
    # 负责人：么一明
    # 该方法实现加载md文件，并返回一个List[Document]
    # clue：参考https://python.langchain.com/docs/how_to/document_loader_markdown/

    try:
        # 使用 LangChain 提供的 UnstructuredMarkdownLoader 加载 Markdown 文件
        loader = UnstructuredMarkdownLoader(file_path)
        # 加载文档并返回
        documents = loader.load()
        return documents
    except Exception as e:
        print(f"加载 Markdown 文件时出错: {e}")
        return []

    pass
def load_docx(file_path:str)->List[Document]:
    # 负责人：李宏伟
    # 该方法实现加载docx文件，并返回一个List[Document]
    # clue：参考https://python.langchain.com/docs/how_to/document_loader_office_file/
    pass
def load_pptx(file_path:str)->List[Document]:
    # 负责人： 高哲文
    # 该方法实现加载pptx文件，并返回一个List[Document]
    # clue：参考https://python.langchain.com/docs/how_to/document_loader_office_file/
    pass

if __name__ == "__main__":
    load_txt("test_files/核工业百科.txt")
    load_pdf_simply("test_files/1.10MW 高温堆热启动时蒸汽发生器.pdf")

    # 下面3个函数有待实现，已经分别指定了测试文件
    # load_md("test_files/LangChainIntroduction.md")
    # load_docx("test_files/大创开题报告.docx")
    # load_pptx("test_files/核工业专业知识问答模型构建-开题答辩.pptx")


