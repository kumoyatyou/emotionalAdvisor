import os
import json
import asyncio
import httpx
from datetime import datetime
from typing import Any
from core.agent import AIAgent

class WechatSync:
    """
    通过监听本地 SSE 接口 (如 http://127.0.0.1:5031/api/v1/push/messages)
    实现聊天记录的实时同步。失败时会自动重试或优雅降级（允许手动上传）。
    """
    def __init__(self, agent: AIAgent, sse_url: str = None, token: str = None):
        self.agent = agent
        # 从 .env 中读取 URL，或者使用默认值
        self.sse_url = sse_url or os.getenv("WECHAT_SYNC_URL", "http://127.0.0.1:5031/api/v1/push/messages")
        # 从 .env 中读取 Token
        self.token = token or os.getenv("WECHAT_SYNC_TOKEN", "")
        self.running = False
        self.processed_keys = set()

    async def start(self):
        self.running = True
        print(f"\n[*] Starting WeChat Realtime Sync listener at {self.sse_url}...")
        
        retry_count = 0
        max_retries = 5
        
        while self.running:
            try:
                # 使用 timeout=None 保持 SSE 长连接不断开
                # 设置 trust_env=False 极其重要：防止请求 127.0.0.1 时被系统 VPN/代理劫持从而返回 502 Bad Gateway
                async with httpx.AsyncClient(timeout=httpx.Timeout(None), trust_env=False) as client:
                    headers = {"Accept": "text/event-stream"}
                    req_url = self.sse_url
                    
                    if self.token:
                        headers["Authorization"] = f"Bearer {self.token}"
                        # 双重保障：很多本地 SSE 接口在长连接时容易丢失自定义 Header，因此在 URL 里也拼上 token
                        sep = "&" if "?" in req_url else "?"
                        req_url = f"{req_url}{sep}access_token={self.token}"
                    
                    # 某些本地服务器返回的 SSE Header 不规范，可以通过 headers 强制声明或者捕获该错误后使用其他库
                    async with client.stream("GET", req_url, headers=headers) as response:
                        if response.status_code != 200:
                            retry_count += 1
                            if retry_count > max_retries:
                                print(f"\n[!] WeChat Sync error: Server returned status {response.status_code}.")
                                print("[!] 已达到最大连续失败次数，自动降级为【手动模式】（停止自动同步）。\n[!] 请检查 WeFlow 服务及 .env 中的 Token 配置，或直接将聊天记录放入 data/raw/ 目录下。")
                                self.running = False
                                break
                            print(f"[!] WeChat Sync error: Server returned status {response.status_code}. Retrying in 5s... ({retry_count}/{max_retries})")
                            await asyncio.sleep(5)
                            continue
                            
                        # 连接成功，重置重试计数器
                        retry_count = 0
                        print("[*] WeChat Sync connected successfully! Listening for new messages...")
                        
                        buffer = ""
                        async for line in response.aiter_lines():
                            if not self.running:
                                break
                            
                            if line.startswith("data: "):
                                try:
                                    json_str = line[6:].strip()
                                    if json_str:
                                        data = json.loads(json_str)
                                        # 如果包裹在事件里，提取出来
                                        if "event" in data and data["event"] == "message.new":
                                            await self._process_message(data)
                                        else:
                                            # 如果没有外层包装，直接处理
                                            await self._process_message(data)
                                except json.JSONDecodeError:
                                    continue
            except httpx.ConnectError:
                retry_count += 1
                if retry_count > max_retries:
                    print("\n[!] WeChat Sync: Connection refused. Is the API server running?")
                    print("[!] 已达到最大连续失败次数，自动降级为【手动模式】（停止自动同步）。\n[!] 请检查 WeFlow 服务及端口，或直接将聊天记录放入 data/raw/ 目录下。")
                    self.running = False
                    break
                print(f"[!] WeChat Sync: Connection refused. Is the API server running? Retrying in 10s... ({retry_count}/{max_retries})")
                await asyncio.sleep(10)
            except Exception as e:
                if self.running:
                    retry_count += 1
                    if retry_count > max_retries:
                        print(f"\n[!] WeChat Sync error: {e}.")
                        print("[!] 已达到最大连续失败次数，自动降级为【手动模式】（停止自动同步）。")
                        self.running = False
                        break
                    print(f"[!] WeChat Sync error: {e}. Retrying in 5s... ({retry_count}/{max_retries})")
                    await asyncio.sleep(5)

    def stop(self):
        self.running = False
        print("[*] WeChat Sync stopped.")

    async def _process_message(self, data: dict):
        msg_key = data.get("messageKey")
        if msg_key and msg_key in self.processed_keys:
            return
        if msg_key:
            self.processed_keys.add(msg_key)

        # Skip group messages (根据截图，群聊会带有 groupName)
        if data.get("groupName"):
            return
            
        contact_id = data.get("sourceName")
        content = data.get("content")
        if not contact_id or not content:
            return
            
        # 格式化消息为 WeFlow 导出的格式
        now = datetime.now()
        formatted_time = now.strftime("%Y-%m-%d %H:%M:%S")
        create_time = int(now.timestamp())
        
        # WeFlow API 中可以从 messageKey 推断 isSend
        # messageKey 格式类似： server:123456:1760000123:1760000123000:321:wxid_member:1
        # 如果是发出的消息，通常 sourceName 可能是我们自己，但这在 push 中可能没明确体现。
        # 我们可以暂且认为 isSend = 0 除非有更明确标识
        is_send = 0 
        
        msg_obj = {
            "localId": msg_key or str(create_time),
            "createTime": create_time,
            "formattedTime": formatted_time,
            "type": "文本消息",
            "content": content,
            "senderDisplayName": contact_id,
            "isSend": is_send
        }

        # 保存到 data/raw/realtime 目录，作为增量备份
        data_dir = os.path.dirname(self.agent.crushes_path)
        realtime_dir = os.path.join(data_dir, "data", "raw", "realtime")
        os.makedirs(realtime_dir, exist_ok=True)
        file_path = os.path.join(realtime_dir, f"私聊_{contact_id}.json")
        
        # 将 IO 操作和同步知识库操作放入线程中运行，防止阻塞异步事件循环
        await asyncio.to_thread(self._save_and_inject, msg_obj, contact_id, file_path, formatted_time, content)

    def _save_and_inject(self, msg_obj: dict, contact_id: str, file_path: str, formatted_time: str, content: str):
        # 1. 写入本地 JSON (符合 WeFlow 导出格式)
        data_to_write = None
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data_to_write = json.load(f)
            except Exception:
                pass
                
        if not data_to_write:
            data_to_write = {
                "session": {
                    "remark": contact_id,
                    "type": "私聊"
                },
                "messages": []
            }
            
        if "messages" not in data_to_write:
            data_to_write["messages"] = []
            
        data_to_write["messages"].append(msg_obj)
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data_to_write, f, ensure_ascii=False, indent=2)

        # 2. 注入 Knowledge Base (支持后续基于历史聊天做分析)
        try:
            self.agent.kb.add_data([msg_obj], contact_id=contact_id)
        except Exception as e:
            print(f"[!] WeChat Sync: Error adding to KB - {e}")
            
        # 3. 自动静默更新该联系人的 Profile 档案
        if "SimpSkill" in self.agent.skills:
            try:
                skill = self.agent.skills["SimpSkill"]
                # 确保目标档案已经存在，如果不存在会自动创建
                self.agent.ensure_contact_profile(contact_id, "SimpSkill")
                
                chat_context = f"[{formatted_time}] {contact_id}: {content}\n"
                skill.run(
                    f"/simp update {contact_id}", 
                    context={"mode": "command", "silent": True, "chat_context": chat_context}
                )
                print(f"\n[WeChat Sync] Automatically updated profile for '{contact_id}' with new message: {content[:20]}...")
            except Exception as e:
                print(f"[!] WeChat Sync: Error updating profile - {e}")

    async def fetch_latest_messages(self, contact_id: str, limit: int = 100) -> str:
        """
        主动调用 WeFlow API 获取最新的聊天记录并返回格式化文本
        """
        api_url = self.sse_url.replace("/push/messages", "/messages")
        
        try:
            # 1. 首先需要获取 target 对应的 wxid (因为 WeFlow /messages 接口的 talker 需要 wxid 或 roomid)
            wxid = contact_id
            # 可以尝试调用 /contacts 接口模糊匹配出 wxid
            contacts_url = self.sse_url.replace("/push/messages", "/contacts")
            # 增加 timeout 到 60 秒，防止拉取大量历史消息时超时
            async with httpx.AsyncClient(trust_env=False, timeout=60.0) as client:
                headers = {"Content-Type": "application/json"}
                if self.token:
                    headers["Authorization"] = f"Bearer {self.token}"
                
                # 获取联系人列表查找 wxid
                contacts_res = await client.post(contacts_url, json={"keyword": contact_id, "limit": 5}, headers=headers)
                if contacts_res.status_code == 200:
                    c_data = contacts_res.json()
                    if c_data.get("success") and c_data.get("contacts"):
                        # 假设第一个就是最匹配的
                        wxid = c_data["contacts"][0].get("username", contact_id)
                        print(f"[*] Resolved '{contact_id}' to wxid: {wxid}")

                # 2. 读取本地记录获取最后更新时间，用于增量拉取
                data_dir = os.path.dirname(self.agent.crushes_path)
                realtime_dir = os.path.join(data_dir, "data", "raw", "realtime")
                os.makedirs(realtime_dir, exist_ok=True)
                file_path = os.path.join(realtime_dir, f"私聊_{contact_id}.json")
                
                last_timestamp = 0
                data_to_write = {
                    "session": {
                        "remark": contact_id,
                        "type": "私聊"
                    },
                    "messages": []
                }
                if os.path.exists(file_path):
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            data_to_write = json.load(f)
                            if data_to_write.get("messages"):
                                last_timestamp = max(m.get("createTime", 0) for m in data_to_write["messages"])
                    except Exception:
                        pass

                # 3. 拉取消息记录 (请求 1000 条以确保拿到所有增量)
                payload = {
                    "talker": wxid,
                    "limit": 1000
                }
                if last_timestamp > 0:
                    payload["start"] = last_timestamp
                
                response = await client.post(api_url, json=payload, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success") and "messages" in data:
                        api_messages = data["messages"]
                        
                        # 过滤出增量新消息
                        new_messages = [m for m in api_messages if m.get("createTime", 0) > last_timestamp]
                        if not new_messages:
                            return f"与 '{contact_id}' 的聊天记录已是最新，没有发现新消息。"
                            
                        # 按时间升序排列
                        new_messages.sort(key=lambda x: x.get("createTime", 0))
                        
                        existing_ids = {m.get("localId") for m in data_to_write["messages"]}
                        added_count = 0
                        latest_time_str = "未知时间"
                        kb_messages = []
                        
                        for msg in new_messages:
                            ts = msg.get("createTime", 0)
                            time_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S") if ts else "未知时间"
                            latest_time_str = time_str
                            
                            sender = msg.get("senderUsername", "Unknown")
                            if msg.get("isSend") == 1:
                                sender = "我"
                            else:
                                sender = contact_id
                                
                            msg_obj = {
                                "localId": msg.get("localId", str(ts)),
                                "createTime": ts,
                                "formattedTime": time_str,
                                "type": "文本消息",
                                "content": msg.get("parsedContent") or msg.get("content", ""),
                                "senderDisplayName": sender,
                                "isSend": msg.get("isSend", 0)
                            }
                            
                            if msg_obj["localId"] not in existing_ids:
                                data_to_write["messages"].append(msg_obj)
                                kb_messages.append(msg_obj)
                                existing_ids.add(msg_obj["localId"])
                                added_count += 1
                                
                        if added_count == 0:
                            return f"与 '{contact_id}' 的聊天记录已是最新，没有新增内容。"
                            
                        # 批量保存到文件和知识库
                        try:
                            with open(file_path, "w", encoding="utf-8") as f:
                                json.dump(data_to_write, f, ensure_ascii=False, indent=2)
                            self.agent.kb.add_data(kb_messages, contact_id=contact_id)
                        except Exception as e:
                            print(f"[!] WeChat Sync: Error saving historical message - {e}")
                            
                        # 批量更新一次档案
                        if "SimpSkill" in self.agent.skills:
                            try:
                                skill = self.agent.skills["SimpSkill"]
                                self.agent.ensure_contact_profile(contact_id, "SimpSkill")
                                # 取本地最新的100条作为更新上下文
                                recent_for_update = data_to_write["messages"][-100:]
                                update_context = ""
                                for m in recent_for_update:
                                    s = "我" if m.get("isSend") == 1 else contact_id
                                    c = m.get("content", "")
                                    t = m.get("formattedTime", "")
                                    update_context += f"[{t}] {s}: {c}\n"
                                    
                                skill.run(
                                    f"/simp update {contact_id}", 
                                    context={"mode": "command", "silent": True, "chat_context": update_context}
                                )
                                print(f"\n[WeChat Sync] Automatically updated profile for '{contact_id}' with batch history.")
                            except Exception as e:
                                print(f"[!] WeChat Sync: Error updating profile after fetch - {e}")
                            
                        return f"✅ 与 {contact_id} 的聊天记录同步成功！共新增了 {added_count} 条记录，目前最新已同步至 {latest_time_str}。"
                    else:
                        return f"获取失败，API 返回: {data}"
                else:
                    return f"获取失败，HTTP 状态码: {response.status_code}"
        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"请求 WeFlow API 出错: {e} (类型: {type(e).__name__})"
