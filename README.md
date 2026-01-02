# Nulear-Industry-QA-App 核工业专业知识问答应用

[LangChian官网](https://python.langchain.com/docs/how_to/)

# 进度安排
- 4-5月：在本地实现对常见类型文件的解析和存储，如TXT文件、PDF文件、DOCX文件、PPTX文件。
- 6-7月：实现控制台多轮问答，同时完成一系列可视化工作（检索结果、令牌使用情况等）。
- 8-9月：学习Streamlit前端框架，设计Web用户界面，包含知识库管理、模型选择、问答（对话）界面管理。
- 10-12月：在后端实现Web界面的各种功能。
- 次年1月-2月：增加文件解析范围，比如CSV文件、HTML文件、MD文件。
- 次年3月：增加代理功能等优化工作。

# 常用命令(在工作目录下执行)
- 运行该项目：streamlit run Streamlit_App.py
- 生成本地环境中安装的所有python包: pip freeze > requirements.txt
- 将所有项目文件添加到暂存区: git add -A
- 将暂存区的文件提交到本地仓库: git commit -m "commit message"
- 将本地仓库提交到远程仓库: git push 
- 将远程仓库更新到本地仓库: git pull

# 过程记录
第1-4周： 
本地复现了GitHub上开源小项目[document.ai](https://github.com/GanymedeNil/document.ai)，理解了RAG框架的最简实现。
**Qdrant数据库服务**通过本地创建运行容器提供，这里通过本地目录挂载的方式创建了Qdrant数据库服务： `docker run -p 6333:6333 -v $(pwd)/qdrant_storage:/qdrant/storage qdrant/qdrant`

第5周：
针对一篇核工业论文构建了简单的测试问题集，完全采用LangChain提供的组件本地实现了简单的RAG问答。
阅读和本地复现了LangChain官网的Build a RAG App: Part 2，基于内存简单实现了多轮交互。

第6周：
试用了Unstructured库加载pdf文件文本，成功识别出各种文本结构，但对于表格识别精度还不够高，而且付费。

第7周：
试用了微软的Azure Form Recognizer服务，识别效果良好，但是付费。
根据LangChain官网提示，对MD、PPT、DOCX类型文件中的文本实现了简单快速的加载。

第8周：
在控制台问答中，实现了以下可视化工作：
1、检索结果可追溯，可以将工具调用结果保存到App状态。
2、令牌使用量，从每次调用llm的返回结果之中提取，简单地使用App状态的一个tokenUsage字段即可。
3、大量文件索引化时的进度可视化，可以调用现成的库。
文档检索进度可视化，由于调用Qdrant的接口中没有控制显示向量库检索进度的参数，无法可视化。

第9周：
实现了将给定目录下的所有文件（txt、pdf、md、docx、pptx）加载、存储到与用户知识库关联的向量数据库中的集合。
引入了持久化技术，将App状态（内含对话历史）保存到PostgreSQL数据库而不是内存中，通过App运行配置成功加载了历史对话。
**持久化实现详情**见RAG_part2_with_Postgres.py中的`checkpointer.setup()`的代码上下文

第10周：
添加一个摘要节点，当消息列表过长时，调用llm进行总结。

第12周：
快速入门streamlit，使用streamlit简单搭建起本项目的前端结构。
缺陷：前后端内容耦合，分离程度不够。

第13周：
学习streamlit基础知识，大概实现了QA界面。

第14周：
优化了一些代码，完善了QA界面。

第15周：
学习Streamit概念，优化了导航菜单。
**基于之前的Postgres容器**，设计了关系表，大致构建出数据库访问模块:
- users（id、email、password）
- chats（thread_id、thread_title、created_time、user_id)
- knowledge_bases(kb_id、name、doc_number、created_time、user_id）

第16周：
为一次完整的QA过程增加了spinner小组件，便于用户感知，初步设计了知识库管理界面。

第17周:
完善了知识库管理界面，包括全部知识库展示界面和单个知识库详情界面，
允许单个文件索引化和全部文件一键索引化。
成功解决了文件在后端异步解析时的进度在前端显示的问题。
使用对话框优化了QA界面中对话删除、重命名的操作。

小学期第1周:
大致构建了配置界面，允许用户的个性化配置。

优化空间:
1. 尝试将对话列表移出侧边栏，显示在QA页面左侧，同时防止它随着对话历史滚动到顶部，让用户看不见。
可以分页面为两列，在左边的一列添加一个底部容器，这样就能始终显示对话列表了？
   如何使得某文件得解析结果（底层模型识别该文件得到的文本、切分结果）呈现在Streamlit页面中？这肯定需要额外保存文档识别结果（md文件）和切分结果（txt文件）。
2. 提供更加精细的知识库文件索引化方案，比如切分chunk的大小、分段策略之类。
3. 提供更加精细的检索策略，比如检索目标KB时排除知识库中某些文件。
4. 提供根据单个文件的知识问答，这也涉及文件索引化，可以在索引化时增加chunk在全文中的位置的元数据（参考LangChain)。
5. 提供文档解析底层模型（付费的Azure、免费的MonkeyOCR）的选择空间。
   本地使用MonkeyOCR对本地主机显存要求至少8GB以上，可以将MonkeyOCR部署为远程服务供本项目调用。
6. 提供文本嵌入模型的选择空间。
7. 后台解析线程可以采用全局唯一的线程池技术。
8...参考LangChain中的How To列表寻找优化点