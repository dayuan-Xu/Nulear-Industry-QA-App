from datetime import datetime

from models.KB import KnowledgeBase
from models.chat import Chat
from models.config import Config
from db_utils import get_user_id, get_KBs, get_chats, insert_KB


class User:
    def __init__(self, email:str, password:str):
        self.id=None
        self.email = email
        self.password = password
        # 该用户所有知识库(知识库文件不是在数据库中，而时在服务器主机的文件系统里）
        self.know_bases = None
        # 该用户所有对话的thread_id
        self.chats = None
        self.config = None

    def complement_user_info(self):
        self.set_id()
        self.set_KBs()
        self.set_chats()
        self.set_config()

    def set_id(self):
        self.id=get_user_id(self.email)
        if self.id is None:
            print(f"用户邮箱:{self.email}, 密码:{self.password}于数据库中不存在!")

    def set_KBs(self):
        # 总是从数据库获取最新知识库
        db_kbs = get_KBs(self.id)

        if db_kbs:
            # 如果数据库有已经创建的知识库
            self.know_bases = db_kbs
            # print(f"从数据库加载了 {len(db_kbs)} 个知识库")
        else:
            # 如果数据库没有任何知识库，则删除提示
            # print("没有从数据库加载任何知识库")
            self.know_bases = []

    def set_chats(self):
        if get_chats(self.email):
            self.chats = get_chats(self.email)
        else:
            Chat1 = Chat(thread_id="abc123", thread_title="对话1")
            Chat2 = Chat(thread_id="abc124", thread_title="对话2")
            Chat3 = Chat(thread_id="abc125", thread_title="对话3")
            self.chats = [Chat1, Chat2, Chat3]

    def set_config(self):
        # 该方法访问数据库，获取该用户上次的graph配置,现在先给出默认配置
        if len(self.know_bases)==0:
            self.config = None
        else:
            target_collection_name = self.get_collection_name(self.know_bases[0])
            self.config = Config(target_collection_name=target_collection_name,max_ctx_retrieved=3)

    def get_collection_name(self,KB:KnowledgeBase):
        return f"user{self.email}_KB_{KB.kb_id}"

    def to_dict(self):
        return  {
            "id": self.id,
            "email": self.email,
            "password": self.password,
            "know_bases": self.know_bases,
            "chats": self.chats,
            "config": self.config
        }