import os
import json
import time
import requests
from typing import Dict, Any, List
from skills.base import BaseSkill
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

class BaziSkill(BaseSkill):
    """
    八字排盘与命理分析 Skill (适配 bazi-skill)
    支持结合 Crushes 档案系统进行增量信息收集和分析。
    """
    def __init__(self, bazi_path: str = "skills/bazi-skill", crushes_path: str = "crushes"):
        super().__init__(
            name="BaziSkill",
            description="四柱八字命理分析。收集出生信息并参照经典命理典籍进行排盘与分析。"
        )
        self.bazi_path = bazi_path
        self.crushes_path = crushes_path
        
        # 统一配置入口
        from dotenv import load_dotenv
        load_dotenv()
        
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.api_base = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
        self.model_name = os.getenv("BAZI_MODEL", os.getenv("MODEL_NAME", "gpt-4o"))
        
        self.llm = ChatOpenAI(
            model=self.model_name,
            api_key=self.api_key,
            base_url=self.api_base,
            temperature=0.3
        )
        
        # 预加载参考文献
        self.references = self._load_references()

    def _call_llm(self, prompt: str) -> str:
        """调用大语言模型 API (via LangChain)"""
        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            content = response.content
            if isinstance(content, list):
                return "".join([c.get("text", "") for c in content if isinstance(c, dict) and "text" in c])
            return str(content)
        except Exception as e:
            print(f"[!] LLM API Error via LangChain: {e}")
            raise e

    def _load_references(self) -> str:
        """加载所有参考典籍内容"""
        ref_dir = os.path.join(self.bazi_path, "references")
        if not os.path.exists(ref_dir):
            return "参考文献未找到"
            
        combined_text = []
        for filename in ["wuxing-tables.md", "shichen-table.md", "dayun-rules.md", "classical-texts.md"]:
            filepath = os.path.join(ref_dir, filename)
            if os.path.exists(filepath):
                with open(filepath, "r", encoding="utf-8") as f:
                    combined_text.append(f"--- {filename} ---\n" + f.read())
        return "\n\n".join(combined_text)

    def _ensure_bazi_calculated(self, meta_dict: Dict[str, Any]) -> bool:
        """检查并确保八字已被计算，如果有更新返回 True"""
        if "calculated_bazi" in meta_dict:
            return False
            
        info_str = json.dumps(meta_dict, ensure_ascii=False)
        # 粗略判断是否包含出生时间相关的关键词
        if "calendar" not in info_str and "time" not in info_str and "生日" not in info_str and "年" not in info_str:
            return False
            
        prompt = f"""请将以下生辰信息解析为标准的公历或农历时间要素。
输入信息：
{info_str}

如果信息不足以确定具体的年、月、日，请返回空字典 {{}}。
如果时辰不确定，请设置 hour 为 12，minute 为 0。
如果能确定，请严格按照以下 JSON 格式返回：
{{
  "year": 1990,
  "month": 5,
  "day": 12,
  "hour": 8,
  "minute": 30,
  "is_lunar": false
}}
注意：只输出纯 JSON，不要输出其他字符。如果明确是农历，is_lunar 填 true，否则默认 false。
"""
        try:
            res = self._call_llm(prompt).strip()
            if res.startswith("```json"): res = res[7:]
            if res.endswith("```"): res = res[:-3]
            res = res.strip()
            
            parsed = json.loads(res)
            if not parsed or "year" not in parsed:
                return False
                
            y = int(parsed.get("year"))
            m = int(parsed.get("month"))
            d = int(parsed.get("day"))
            h = int(parsed.get("hour", 12))
            minu = int(parsed.get("minute", 0))
            is_lunar = bool(parsed.get("is_lunar", False))
            
            from lunar_python import Lunar, Solar
            if is_lunar:
                lunar = Lunar.fromYmdHms(y, m, d, h, minu, 0)
                bazi = lunar.getEightChar()
            else:
                solar = Solar.fromYmdHms(y, m, d, h, minu, 0)
                bazi = solar.getLunar().getEightChar()
                
            bazi_str = f"{bazi.getYear()} {bazi.getMonth()} {bazi.getDay()} {bazi.getTime()}"
            meta_dict["calculated_bazi"] = bazi_str
            return True
        except Exception as e:
            print(f"[!] Bazi Calculation Helper Error: {e}")
            return False

    def _get_contact_meta(self, contact_id: str) -> Dict[str, Any]:
        """获取目标人物的元数据（包含八字所需信息）"""
        contact_slug = contact_id.lower().replace(" ", "_")
        meta_path = os.path.join(self.crushes_path, contact_slug, "meta.json")
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_contact_meta(self, contact_id: str, meta: Dict[str, Any]):
        """保存目标人物的元数据"""
        contact_slug = contact_id.lower().replace(" ", "_")
        meta_path = os.path.join(self.crushes_path, contact_slug, "meta.json")
        if os.path.exists(meta_path):
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2, ensure_ascii=False)

    def _get_user_meta(self) -> Dict[str, Any]:
        """获取用户本人的元数据"""
        meta_path = os.path.join("user_profile", "meta.json")
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_user_meta(self, meta: Dict[str, Any]):
        """保存用户本人的元数据"""
        os.makedirs("user_profile", exist_ok=True)
        meta_path = os.path.join("user_profile", "meta.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

    def run(self, data: Any, context: Dict[str, Any] = None) -> Any:
        contact_id = context.get("contact_id") if context else None
        user_query = data if isinstance(data, str) else str(data)
        
        from datetime import datetime
        current_date = datetime.now().strftime("%Y年%m月%d日 %H:%M")
        
        system_prompt = f"""你是一个专业的中国传统四柱八字命理分析师。
你需要根据用户提供的生辰八字信息进行排盘和命理分析。

【当前系统时间】：{current_date} (请在计算大运、流年、今年运势等与时间相关的内容时，严格以此时刻为基准)

【你的参考知识库】
{self.references[:4000]}... (由于长度限制截断，请基于你内置的八字命理知识进行分析)

【工作流程】
1. 信息检查：如果用户想要算八字，你需要检查是否已经拥有了足够的生辰信息（姓名、性别、出生地、阳历/农历生日、出生时辰）。
2. 增量收集：如果信息缺失，你需要以引导式的语气，询问用户补充缺失的信息。**一次只问一个缺失的问题**。
3. 排盘分析：如果信息已经收集齐全，或者用户让你直接算，请根据你掌握的《滴天髓》、《渊海子平》等经典理论，给出详细的四柱排盘、日主分析、大运流年分析。
"""

        # 获取并加载本人信息
        user_meta = self._get_user_meta()

        # 尝试通过 LLM 提取用户当前输入中包含的八字信息，并自动更新到对应的 meta 中
        extract_prompt = f"""用户说："{user_query}"
请判断用户是在提供谁的信息（是提供用户【本人】的信息，还是提供【目标人物 {contact_id if contact_id else 'ta'}】的信息）。
然后提取其中包含的基本信息（如：姓名(name)、阳历生日(solar_calendar)、农历生日(lunar_calendar)、出生时辰(birth_time)、性别(gender)、出生地(birth_place)等）。
输出格式必须为 JSON：
{{
  "target": "self" 或 "contact",
  "info": {{ 提取到的字段字典, 如果没有则为空字典 }}
}}
"""
        try:
            extract_res = self._call_llm(extract_prompt).strip()
            if extract_res.startswith("```json"): extract_res = extract_res[7:]
            if extract_res.endswith("```"): extract_res = extract_res[:-3]
            extract_res = extract_res.strip()
            
            parsed_res = json.loads(extract_res)
            target = parsed_res.get("target")
            new_info = parsed_res.get("info", {})
            
            if new_info:
                if target == "self":
                    user_meta.update(new_info)
                    # 如果重新提供了时间，需要重新计算八字
                    if "calculated_bazi" in user_meta: del user_meta["calculated_bazi"]
                    self._save_user_meta(user_meta)
                elif target == "contact" and contact_id and contact_id != "default":
                    meta = self._get_contact_meta(contact_id)
                    meta.update(new_info)
                    if "bazi_info" in meta: del meta["bazi_info"]
                    if "calculated_bazi" in meta: del meta["calculated_bazi"]
                    self._save_contact_meta(contact_id, meta)
        except Exception as e:
            print(f"[!] Info Extraction Error: {e}")

        # 获取并计算本人信息
        user_meta = self._get_user_meta()
        if self._ensure_bazi_calculated(user_meta):
            self._save_user_meta(user_meta)

        user_bazi_info = {
            "name": user_meta.get("name", "用户本人"),
            "gender": user_meta.get("gender", ""),
            "solar_calendar": user_meta.get("solar_calendar", ""),
            "lunar_calendar": user_meta.get("lunar_calendar", ""),
            "birth_time": user_meta.get("birth_time", ""),
            "birth_place": user_meta.get("birth_place", ""),
            "calculated_bazi": user_meta.get("calculated_bazi", "")
        }
        user_bazi_info = {k: v for k, v in user_bazi_info.items() if v}
        user_info_str = f"\n\n目前档案中已保存的【用户本人】基本信息如下：\n{json.dumps(user_bazi_info, ensure_ascii=False, indent=2)}" if user_bazi_info else ""

        # 如果有目标人物，获取并计算其八字档案
        meta_info = user_info_str
        if contact_id and contact_id != "default":
            meta = self._get_contact_meta(contact_id)
            if self._ensure_bazi_calculated(meta):
                self._save_contact_meta(contact_id, meta)

            bazi_info = {
                "gender": meta.get("gender", ""),
                "solar_calendar": meta.get("solar_calendar", ""),
                "lunar_calendar": meta.get("lunar_calendar", ""),
                "birth_time": meta.get("birth_time", ""),
                "birth_place": meta.get("birth_place", ""),
                "calculated_bazi": meta.get("calculated_bazi", "")
            }
            bazi_info = {k: v for k, v in bazi_info.items() if v}
            
            if bazi_info:
                meta_info += f"\n\n目前档案中已保存的【{contact_id}】的基本信息如下：\n{json.dumps(bazi_info, ensure_ascii=False, indent=2)}\n如果信息已全，请直接进行命理分析（如果是合婚，请综合你和ta的信息）；如果缺失，请询问用户补充。"
            else:
                meta_info += f"\n\n目前档案中尚未保存【{contact_id}】的基本信息，请引导用户提供性别、出生年月日时和出生地等。"

        final_prompt = system_prompt + meta_info + "\n\n用户问题：" + user_query
        
        try:
            return self._call_llm(final_prompt)
        except Exception as e:
            return f"八字排盘分析出错: {e}"