import os
os.environ['KMP_DUPLICATE_LIB_OK']='True'
from dotenv import load_dotenv
from core.agent import AIAgent
from skills.simp_skill import SimpSkill
from skills.bazi_skill import BaziSkill
from rich.console import Console
from rich.markdown import Markdown

# 加载环境变量
load_dotenv()

import asyncio

console = Console()

async def interactive_chat(agent: AIAgent):
    print("\n" + "="*30)
    print("AI 情感军师 Agent 已启动")
    print("您可以输入指令，如：")
    print("- '帮我建一个xxx的档案' (创建档案)")
    print("- '用 Naval 的视角建议我如何处理这段关系'")
    print("- '分析一下xxx最近的态度'")
    print("- '结合我和xxx的八字算一下今天的接触策略'")
    print("- '给我一个今天的每日建议吧'")
    print("- '退出' 结束对话")
    print("="*30 + "\n")

    while True:
        # 使用 aio 线程避免阻塞 event loop
        user_input = await asyncio.to_thread(input, "User ❯ ")
        user_input = user_input.strip()
        if user_input.lower() in ["退出", "exit", "quit"]:
            break
        
        if not user_input:
            continue

        try:
            result = await agent.chat(user_input)
            print("\nAssistant ❯")
            # 使用 Rich 的 Markdown 渲染输出
            console.print(Markdown(str(result)))
            print()
        except Exception as e:
            print(f"\n[!] Error: {e}\n")

async def async_main():
    # 1. 初始化 Agent (支持存储档案到 crushes 目录)
    agent = AIAgent(kb_path="./db", crushes_path="./crushes")

    # 2. 注册 SimpSkill
    simp_skill = SimpSkill(simp_skill_path="skills/simp-skill", crushes_path="./crushes")
    agent.register_skill(simp_skill)

    # 3. 注册 NuwaSkill (如果存在)
    try:
        from skills.nuwa_skill import NuwaSkill
        nuwa_skill = NuwaSkill(nuwa_path="skills/nuwa-skill")
        agent.register_skill(nuwa_skill)
    except ImportError:
        print("[!] NuwaSkill not found, skipping registration.")

    bazi_skill = BaziSkill()
    agent.register_skill(bazi_skill)

    # 4. 自动同步原始数据 (增量且静默处理，不输出分析结果)
    print("\n[*] Synchronizing new data (Silent Mode) in background...")
    raw_data_dir = "./data/raw"
    sync_folder_task = None
    if os.path.exists(raw_data_dir):
        # 放在后台异步执行，不阻塞主流程
        sync_folder_task = asyncio.create_task(
            asyncio.to_thread(agent.process_folder, raw_data_dir, "SimpSkill", True)
        )

    # 5. 启动微信实时同步服务
    try:
        from core.wechat_sync import WechatSync
        sync_service = WechatSync(agent)
        sync_task = asyncio.create_task(sync_service.start())
    except ImportError:
        print("[!] core.wechat_sync not found, skipping real-time sync.")
    except Exception as e:
        print(f"[!] Failed to start WeChat sync: {e}")

    # 6. 进入交互模式
    await interactive_chat(agent)
    
    if sync_folder_task and not sync_folder_task.done():
        sync_folder_task.cancel()

    if 'sync_service' in locals():
        sync_service.stop()
        if not sync_task.done():
            sync_task.cancel()

def main():
    asyncio.run(async_main())

if __name__ == "__main__":
    main()
