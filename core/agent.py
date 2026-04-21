import os
import json
from typing import List, Dict, Any
from core.knowledge_base import KnowledgeBase
from skills.base import BaseSkill

class AIAgent:
    """
    AI Agent 核心框架。
    具备自然语言意图分发能力。
    """
    def __init__(self, kb_path: str = "./db", crushes_path: str = "./crushes"):
        self.kb_path = kb_path
        self._kb = None
        self.crushes_path = crushes_path
        self.registry_path = os.path.join(self.crushes_path, "processed_files.json")
        self.processed_files = self._load_registry()
        self.skills: Dict[str, BaseSkill] = {}
        if not os.path.exists(self.crushes_path):
            os.makedirs(self.crushes_path)
        
        self._dispatcher_llm = None
        
        # 聊天历史记录，用于保持上下文
        self.chat_history = []
        self.max_history = 5

    @property
    def kb(self):
        if self._kb is None:
            self._kb = KnowledgeBase(persist_directory=self.kb_path)
        return self._kb

    @property
    def dispatcher_llm(self):
        if self._dispatcher_llm is None:
            from langchain_openai import ChatOpenAI
            self._dispatcher_llm = ChatOpenAI(
                model=os.getenv("AGENT_MODEL", os.getenv("MODEL_NAME", "gpt-4o")).strip(),
                openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
                openai_api_base=os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1").strip(),
                temperature=0.01, # 有些模型不支持绝对 0，设置为 0.01 保证兼容
                max_retries=2
            )
        return self._dispatcher_llm

    def _load_registry(self) -> Dict[str, float]:
        if os.path.exists(self.registry_path):
            try:
                with open(self.registry_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save_registry(self):
        with open(self.registry_path, 'w', encoding='utf-8') as f:
            json.dump(self.processed_files, f, ensure_ascii=False, indent=2)

    def register_skill(self, skill: BaseSkill):
        """
        注册一个新的 Skill。
        """
        self.skills[skill.name] = skill

    async def chat(self, user_query: str):
        """
        处理用户的自然语言指令，拆解需求并调用相关 Skill。
        """
        print(f"[*] Thinking about your request: '{user_query}'...")
        
        # 1. 意图解析
        dispatch_info = self._get_dispatch_info(user_query)
        skill_name = dispatch_info.get("skill")
        
        # 处理 "None" 字符串或者真正的 None
        contact_id = None
        if "contact" in dispatch_info:
            c = dispatch_info["contact"]
            if c and isinstance(c, str) and c.strip().lower() != "none":
                contact_id = c.strip()
        
        # 将联系人上下文保存到会话历史中
        if not hasattr(self, "context"):
            self.context = {}
        if contact_id:
            self.context["current_contact"] = contact_id
        else:
            # 继承上一次的联系人
            contact_id = self.context.get("current_contact")
            
        refined_query = dispatch_info.get("refined_query", user_query)
        
        # 处理 MultiSkill（如果大模型直接返回了 MultiSkill，或者命中关键字）
        if "结合" in user_query and "八字" in user_query and ("策略" in user_query or "接触" in user_query):
            skill_name = "MultiSkill"

        if not skill_name or (skill_name not in self.skills and skill_name != "WechatSync" and skill_name != "MultiSkill"):
            # 如果没有匹配到 Skill，则直接通过 LLM 回答（或默认使用 SimpSkill）
            if "分析" in user_query or "怎么样" in user_query:
                skill_name = "SimpSkill"
            else:
                return f"抱歉，我还没学会处理这个需求的技能。目前我擅长分析联系人和模拟对话。"

        # 2. 自动处理档案（如果是针对特定联系人）
        if contact_id:
            # 如果指令本身就是明确创建/更新档案，跳过自动确保机制，直接交由 Skill 处理
            if not (isinstance(refined_query, str) and (refined_query.startswith("/simp create ") or refined_query.startswith("/simp update "))):
                self.ensure_contact_profile(contact_id, "SimpSkill" if skill_name == "MultiSkill" else skill_name)

        # 3. 调用 Skill
        print(f"[*] Dispatching to {skill_name} for contact '{contact_id}'...")
        if skill_name == "WechatSync":
            response_text = await self._handle_wechat_sync_query(refined_query, contact_id)
        elif skill_name == "MultiSkill":
            response_text = await self._handle_multi_skill_query(refined_query, contact_id)
        else:
            response_text = self.run_skill_directly(skill_name, refined_query, contact_id=contact_id)
        
        # 记录 AI 的回答，以便下一次意图分发时理解上下文
        self.chat_history.append({"role": "Assistant", "content": response_text[:200] + "..." if len(response_text) > 200 else response_text})
        
        return response_text

    async def _handle_wechat_sync_query(self, query: str, contact_id: str) -> str:
        """处理通过 WechatSync 获取聊天记录的请求"""
        if not contact_id or contact_id == "Unknown":
            return "请提供要同步聊天记录的具体联系人姓名。"
            
        from core.wechat_sync import WechatSync
        # 这里只是一个临时实例用来请求接口，实际服务在 main 里长期运行
        sync = WechatSync(self)
        print(f"[*] Fetching latest messages for {contact_id} via API...")
        result = await sync.fetch_latest_messages(contact_id, limit=100)
        return result

    async def _handle_multi_skill_query(self, query: str, contact_id: str) -> str:
        """处理需要结合多个技能（如 BaziSkill + SimpSkill）的综合查询"""
        print(f"[*] Running multi-skill synthesis for {contact_id}...")
        
        import asyncio
        import time
        from langchain_core.messages import SystemMessage, HumanMessage
        
        # 1. 并发调用 BaziSkill 和 SimpSkill
        bazi_task = asyncio.to_thread(self.run_skill_directly, "BaziSkill", "请给出纯命理学的今日运势与性格特质建议，无需考虑聊天记录。", contact_id)
        simp_task = asyncio.to_thread(self.run_skill_directly, "SimpSkill", "请给出纯基于聊天记录、社交媒体和历史档案的今日策略建议，无需考虑八字命理。", contact_id)
        
        try:
            bazi_res, simp_res = await asyncio.gather(bazi_task, simp_task)
        except Exception as e:
            return f"多技能综合分析失败: {e}"
            
        # 2. 主模型综合分析
        synthesis_prompt = f"""你是一个高级情感战略顾问。你需要综合【中国传统命理学专家(BaziSkill)】和【聊天心理学分析专家(SimpSkill)】的报告，给出一份最终的综合行动建议。

【用户需求】：{query}

【命理学专家(BaziSkill) 的分析】：
{bazi_res}

【聊天行为学专家(SimpSkill) 的分析】：
{simp_res}

【你的任务】：
请将两者的观点完美融合。不要生硬地分成“命理说”和“聊天分析说”，而是将命理的玄学特质作为底层支撑，将聊天记录的现实情况作为表层现象，结合成一篇流畅、深刻且有实操性的建议报告。
输出风格应客观、冷静，带有战略指导意义。
"""
        try:
            print("[*] Synthesizing results via Main LLM...")
            response = self.dispatcher_llm.invoke([
                HumanMessage(content=synthesis_prompt)
            ])
            return response.content
        except Exception as e:
            return f"综合分析生成失败: {e}"

    def _get_dispatch_info(self, query: str) -> Dict[str, Any]:
        """
        通过 LLM 拆解用户需求，结合上下文提取 Skill、联系人和具体问题。
        """
        from langchain_core.messages import SystemMessage, HumanMessage
        history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in self.chat_history])
        
        system_prompt = f"""你是一个 AI Agent 的调度中心。你的任务是结合聊天历史，分析用户的最新输入，并将其拆解为结构化的 JSON。
目前可用的 Skill：
- SimpSkill: 情感分析、信号解读、追求策略、性格档案分析、回复建议。如果用户明确要求“创建档案”、“新建档案”，请将 refined_query 格式化为 `/simp create 姓名`。如果用户明确要求“更新档案”、“更新记录”，请将 refined_query 格式化为 `/simp update 姓名`。**注意：如果是用户在提供【自己/本人】的信息，请勿调用 SimpSkill 去更新别人档案，而是根据实际情况分发给 BaziSkill 或 NuwaSkill。**
- NuwaSkill: 模拟特定人物的思维方式进行对话，或者提取“我本人”的画像。如果用户要求“总结我的聊天记录”、“提炼我的画像”、“总结我的部分”，请将 refined_query 格式化为 `/nuwa extract_user`。
- BaziSkill: 八字排盘、命理分析、算命、测运势。如果用户在提供“自己的生日/名字/出生时间”，这就是在提供算命信息，必须分发给 BaziSkill！注意：如果是“结合八字分析策略”，请分发给 MultiSkill。
- MultiSkill: 需要同时结合【八字命理】和【聊天心理学分析/策略】的综合请求。
- WechatSync: 获取最新的微信聊天记录。如果用户要求“从WeChat Realtime Sync更新最新聊天记录”或“拉取最新聊天记录”，请将 skill 设为 `WechatSync`，并提供联系人姓名。

聊天历史（用于理解上下文代词如“他/她”、“这个”等）：
{history_text if history_text else "无历史"}

输出 JSON 格式（必须输出合法的 JSON，不要附加多余文字）：
{{
    "skill": "SimpSkill" 或 "NuwaSkill" 或 "BaziSkill" 或 "MultiSkill" 或 "WechatSync" 或 null,
    "contact": "识别到的联系人姓名(如果没有明确说明但上下文中存在，请继承上下文中的联系人)。如果是用户本人，必须填 'self' 或 null！",
    "refined_query": "补全代词和上下文后的具体问题或指令"
}}

示例：
输入："帮我建一个李雷的档案"
输出：{{"skill": "SimpSkill", "contact": "李雷", "refined_query": "/simp create 李雷"}}
输入："帮我算一下张天岩的八字"
输出：{{"skill": "BaziSkill", "contact": "张天岩", "refined_query": "帮我算一下张天岩的八字"}}
输入："我的名字是赵允烨，出生时间是2006年3月3日14时"
输出：{{"skill": "BaziSkill", "contact": "self", "refined_query": "我的名字是赵允烨，出生时间是2006年3月3日14时"}}
历史：User: 分析张天岩最近的态度
输入："如果明天约他看电影呢？"
输出：{{"skill": "SimpSkill", "contact": "张天岩", "refined_query": "如果明天约张天岩看电影，有什么建议或策略？"}}
输入："获取方雅婷的最新记录"
输出：{{"skill": "WechatSync", "contact": "方雅婷", "refined_query": "获取方雅婷的最新记录"}}
"""
        try:
            response = self.dispatcher_llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=query)
            ])
            # 清理可能的 Markdown 格式
            content = response.content.strip().replace("```json", "").replace("```", "")
            result = json.loads(content)
            
            # 更新聊天历史
            self.chat_history.append({"role": "User", "content": query})
            if len(self.chat_history) > self.max_history * 2:
                self.chat_history = self.chat_history[-self.max_history * 2:]
                
            return result
        except Exception as e:
            print(f"[!] Dispatcher error: {e}")
            return {"skill": None, "contact": None, "refined_query": query}

    def ensure_contact_profile(self, contact_id: str, skill_name: str):
        """
        确保联系人档案存在。
        """
        if skill_name not in self.skills or not contact_id:
            return
            
        # 如果是用户本人，跳过在 crushes 下创建档案
        if contact_id == "user_profile" or contact_id == "self":
            return

        skill = self.skills[skill_name]
        contact_slug = str(contact_id).lower().replace(" ", "_")
        profile_dir = os.path.join(self.crushes_path, contact_slug)
        profile_file = os.path.join(profile_dir, "profile.md")

        # 检查文件夹和核心档案文件是否存在
        if not os.path.exists(profile_dir) or not os.path.exists(profile_file):
            print(f"[*] Profile for '{contact_id}' incomplete or missing. Initializing...")
            # 确保目录存在
            if not os.path.exists(profile_dir):
                os.makedirs(profile_dir)
            skill.run(f"/simp create {contact_id}", context={"mode": "command"})
        else:
            # 静默更新，不输出大篇幅策略
            skill.run(f"/simp update {contact_id}", context={"mode": "command", "silent": True})

    def process_folder(self, folder_path: str, skill_name: str, silent: bool = False):
        """
        处理指定文件夹中的原始数据。
        优化：仅处理新增或修改的文件。
        :param silent: 是否静默处理（不输出分析报告）
        """
        if skill_name not in self.skills:
            raise ValueError(f"Skill '{skill_name}' not found.")

        skill = self.skills[skill_name]
        processed_count = 0
        
        for root, dirs, files in os.walk(folder_path):
            for filename in files:
                if filename.endswith(".json"):
                    file_path = os.path.join(root, filename)
                    
                    # 增量检查：对比修改时间
                    mtime = os.path.getmtime(file_path)
                    if file_path in self.processed_files and self.processed_files[file_path] >= mtime:
                        continue

                    if not silent:
                        print(f"--- Processing New Data: {filename} ---")
                    
                    try:
                        contact_id = "default"
                        media_root = os.path.join(root, "media")
                        
                        import ijson
                        
                        # 先尝试用 ijson 提取 session 信息，避免加载整个大文件进内存
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                session_parser = ijson.items(f, 'session')
                                session = next(session_parser, None)
                                if session:
                                    contact_id = session.get("remark", session.get("nickname", "unknown"))
                        except Exception:
                            pass
                            
                        self.ensure_contact_profile(contact_id, skill_name)

                        run_context = {
                            "contact_id": contact_id,
                            "media_root": media_root,
                            "file_path": file_path,
                            "silent": silent
                        }

                        recent_messages = []
                        current_batch = []
                        batch_size = 500  # 每次送给知识库 500 条
                        analysis_context_size = 500  # 将用于生成档案的最新聊天记录提升到 500 条
                        has_data = False
                        
                        with open(file_path, 'r', encoding='utf-8') as f:
                            # 兼容微信导出的数组或包裹在 messages 中的格式
                            parser = ijson.items(f, 'messages.item')
                            try:
                                first_item = next(parser)
                                has_data = True
                            except StopIteration:
                                pass
                                
                            if not has_data:
                                f.seek(0)
                                parser = ijson.items(f, 'item')
                                try:
                                    first_item = next(parser)
                                    has_data = True
                                except StopIteration:
                                    pass

                            if has_data:
                                current_batch.append(first_item)
                                recent_messages.append(first_item)
                                
                                for item in parser:
                                    current_batch.append(item)
                                    recent_messages.append(item)
                                    # 保留最近的 analysis_context_size 条用于最终的意图/档案分析
                                    if len(recent_messages) > analysis_context_size:
                                        recent_messages.pop(0)
                                    
                                    if len(current_batch) >= batch_size:
                                        self.kb.add_data(current_batch, contact_id=contact_id)
                                        current_batch = []
                                        if not silent:
                                            print(f"[*] Indexed 500 messages for '{contact_id}'...")
                                            
                                # 最后一批
                                if current_batch:
                                    self.kb.add_data(current_batch, contact_id=contact_id)
                                    if not silent:
                                        print(f"[*] Indexed final {len(current_batch)} messages for '{contact_id}'...")
                                        
                                # 在静默同步模式下，自动调用档案更新指令，强制将最新的上下文写入 Profile
                                if silent:
                                    # 将最近的 50 条消息格式化为文本传给 update 逻辑
                                    chat_context = ""
                                    for msg in recent_messages:
                                        if isinstance(msg, dict):
                                            sender = msg.get("senderDisplayName", msg.get("sender", "Unknown"))
                                            content = msg.get("content", "")
                                            time_str = msg.get("formattedTime", "")
                                            if content:
                                                chat_context += f"[{time_str}] {sender}: {content}\n"
                                    
                                    update_query = f"/simp update {contact_id}"
                                    skill.run(update_query, context={"mode": "command", "silent": True, "chat_context": chat_context})
                                    
                                # 执行 Skill 分析 (只分析最新的 50 条，历史交由知识库)
                                result = skill.run(recent_messages, context=run_context)
                                
                                if not silent:
                                    print(f"Finished processing '{contact_id}'. Result summary: {str(result)[:100]}...")
                                
                                # 记录已处理
                                self.processed_files[file_path] = mtime
                                processed_count += 1
                            else:
                                print(f"[!] No valid messages array found in {filename}")
                    except Exception as e:
                        print(f"Error processing {filename}: {e}")
        
        if processed_count > 0:
            self._save_registry()
            print(f"[*] Synchronized {processed_count} new files.")

    def run_skill_directly(self, skill_name: str, query: str, contact_id: str = None):
        """
        直接调用 Skill，并利用指定联系人的知识库辅助。
        """
        if skill_name not in self.skills:
            raise ValueError(f"Skill '{skill_name}' not found.")
        
        # 从知识库检索相关信息（可选过滤联系人）
        context_docs = self.kb.query(query, contact_id=contact_id)
        context = {
            "kb_results": [doc.page_content for doc in context_docs],
            "contact_id": contact_id
        }
        
        # 执行 Skill
        return self.skills[skill_name].run(query, context=context)
