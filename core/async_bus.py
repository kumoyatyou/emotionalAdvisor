import asyncio
import time
import uuid
from typing import Any, Dict, List, Optional, Callable
from pydantic import BaseModel, Field

class Message(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sender: str
    content: str
    timestamp: float = Field(default_factory=time.time)
    metadata: Dict[str, Any] = {}

class AsyncDialogueBus:
    """
    异步消息总线，负责处理高并发的对话请求。
    """
    def __init__(self, max_concurrency: int = 500):
        self.queue = asyncio.Queue()
        self.max_concurrency = max_concurrency
        self.handlers: Dict[str, Callable] = {}
        self._running = False
        self._tasks = []

    def register_handler(self, message_type: str, handler: Callable):
        self.handlers[message_type] = handler

    async def push(self, message_type: str, payload: Any) -> Any:
        """推送消息并等待处理结果"""
        future = asyncio.get_event_loop().create_future()
        await self.queue.put((message_type, payload, future))
        return await future

    async def start(self):
        self._running = True
        # 启动并发工作协程
        for _ in range(self.max_concurrency):
            task = asyncio.create_task(self._worker())
            self._tasks.append(task)

    async def stop(self):
        self._running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    async def _worker(self):
        while self._running:
            try:
                msg_type, payload, future = await self.queue.get()
                if msg_type in self.handlers:
                    try:
                        # 执行注册的处理程序
                        result = await self.handlers[msg_type](payload)
                        future.set_result(result)
                    except Exception as e:
                        future.set_exception(e)
                else:
                    future.set_exception(ValueError(f"No handler for {msg_type}"))
                self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Worker error: {e}")
