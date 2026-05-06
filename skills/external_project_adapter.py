import subprocess
import sys
import os
from typing import Any, Dict
from skills.base import BaseSkill

class ExternalProjectSkill(BaseSkill):
    """
    封装外部 GitHub 项目的 Skill 适配器。
    """
    def __init__(self, project_path: str):
        super().__init__(
            name="ExternalProject",
            description=f"调用位于 {project_path} 的外部项目逻辑"
        )
        self.project_path = project_path
        # 将项目路径添加到 sys.path 方便导入
        if self.project_path not in sys.path:
            sys.path.append(self.project_path)

    def run(self, data: Any, context: Dict[str, Any] = None) -> Any:
        """
        根据外部项目的接入方式，选择以下一种或多种实现：
        """
        
        # 方式 1: 如果外部项目可以作为模块导入
        # try:
        #     from external_module import process_data
        #     return process_data(data, context)
        # except ImportError:
        #     pass

        # 方式 2: 如果外部项目需要通过命令行调用
        # return self._run_via_subprocess(data)

        # 方式 3: 如果外部项目是 API 服务
        # return self._run_via_api(data)

        return f"ExternalProjectSkill simulation: processed {len(data) if isinstance(data, list) else 1} items."

    def _run_via_subprocess(self, data: Any) -> str:
        # 将数据写入临时文件供外部程序读取
        temp_file = "temp_input.json"
        import json
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        
        # 调用外部项目的入口脚本
        result = subprocess.run(
            [sys.executable, os.path.join(self.project_path, "main.py"), "--input", temp_file],
            capture_output=True,
            text=True
        )
        return result.stdout

    def _run_via_api(self, data: Any) -> Dict:
        import requests
        url = "http://localhost:8000/process"
        response = requests.post(url, json={"data": data})
        return response.json()
