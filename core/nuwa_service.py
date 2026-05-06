import asyncio
from typing import Dict, Any
from core.async_bus import AsyncDialogueBus
from skills.nuwa_skill import NuwaSkill

class NuwaService:
    """
    Nuwa 服务层：对接异步消息总线与 NuwaSkill。
    确保高并发场景下的性能表现。
    """
    def __init__(self, nuwa_skill: NuwaSkill):
        self.skill = nuwa_skill
        self.bus = AsyncDialogueBus(max_concurrency=500)
        self._setup_handlers()

    def _setup_handlers(self):
        # 注册总线处理函数
        self.bus.register_handler("chat", self._handle_chat)
        self.bus.register_handler("reset", self._handle_reset)
        self.bus.register_handler("load", self._handle_load)

    async def _handle_chat(self, payload: Dict[str, Any]) -> str:
        persona = payload.get("persona")
        user_input = payload.get("user_input")
        session_id = payload.get("session_id", "default")
        return await asyncio.to_thread(self.skill.generate_response, persona, user_input, session_id)

    async def _handle_reset(self, payload: Dict[str, Any]) -> bool:
        session_id = payload.get("session_id")
        await self.skill.reset_context(session_id)
        return True

    async def _handle_load(self, payload: Dict[str, Any]) -> bool:
        persona = payload.get("persona")
        return await self.skill.load_persona(persona)

    async def start(self):
        await self.bus.start()

    async def stop(self):
        await self.bus.stop()

    async def chat(self, persona: str, user_input: str, session_id: str = "default") -> str:
        """对外暴露的高并发对话接口"""
        payload = {
            "persona": persona,
            "user_input": user_input,
            "session_id": session_id
        }
        return await self.bus.push("chat", payload)

    async def reset(self, session_id: str):
        await self.bus.push("reset", {"session_id": session_id})

    async def load(self, persona: str):
        await self.bus.push("load", {"persona": persona})
