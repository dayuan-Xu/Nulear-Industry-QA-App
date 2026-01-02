from datetime import datetime
class KnowledgeBase:
    def __init__(self, kb_id: int, name: str, doc_number: int = 0, created_time:datetime = None, path: str = None):
        self.kb_id = kb_id
        self.name = name
        self.doc_number = doc_number
        self.created_time = created_time
        self.path = path