# 加载和读取
from dotenv import load_dotenv
import os

load_dotenv(override=True)
OPENAI_API_KEY = os.getenv('FREE_OPENAI_API_KEY')
OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL')
from langchain.chat_models import init_chat_model
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage
#配置一个llm，方便下面的测试函数使用:
llm = init_chat_model("gpt-3.5-turbo", model_provider="openai",api_key=OPENAI_API_KEY,base_url=OPENAI_BASE_URL)

def check_AiMessage_format():
    #该方法检查LangChain中对于llm输出的封装，即AiMessage的确切格式
    AiMessage=llm.invoke("给我讲一个笑话") #此处直接传入一个str，但是invoke方法内部会将该str自动封装成一个HumanMessage，再封装进一个消息列表List[BaseMessage]，于是llm接受的还是一个消息列表。
    print("AiMessage的结构为:\n")
    for key, value in vars(AiMessage).items():
        # 输出vars(AiMessage_format)中每个键值对
        print(f"{key}: {value}")

def check_PromptValue_format():
    #该方法检查提示词模板invoke后的返回值类型PromptValue的结构
    template="""你是一名核工业专业知识问答助理。使用下面检索到的上下文信息回答提问。
            如果检索到的上下文信息对于生成答案没有帮助，请直接告诉我你不知道。
            最多使用三条检索到的信息，确保答案简明。
            总是以“欢迎你再次提问！”作为每次回答的结尾。
            提问: {question} 
            上下文: {context} 
            回答:"""
    prompt_template = PromptTemplate.from_template(template)
    messages = prompt_template.invoke({"question":"你是谁？？", "context":"这是上下问的内容"})
    for key,value in vars(messages).items():
        print(f"{key}: {value}")

class schema(BaseModel):
    # 这种定义输出结构的类，本质上是只是让llm以特定格式回答，各个键的值仍然是由llm生成的。
    answer: str = Field(description="The answer to the user's question ")
    followup_question: str = Field(description="The following question that may be asked by user")
def check_structured_output():
    # 该函数是用于测试llm的结构化输出。
    global llm
    llm=llm.with_structured_output(schema)
    # 传入一个消息列表，其中只包含一个LangChain中的HumanMessage对象
    structred_response = llm.invoke([HumanMessage(content="给我讲一个笑话")])
    print(structred_response)

def check_stream_output():
    # 该函数是用于测试llm的流式输出。
    for chunk in llm.stream("给我讲一个500字的笑话"):
        #print(chunk)
        print(chunk.content,end="")

if __name__ == "__main__":
    check_AiMessage_format()
