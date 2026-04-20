import os
import sys
import time
from typing import Any, Dict, List, Optional
from skills.base import BaseSkill
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import HumanMessage

class SimpSkill(BaseSkill):
    """
    集成 simp-skill 项目的适配器。
    支持分析聊天记录及关联的照片、朋友圈等媒体数据。
    """
    def __init__(self, simp_skill_path: str = "skills/simp-skill", crushes_path: str = "./crushes"):
        super().__init__(
            name="SimpSkill",
            description="利用 simp-skill 逻辑进行信号解读和情感分析"
        )
        self.path = simp_skill_path
        self.crushes_path = crushes_path
        
        # 统一配置入口：清理模型名称中的空格
        self.model_name = (os.getenv("SIMP_MODEL") or os.getenv("MODEL_NAME", "gpt-4o")).strip()
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("OPENAI_API_BASE")
        self.temperature = float(os.getenv("TEMPERATURE", 0.7))

        self.llm = ChatOpenAI(
            model=self.model_name,
            openai_api_key=self.api_key,
            openai_api_base=self.base_url,
            temperature=self.temperature,
            max_retries=2
        )
        self.prompts = self._load_prompts()
        
        # 将 simp-skill 的 tools 目录加入系统路径，以便调用其中的解析器
        self.tools_path = os.path.join(self.path, "tools")
        if self.tools_path not in sys.path:
            sys.path.insert(0, self.tools_path)

    def _call_llm_robust(self, messages: List[Any]) -> str:
        """健壮的 LLM 调用，如果 LangChain 失败，尝试极简原生调用"""
        try:
            return self.llm.invoke(messages).content
        except Exception as e:
            print(f"[*] LangChain failed: {e}")
            print(f"[*] Attempting ultra-minimal native call to {self.model_name}...")
            
            from openai import OpenAI
            # 确保 API Key 和 Base URL 干净
            client = OpenAI(api_key=self.api_key.strip(), base_url=self.base_url.strip())
            
            native_messages = []
            for m in messages:
                role = "user"
                if hasattr(m, "type") and m.type == "system": role = "system"
                native_messages.append({"role": role, "content": m.content})
            
            import json
            with open("debug_native_payload.json", "w", encoding="utf-8") as f:
                json.dump({"model": self.model_name, "messages": native_messages}, f, ensure_ascii=False)
                
            try:
                # 极简调用：只传 model 和 messages，不传 temperature 等其他任何参数
                resp = client.chat.completions.create(
                    model=self.model_name,
                    messages=native_messages
                )
                return resp.choices[0].message.content
            except Exception as e2:
                print(f"[!] Ultra-minimal call also failed: {e2}")
                raise e2

    def _get_contact_paths(self, contact_id: str) -> Dict[str, str]:
        slug = str(contact_id).lower().replace(" ", "_") if contact_id else "unknown"
        base = os.path.join(self.crushes_path, slug)
        return {
            "base": base,
            "profile": os.path.join(base, "profile.md"),
            "strategy": os.path.join(base, "strategy.md"),
            "meta": os.path.join(base, "meta.json"),
            "chats": os.path.join(base, "memories", "chats"),
            "social": os.path.join(base, "memories", "social"),
            "photos": os.path.join(base, "memories", "photos")
        }

    def _handle_command(self, command: str, context: Dict[str, Any] = None) -> str:
        """处理类似 /simp create <name> 的指令"""
        silent = context.get("silent", False) if context else False
        parts = command.split(" ")
        if len(parts) < 3:
            return "Invalid command format. Use /simp <cmd> <name>"
        
        cmd = parts[1]
        name = " ".join(parts[2:])
        paths = self._get_contact_paths(name)

        if cmd == "create":
            if not os.path.exists(paths["base"]) or not os.path.exists(paths["profile"]):
                if not silent: print(f"[*] Creating directories and profile for {name}...")
                os.makedirs(paths["chats"], exist_ok=True)
                os.makedirs(paths["social"], exist_ok=True)
                os.makedirs(paths["photos"], exist_ok=True)
                
                template = self.prompts.get("intake", "初始化档案...")
                prompt = f"{template}\n\n请为目标人物 {name} 创建初始档案大纲。"
                content = self._call_llm_robust([HumanMessage(content=prompt)])
                
                with open(paths["profile"], "w", encoding="utf-8") as f:
                    f.write(content)
                
                import json
                meta = {"name": name, "stage": "破冰期", "score": 0, "created_at": str(time.time())}
                with open(paths["meta"], "w", encoding="utf-8") as f:
                    json.dump(meta, f, indent=2, ensure_ascii=False)
                    
                return f"Successfully created profile for {name}."
            return f"Profile for {name} already exists."

        elif cmd == "update":
            if not os.path.exists(paths["profile"]):
                return f"Profile for {name} does not exist. Please create it first."
            
            if not silent: print(f"[*] Updating profile for {name}...")
            
            # 读取当前档案
            with open(paths["profile"], "r", encoding="utf-8") as f:
                current_profile = f.read()
                
            # 尝试从知识库中获取最近的数据，或者由 LLM 直接基于最新的 recent_messages 给出更新建议
            template = self.prompts.get("intake", "更新档案...")
            chat_context = context.get("chat_context", "无最新聊天记录") if context else "无最新聊天记录"
            
            prompt = (
                f"{template}\n\n"
                f"这是 {name} 目前的档案：\n{current_profile}\n\n"
                f"=== 最新聊天记录 ===\n{chat_context}\n\n"
                f"请结合最新的聊天记录，对上述档案进行更新。保持原有格式不变，只修改或补充其中的信息。注意：务必包含最新的时间节点。"
            )
            
            updated_content = self._call_llm_robust([HumanMessage(content=prompt)])
            
            with open(paths["profile"], "w", encoding="utf-8") as f:
                f.write(updated_content)
                
            # 更新 meta.json
            if os.path.exists(paths["meta"]):
                import json
                try:
                    with open(paths["meta"], "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    meta["updated_at"] = str(time.time())
                    with open(paths["meta"], "w", encoding="utf-8") as f:
                        json.dump(meta, f, indent=2, ensure_ascii=False)
                except Exception: pass
                
            return f"Successfully updated profile for {name}."
        
        return f"Unknown command: {cmd}"

    def _clean_text(self, text: str) -> str:
        if not text: return ""
        return "".join(c for c in text if ord(c) <= 0xffff)

    def _load_prompts(self) -> Dict[str, str]:
        prompts = {}
        prompt_dir = os.path.join(self.path, "prompts")
        if os.path.exists(prompt_dir):
            for filename in os.listdir(prompt_dir):
                if filename.endswith(".md"):
                    name = filename[:-3]
                    with open(os.path.join(prompt_dir, filename), "r", encoding="utf-8") as f:
                        prompts[name] = f.read()
        return prompts

    def _analyze_social(self, media_root: str, contact_id: str) -> str:
        """调用 social_parser 解析朋友圈/社交媒体文本"""
        social_dir = os.path.join(media_root, "social")
        if not os.path.exists(social_dir): return ""
        try:
            import social_parser
            
            files = social_parser.scan_directory(social_dir)
            texts = files.get("texts", [])
            
            if not texts:
                return ""
                
            report_lines = ["\n### 关联媒体分析 (基于社交媒体文字) ###"]
            text_count = 0
            
            for t_file in texts:
                path = t_file["path"]
                # 尝试解析 JSON
                if path.endswith(".json"):
                    posts = social_parser.parse_json_export(path)
                    for post in posts:
                        text_count += 1
                        signals = social_parser.scan_signals(post["text"])
                        signal_str = f" [发现信号: {', '.join(list(signals.keys()))}]" if signals else ""
                        report_lines.append(f"- [{post.get('time', '未知时间')}] {post['text'][:50]}...{signal_str}")
                else:
                    # 尝试读取普通文本
                    content = social_parser.read_text_file(path, max_chars=200)
                    if content and not content.startswith("[读取失败"):
                        text_count += 1
                        signals = social_parser.scan_signals(content)
                        signal_str = f" [发现信号: {', '.join(list(signals.keys()))}]" if signals else ""
                        report_lines.append(f"- {t_file['name']}: {content[:50]}...{signal_str}")
                        
            if text_count > 0:
                report_lines.append(f"\n共提取了 {text_count} 条社交媒体动态/文本。")
                return "\n".join(report_lines)
        except Exception as e:
            print(f"[!] Error analyzing social media: {e}")
        return ""

    def _analyze_photos(self, media_root: str, contact_id: str) -> str:
        images_dir = os.path.join(media_root, "images")
        if not os.path.exists(images_dir): return ""
        try:
            import photo_analyzer
            
            report_lines = ["\n### 关联媒体分析 (基于照片 EXIF) ###"]
            photo_count = 0
            for file in os.listdir(images_dir):
                if file.lower().endswith(('.jpg', '.jpeg', '.png')):
                    path = os.path.join(images_dir, file)
                    exif = photo_analyzer.get_exif_data(path)
                    dt = photo_analyzer.get_datetime(exif)
                    gps = photo_analyzer.get_gps(exif)
                    if dt or gps:
                        photo_count += 1
                        info = f"- 文件: {file}"
                        if dt: info += f" | 拍摄时间: {dt}"
                        if gps: info += f" | GPS: {gps.get('lat')}, {gps.get('lon')}"
                        report_lines.append(info)
            
            if photo_count > 0:
                report_lines.append(f"\n共分析了 {photo_count} 张带有元数据的照片。")
                return "\n".join(report_lines)
        except Exception as e: 
            print(f"[!] Error analyzing photos: {e}")
        return ""

    def _get_bazi_info(self, contact_id: str) -> str:
        """读取双方的八字信息用于辅助策略生成"""
        import json
        user_bazi = ""
        user_meta_path = os.path.join("user_profile", "meta.json")
        if os.path.exists(user_meta_path):
            try:
                with open(user_meta_path, "r", encoding="utf-8") as f:
                    u_meta = json.load(f)
                    if u_meta.get("calculated_bazi"):
                        user_bazi = u_meta.get("calculated_bazi")
            except Exception:
                pass
                
        target_bazi = ""
        if contact_id and contact_id != "Unknown":
            paths = self._get_contact_paths(contact_id)
            if os.path.exists(paths["meta"]):
                try:
                    with open(paths["meta"], "r", encoding="utf-8") as f:
                        t_meta = json.load(f)
                        if t_meta.get("calculated_bazi"):
                            target_bazi = t_meta.get("calculated_bazi")
                except Exception:
                    pass
                    
        if user_bazi and target_bazi:
            return f"\n### 🔮 命理匹配参考 (Bazi Compatibility) ###\n- 我的八字：{user_bazi}\n- {contact_id}的八字：{target_bazi}\n[重要要求] 请务必结合双方的八字五行生克、性格特质，在你的分析和策略中提供一层中国传统命理学的深度参考建议（如合盘优劣、近期运势对关系的影响）。\n"
        elif user_bazi:
            return f"\n### 🔮 命理参考 (My Bazi) ###\n- 我的八字：{user_bazi}\n[要求] 可以结合我的八字命理特征给出更贴合我性格的建议。\n"
        elif target_bazi:
            return f"\n### 🔮 命理参考 (Target's Bazi) ###\n- {contact_id}的八字：{target_bazi}\n[要求] 可以结合对方的八字命理特征来分析其潜在性格和近期状态倾向。\n"
        return ""

    def _get_user_profile(self) -> str:
        """获取用户本人的档案，用于辅助生成更贴合用户的策略"""
        user_profile_path = os.path.join("user_profile", "profile.md")
        if os.path.exists(user_profile_path):
            try:
                with open(user_profile_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                pass
        return "暂无用户本人档案"

    def run(self, data: Any, context: Dict[str, Any] = None) -> Any:
        silent = context.get("silent", False) if context else False
        
        # 兼容 context 中指定 command 模式，或直接传入 /simp 开头的指令
        if isinstance(data, str) and data.strip().startswith("/simp "):
            return self._handle_command(data.strip(), context=context)
        elif context and context.get("mode") == "command" and isinstance(data, str):
            return self._handle_command(data, context=context)

        contact_id = context.get("contact_id", "Unknown") if context else "Unknown"
        kb_results = context.get("kb_results", []) if context else []
        media_root = context.get("media_root")
        
        chat_text = ""
        if isinstance(data, list):
            recent_msgs = data[-500:] # 支持提取最多 500 条
            for msg in recent_msgs:
                if isinstance(msg, dict):
                    sender = msg.get("senderDisplayName", msg.get("sender", "Unknown"))
                    content = msg.get("content", "")
                    time = msg.get("formattedTime", "")
                    if content:
                        chat_text += f"[{time}] {sender}: {self._clean_text(str(content))}\n"
        elif isinstance(data, str):
            chat_text = f"User Query: {self._clean_text(data)}"

        kb_context = self._clean_text("\n".join(kb_results)) if kb_results else "无历史背景数据"
        media_analysis = self._clean_text(self._analyze_photos(media_root, contact_id)) if media_root else ""
        social_analysis = self._clean_text(self._analyze_social(media_root, contact_id)) if media_root else ""
        
        profile_content = ""
        paths = self._get_contact_paths(contact_id)
        if os.path.exists(paths["profile"]):
            with open(paths["profile"], "r", encoding="utf-8") as f:
                profile_content = f.read()

        template_name = "signal_reader" if isinstance(data, list) else "strategy_builder"
        template_text = self._clean_text(self.prompts.get(template_name, "你是一个情感分析专家。"))
        
        user_profile_text = self._get_user_profile()
        bazi_context = self._get_bazi_info(contact_id)
        
        full_content = (
            f"Prompt Template:\n{template_text}\n\n"
            f"### 【用户本人画像】（请在生成策略和话术时，务必贴合用户的性格、沟通风格和优劣势） ###\n{user_profile_text}\n\n"
            f"### 分析对象: {contact_id} ###\n\n"
            f"### {contact_id} 的长期档案 (已提纯) ###\n{profile_content if profile_content else '暂无档案'}\n\n"
            f"### 历史背景 (知识库检索) ###\n{kb_context}\n\n"
            f"### 当前记录/咨询 ###\n{chat_text}\n"
            f"{media_analysis}\n"
            f"{social_analysis}\n"
            f"{bazi_context}"
        )
        
        messages = [HumanMessage(content=full_content)]
        if not silent:
            print(f"--- SimpSkill: Analyzing '{contact_id}' (Length: {len(full_content)}) ---")
            
        response = self._call_llm_robust(messages)
        
        # 自动将非静默的日常对话与策略沉淀到 strategy.md 中
        if template_name == "strategy_builder" and contact_id != "Unknown" and not silent:
            try:
                strategy_path = paths["strategy"]
                from datetime import datetime
                now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                with open(strategy_path, "a", encoding="utf-8") as f:
                    f.write(f"\n\n## 📅 {now_str} 咨询记录\n")
                    if isinstance(data, str):
                        f.write(f"**🗣️ User:** {data}\n\n")
                    f.write(f"**💡 Simp:**\n{response}\n")
            except Exception as e:
                print(f"[!] Failed to append to strategy.md: {e}")
                
        return response
