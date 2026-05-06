from skills.base import BaseSkill
from typing import Any, Dict

class DataProcessorSkill(BaseSkill):
    def __init__(self):
        super().__init__(
            name="DataProcessor",
            description="处理原始 JSON 数据并提取关键信息"
        )

    def run(self, data: Any, context: Dict[str, Any] = None) -> Any:
        """
        处理数据。如果 context 中包含知识库检索结果，则结合检索结果进行分析。
        """
        contact_id = context.get("contact_id", "Unknown") if context else "Unknown"
        kb_results = context.get("kb_results", []) if context else []

        if kb_results:
            # 如果有知识库结果，模拟一个基于历史背景的回复/分析
            analysis = f"Analysis for {contact_id} based on {len(kb_results)} historical records: "
            # 这里实际可以调用 LLM
            return analysis + " (Historical context integrated)"
            
        # 否则只是基础处理
        content_snippet = str(data)[:50]
        return f"Processed data for {contact_id}: {content_snippet}..."
