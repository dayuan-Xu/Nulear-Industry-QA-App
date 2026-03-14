# Nulear-Industry-QA-App 核工业专业知识问答应用

# 0、技术参考
[LangChain官网](https://python.langchain.com/docs/how_to/)

# 1、项目介绍
本项目开发了一个面向核工业领域的智能问答系统，核心采用“混合检索+智能重排序”的增强型RAG架构。系统创新性地融合了语义向量检索与BM25关键词检索，实现对专业知识的双路精准召回；并引入基于CrossEncoder的智能重排序模块，对结果进行深度语义重排，确保生成答案的准确性与可信度。基于LangGraph构建的可配置工程化流水线，使系统具备了模块化、可扩展的生产级应用能力。本项目不仅解决了垂直领域知识获取的难题，更为工业场景的智能化知识管理提供了一个先进、可复用的技术范本。



# 2、项目运行
- 将远程仓库的文件克隆到本地：git clone https://github.com/dayuan-Xu/Nulear-Industry-QA-App
- 先创建虚拟环境，项目根目录下打开PowerShell，执行python -m venv .venv，之后安装项目所需要的所有Python包依赖：pip install -r requirements.txt
- 数据库准备
  - 安装dockerdesktop
  - 创建并运行Qdrant向量数据库容器：PowerShell下运行命令 docker run -p 6333:6333 -v ${PWD}/qdrant_storage:/qdrant/storage qdrant/qdrant（或者使用docker desktop的图形化界面完成创建）
  - 创建并允许PostgreSQL数据库：PowerShell下运行命令
  ```powershell
  docker run --name postgres `
  -e POSTGRES_PASSWORD=postgres `
  -d -p 5442:5432 `
  -v ${PWD}/postgres_data:/var/lib/postgresql `
  postgres
  ```
  - 进入PostgresSQL数据库：docker exec -it mypostgres psql -U postgres （或者通过docker desktop的图形化界面进入该容器的exec标签页，执行psql -U postgres）
  - 创建业务表：
  ```sql
  -- 1. 创建用户表（基础表，其他表关联此表的user_id）
  CREATE TABLE IF NOT EXISTS users (
      id SERIAL PRIMARY KEY,  -- 自增主键
      email VARCHAR(255) NOT NULL UNIQUE,  -- 邮箱唯一，不允许重复
      password VARCHAR(255) NOT NULL,  -- 存储加密后的密码（不要存明文）
      created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP  -- 可选：添加创建时间，默认当前时间
  );
  -- 2. 创建聊天表（关联用户表）
  CREATE TABLE IF NOT EXISTS chats (
      thread_id SERIAL PRIMARY KEY,  -- 会话ID（自增）
      thread_title VARCHAR(255) NOT NULL,  -- 会话标题
      created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 创建时间，默认当前时间
      user_id INTEGER NOT NULL,  -- 关联用户ID
      -- 外键约束：确保user_id必须存在于users表中
      CONSTRAINT fk_chats_user FOREIGN KEY (user_id) 
          REFERENCES users(id) 
          ON DELETE CASCADE  -- 当用户删除时，关联的聊天记录也删除
  );
  -- 3. 创建知识库表（关联用户表）
  CREATE TABLE IF NOT EXISTS knowledge_bases (
      kb_id SERIAL PRIMARY KEY,  -- 知识库ID（自增）
      name VARCHAR(255) NOT NULL,  -- 知识库名称
      doc_number INTEGER DEFAULT 0,  -- 文档数量，默认0
      created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 创建时间
      user_id INTEGER NOT NULL,  -- 关联用户ID
      -- 外键约束：确保user_id必须存在于users表中
      CONSTRAINT fk_kb_user FOREIGN KEY (user_id) 
          REFERENCES users(id) 
          ON DELETE CASCADE  -- 当用户删除时，关联的知识库也删除
  );
  ```
- 在Postgres数据库中添加默认管理员账号信息，执行下面的命令：
```sql
INSERT INTO users (email, password)
VALUES ('2117543200@qq.com', '123456');
```
- 单独运行LangChain_Learning/setup.py，在postgres容器中创建持久化LangGraph State所需的表。

- 运行项目：根目录下打开PowerShell终端，激活项目虚拟环境（.venv\Scripts\activate.bat
），执行streamlit run app.py


