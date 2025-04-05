from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

def show_PyPDFLoader():
    file_path = "../test_files/1.10MW 高温堆热启动时蒸汽发生器.pdf"
    loader = PyPDFLoader(file_path)

    # 加载一个文件，pages是列表，每一元素Document对应pdf文件中的一页，还包括元数据
    pages = loader.load()

    print("pdf文件的第一页对应的元数据为:", end="\n")
    #遍历元数据pages[0].metadata这个字典
    for key, value in pages[0].metadata.items():
        print(f"{key}: {value}")
    print()
    print("pdf文件的第一页的文本为:", pages[0].page_content[:300], sep="\n",end="\n\n")

    # 将文档进行切分
    text_splitter = RecursiveCharacterTextSplitter(
        separators=[
            "\n\n",
            "\n",
            " ",
            ".",
            ",",
            "\u200b",  # Zero-width space
            "\uff0c",  # Fullwidth comma
            "\u3001",  # Ideographic comma
            "\uff0e",  # Fullwidth full stop
            "\u3002",  # Ideographic full stop
            "",
        ],
        chunk_size=500, chunk_overlap=200, add_start_index=True
    )
    # pages经过spilt后没有改变类型，只是内容size小了并且元数据多了一个start_index，表明了该chunk在pdf中的起始字符位置
    chunks = text_splitter.split_documents(pages)

    # 输出前几个chunk
    for i in range(2):
        print(f"page切分后得到的chunk {i}的内容为:")
        print(chunks[i].page_content, end="\n\n")



if __name__ == "__main__":
    show_PyPDFLoader()
