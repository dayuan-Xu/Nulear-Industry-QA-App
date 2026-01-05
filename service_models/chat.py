from datetime import datetime
from typing import TypedDict
class Chat(TypedDict, total=False):
    thread_id: str
    thread_title: str
    created_time: datetime