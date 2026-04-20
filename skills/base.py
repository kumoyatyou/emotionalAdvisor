from abc import ABC, abstractmethod
from typing import Any, Dict, List
import os

class BaseSkill(ABC):
    """
    Skill 的基类。所有具体的功能模块（Skill）都应继承此类。
    """
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self._llm = None

    @property
    def llm(self):
        """统一的 LLM 实例获取入口"""
        if self._llm is None:
            from langchain_openai import ChatOpenAI
            # 允许子类覆盖模型名称的环境变量，如果未提供则使用通用的 MODEL_NAME
            env_model_key = f"{self.name.upper()}_MODEL"
            model_name = (os.getenv(env_model_key) or os.getenv("MODEL_NAME", "gpt-4o")).strip()
            api_key = os.getenv("OPENAI_API_KEY", "").strip()
            base_url = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1").strip()
            
            # 从环境变量或类属性中获取 temperature
            temperature = getattr(self, "temperature", float(os.getenv("TEMPERATURE", 0.7)))

            self._llm = ChatOpenAI(
                model=model_name,
                openai_api_key=api_key,
                openai_api_base=base_url,
                temperature=temperature,
                max_retries=2
            )
        return self._llm

    def _call_llm_robust(self, messages: List[Any], temperature: float = None) -> str:
        """健壮的 LLM 调用，如果 LangChain 失败，尝试极简原生调用"""
        # 如果需要临时改变 temperature
        if temperature is not None:
            old_temp = self.llm.temperature
            self.llm.temperature = temperature
            
        try:
            res = self.llm.invoke(messages).content
            if temperature is not None:
                self.llm.temperature = old_temp
            return res
        except Exception as e:
            if temperature is not None:
                self.llm.temperature = old_temp
                
            print(f"[*] LangChain failed: {e}")
            print(f"[*] Attempting ultra-minimal native call to {self.llm.model_name}...")
            
            from openai import OpenAI
            client = OpenAI(api_key=self.llm.openai_api_key.get_secret_value(), base_url=self.llm.openai_api_base)
            
            native_messages = []
            for m in messages:
                role = "user"
                if hasattr(m, "type"):
                    if m.type == "system": role = "system"
                    elif m.type == "ai": role = "assistant"
                elif isinstance(m, dict):
                    role = m.get("role", "user")
                    m = m.get("content", "")
                
                content = m.content if hasattr(m, "content") else str(m)
                native_messages.append({"role": role, "content": content})
                
            try:
                resp = client.chat.completions.create(
                    model=self.llm.model_name,
                    messages=native_messages,
                    temperature=temperature if temperature is not None else self.llm.temperature
                )
                return resp.choices[0].message.content
            except Exception as e2:
                print(f"[!] Ultra-minimal call also failed: {e2}")
                raise e2

    @abstractmethod
    def run(self, data: Any, context: Dict[str, Any] = None) -> Any:
        """
        执行 Skill 的核心逻辑。
        :param data: 传入的原始数据或处理后的数据
        :param context: 上下文信息，如知识库检索结果
        :return: 处理结果
        """
        pass

