from datetime import datetime

from models.KB import KnowledgeBase
from models.chat import Chat
from models.config import Config
from db_utils import get_user_id,get_KBs, get_chats


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
        if get_KBs(self.email):
            self.know_bases = get_KBs(self.email)
        else:
            KB1 = KnowledgeBase(kb_id=1, name="user2117543200@qq.com_kb0",  doc_number=4,created_time= datetime.now())
            KB2 = KnowledgeBase(kb_id=2, name="user2117543200@qq.com_kb1", doc_number=5,created_time= datetime.now())
            KB3 = KnowledgeBase(kb_id=3, name="user2117543200@qq.com_kb2",  doc_number=6,created_time= datetime.now())
            self.know_bases = [KB1, KB2, KB3]

    def set_chats(self):
        if get_chats(self.email):
            self.chats = get_chats(self.email)
        else:
            Chat1 = Chat(thread_id="abc123", thread_title="对话1")
            Chat2 = Chat(thread_id="abc124", thread_title="对话2")
            Chat3 = Chat(thread_id="abc125", thread_title="对话3")
            self.chats = [Chat1, Chat2, Chat3]

    def set_config(self):
        # 该方法访问数据库，获取该用户上次的graph配置
        self.config = Config(target_KB=self.know_bases[0])
        pass

