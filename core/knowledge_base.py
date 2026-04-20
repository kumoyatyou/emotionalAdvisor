import os
import time
import threading
from typing import List, Any
from langchain_core.documents import Document

# 预热 tiktoken 避免并发加载时的 RustBindingsAPI 线程安全 Bug
try:
    import tiktoken
    tiktoken.get_encoding("cl100k_base")
except Exception:
    pass

class KnowledgeBase:
    """
    长期知识库管理类。负责数据的提纯、向量化存储和检索。
    """
    def __init__(self, persist_directory: str = "./db"):
        self.persist_directory = persist_directory
        self._embeddings = None
        self._vector_db = None
        self._text_splitter = None
        self.lock = threading.Lock()

    @property
    def embeddings(self):
        if self._embeddings is None:
            # 从环境变量读取配置，支持自定义 API Base 和 Model
            api_key = os.getenv("OPENAI_API_KEY")
            base_url = os.getenv("OPENAI_API_BASE")
            embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
            
            from langchain_openai import OpenAIEmbeddings
            self._embeddings = OpenAIEmbeddings(
                openai_api_key=api_key,
                openai_api_base=base_url,
                model=embedding_model,
                chunk_size=50 # 强制设置底层 OpenAIClient 的分批大小为 50，解决 SiliconFlow 的 64 限制
            )
        return self._embeddings

    @property
    def vector_db(self):
        if self._vector_db is None:
            from langchain_chroma import Chroma
            self._vector_db = Chroma(
                persist_directory=self.persist_directory,
                embedding_function=self.embeddings
            )
        return self._vector_db

    @property
    def text_splitter(self):
        if self._text_splitter is None:
            from langchain_text_splitters import RecursiveCharacterTextSplitter
            self._text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200
            )
        return self._text_splitter

    def add_data(self, raw_data: Any, contact_id: str = "default", purify: bool = True):
        """
        对原始数据进行提纯并构建知识库。
        对超长聊天记录进行会话分块（按条数聚合），提升向量检索的上下文连贯性并避免 Token/API 限流。
        """
        all_docs = []
        if isinstance(raw_data, list):
            # 将多条消息合并为一个有上下文的文本块，比如每 50 条合并一次
            chunk_size = 50
            for i in range(0, len(raw_data), chunk_size):
                chunk_items = raw_data[i:i+chunk_size]
                chunk_texts = [self._purify_data(item) if purify else str(item) for item in chunk_items]
                merged_text = "\n".join(chunk_texts)
                all_docs.append(Document(page_content=merged_text, metadata={"source": "wechat_log", "contact_id": contact_id}))
        else:
            text = self._purify_data(raw_data) if purify else str(raw_data)
            all_docs.append(Document(page_content=text, metadata={"source": "raw_data", "contact_id": contact_id}))

        # 先分块
        split_docs = self.text_splitter.split_documents(all_docs)
        if not split_docs:
            return
            
        # 分批写入向量数据库，确保每批不超过 SiliconFlow 的限制 (64)
        # 使用锁保护 ChromaDB 的并发写入
        with self.lock:
            batch_size = 50
            for i in range(0, len(split_docs), batch_size):
                batch = split_docs[i : i + batch_size]
                self.vector_db.add_documents(batch)
                if i + batch_size < len(split_docs):
                    time.sleep(0.5) # 限流保护

    def _purify_data(self, item: Any) -> str:
        """
        针对微信聊天记录优化的提纯逻辑。
        """
        if isinstance(item, dict):
            # 优先从 WeChat JSON 结构中提取
            sender = item.get("senderDisplayName", item.get("sender", "Unknown"))
            content = item.get("content", "")
            time = item.get("formattedTime", item.get("time", ""))
            
            if content:
                return f"[{time}] {sender}: {content}"
            
            import json
            return json.dumps(item, ensure_ascii=False)
        return str(item)

    def query(self, query_text: str, contact_id: str = None, k: int = 5) -> List[Document]:
        """
        从知识库中检索相关内容。
        :param contact_id: 如果提供，则只在指定联系人的数据中搜索
        """
        search_kwargs = {}
        if contact_id:
            search_kwargs["filter"] = {"contact_id": contact_id}
            
        with self.lock:
            return self.vector_db.similarity_search(query_text, k=k, **search_kwargs)
