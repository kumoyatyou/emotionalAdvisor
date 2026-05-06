import os
import asyncio
from typing import Any, Dict, List, Optional
from skills.base import BaseSkill

class NuwaSkill(BaseSkill):
    """
    NuwaSkill 适配器：加载 nuwa-skill 的思维模型并进行对话生成。
    """
    def __init__(self, nuwa_path: str = "skills/nuwa-skill"):
        super().__init__(
            name="NuwaSkill",
            description="基于思维模型的角色蒸馏对话技能"
        )
        self.nuwa_path = nuwa_path
        self.temperature = float(os.getenv("TEMPERATURE", 0.3))
        
        self.personas: Dict[str, str] = {}
        self.contexts: Dict[str, List[Dict[str, str]]] = {}
        self._load_all_personas()

    def _load_all_personas(self):
        """扫描 examples 目录并加载所有的思维模型（SKILL.md）"""
        examples_dir = os.path.join(self.nuwa_path, "examples")
        if not os.path.exists(examples_dir):
            return

        for entry in os.scandir(examples_dir):
            if entry.is_dir():
                skill_file = os.path.join(entry.path, "SKILL.md")
                if os.path.exists(skill_file):
                    persona_name = entry.name.replace("-perspective", "")
                    with open(skill_file, "r", encoding="utf-8") as f:
                        self.personas[persona_name] = f.read()
        
        # 优化输出格式，让控制台显示更美观
        persona_names = list(self.personas.keys())
        if persona_names:
            print(f"[*] Loaded {len(persona_names)} Nuwa personas: {', '.join(persona_names)}")
        else:
            print("[!] No Nuwa personas loaded.")

    async def load_persona(self, persona_name: str) -> bool:
        """显式加载角色"""
        return persona_name in self.personas

    async def reset_context(self, session_id: str):
        """重置指定会话的上下文"""
        if session_id in self.contexts:
            del self.contexts[session_id]

    def generate_response(self, persona_name: str, user_input: str, session_id: str) -> str:
        """生成基于特定思维模型的回复"""
        if persona_name not in self.personas:
            raise ValueError(f"Persona '{persona_name}' not found.")

        # 维护对话历史
        if session_id not in self.contexts:
            self.contexts[session_id] = [
                {"role": "system", "content": self.personas[persona_name]}
            ]
        
        self.contexts[session_id].append({"role": "user", "content": user_input})
        
        # 调用 LLM
        response = self.llm.invoke(self.contexts[session_id])
        reply = response.content
        
        self.contexts[session_id].append({"role": "assistant", "content": reply})
        return reply

    def _extract_user_profile(self) -> str:
        """读取全局所有处理过的知识库或聊天记录（此处从 db 或 crushes 目录扫描），
        提炼用户本人的画像并保存到 user_profile/profile.md。
        """
        import glob
        import json
        
        all_texts = []
        crushes_path = "crushes"
        
        # 扫描所有 crushes 下的 meta.json 或 profile.md 以获取全局上下文
        # 为了高效，我们扫描最近处理过的一些文件或从 vector db 中提取。
        # 这里简化为扫描所有 chats 目录下的记录（如果有存的话），或者直接让 LLM 总结知识库
        
        # 方案：遍历 crushes 目录下的所有 profile.md，提取出其中 user_style 相关的字段
        profiles = glob.glob(f"{crushes_path}/*/profile.md")
        for p in profiles:
            try:
                with open(p, "r", encoding="utf-8") as f:
                    all_texts.append(f"【来自 {p} 的片段】\n" + f.read()[:2000]) # 取前2000字防止超长
            except: pass
            
        if not all_texts:
            return "未找到任何聊天档案，无法提取本人画像。"
            
        combined_text = "\n\n".join(all_texts)
        
        prompt = f"""你是一个心理学与人物画像专家。
以下是我（用户本人）在与多个不同联系人的交往中，AI 总结出来的各个人物档案片段。
在这些档案中，通常包含了对我本人（User/我）的分析，例如 "user_style", "user_message_style" 或互动模式中的描述。

请你综合这些信息，为“我本人”提炼一份专属的全局性格画像。
请使用 Markdown 格式输出，必须包含以下三个标题：
## 🎭 性格画像
## 💬 沟通风格
## 💡 个人优势与吸引力点

以下是供你参考的全局数据：
{combined_text}
"""
        try:
            # 使用同步的 llm invoke，因为这个过程不一定在 event loop 里
            from langchain_core.messages import HumanMessage
            result = self._call_llm_robust([HumanMessage(content=prompt)])
            
            # 保存到 user_profile/profile.md
            user_profile_path = os.path.join("user_profile", "profile.md")
            os.makedirs("user_profile", exist_ok=True)
            
            # 保留原有的基础信息部分，只替换后面的动态分析
            base_info = "## 📝 基础信息\n- **性别**: [待补充]\n- **生日**: [待补充]\n- **常居地**: [待补充]\n- **职业/状态**: [待补充]\n\n"
            try:
                if os.path.exists(user_profile_path):
                    with open(user_profile_path, "r", encoding="utf-8") as f:
                        old_content = f.read()
                        if "## 📝 基础信息" in old_content:
                            base_info = old_content.split("## 🎭 性格画像")[0]
            except: pass

            with open(user_profile_path, "w", encoding="utf-8") as f:
                f.write(f"# 用户本人档案画像\n\n这里记录了通过各个聊天记录分析提炼出的你自己的性格画像。\n\n{base_info}{result}")
                
            return "已成功提炼并更新本人全局画像，已保存至 user_profile/profile.md"
        except Exception as e:
            return f"提取本人画像失败: {e}"

    def run(self, data: Any, context: Dict[str, Any] = None) -> Any:
        """同步运行方法（兼容基类）"""
        if isinstance(data, str) and data.strip().startswith("/nuwa extract_user"):
            return self._extract_user_profile()
            
        persona = context.get("persona", "naval") if context else "naval"
        session_id = context.get("session_id", "default")
        return self.generate_response(persona, str(data), session_id)
