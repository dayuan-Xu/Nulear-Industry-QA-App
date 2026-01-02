from service_models.KB import KnowledgeBase
from service_models.chat import Chat
from db_utils import get_user_id, get_KBs, get_chats, insert_KB

class User:
    def __init__(self, email:str, password:str):
        self.id= None
        self.email = email
        self.password = password
        # 该用户所有知识库(知识库文件不是在数据库中，而时在服务器主机的文件系统里）
        self.know_bases: list[KnowledgeBase] = []
        # 该用户的所有对话
        self.chats: list[Chat]  = []

    def complement_user_info(self):
        self.set_id()
        self.set_KBs()
        self.set_chats()

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
            # 如果对话列表非空
            self.chats = get_chats(self.email)
        else:
           self.chats=[]

    def get_collection_name(self, KB:KnowledgeBase):
        if KB is None:
            print("从KB对象获取collection_name失败，因为KB是None！！！")
            return None
        return f"user{self.email}_KB_{KB.kb_id}"

    def to_dict(self):
        return  {
            "id": self.id,
            "email": self.email,
            "password": self.password,
            "know_bases": self.know_bases,
            "chats": self.chats,
        }