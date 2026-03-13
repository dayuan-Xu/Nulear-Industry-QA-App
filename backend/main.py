from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import knowledge_bases
from contextlib import asynccontextmanager
import logging

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时执行
    logger.info("Starting FastAPI application...")
    yield
    # 关闭时执行
    logger.info("Shutting down FastAPI application...")

app = FastAPI(
    title="知识库管理系统API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],  # Streamlit默认端口
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(knowledge_bases.router)

@app.get("/")
async def root():
    return {"message": "知识库管理系统API服务运行中"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}