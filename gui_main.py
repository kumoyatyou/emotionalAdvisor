import os
import sys
import asyncio
import webbrowser
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
import uvicorn

# Ensure KMP_DUPLICATE_LIB_OK for PyTorch/TorchAudio on Windows
os.environ['KMP_DUPLICATE_LIB_OK']='True'

# Determine paths
if getattr(sys, 'frozen', False):
    APP_DIR = sys._MEIPASS
    DATA_DIR = os.path.join(os.path.expanduser("~"), ".emotionalAdvisor")
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = APP_DIR

# Ensure data directories exist
os.makedirs(os.path.join(DATA_DIR, "db"), exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, "crushes"), exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, "data", "raw"), exist_ok=True)

# Create .env if not exists
env_path = os.path.join(DATA_DIR, ".env")

from dotenv import load_dotenv
load_dotenv(env_path, override=True)

# Import project modules
sys.path.insert(0, APP_DIR)
from core.agent import AIAgent
from skills.simp_skill import SimpSkill
from skills.bazi_skill import BaziSkill

class ChatRequest(BaseModel):
    message: str

# Global agent instance
global_agent = None
sync_folder_task = None
thought_queue = asyncio.Queue()

def agent_thought_callback(message: str):
    # Try to push to queue without blocking, useful for sync code calling into async
    try:
        thought_queue.put_nowait(message)
    except Exception as e:
        print(f"Error putting thought in queue: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    global global_agent, sync_folder_task
    print("\n[*] Initializing AIAgent...")
    
    # 1. Initialize Agent
    global_agent = AIAgent(kb_path=os.path.join(DATA_DIR, "db"), crushes_path=os.path.join(DATA_DIR, "crushes"))
    global_agent.set_thought_callback(agent_thought_callback)

    # 2. Register SimpSkill
    simp_skill = SimpSkill(simp_skill_path=os.path.join(APP_DIR, "skills", "simp-skill"), crushes_path=os.path.join(DATA_DIR, "crushes"))
    global_agent.register_skill(simp_skill)

    # 3. Register NuwaSkill (if exists)
    try:
        from skills.nuwa_skill import NuwaSkill
        nuwa_skill = NuwaSkill(nuwa_path=os.path.join(APP_DIR, "skills", "nuwa-skill"))
        global_agent.register_skill(nuwa_skill)
    except ImportError:
        print("[!] NuwaSkill not found, skipping registration.")

    bazi_skill = BaziSkill()
    global_agent.register_skill(bazi_skill)

    # 4. Background Sync (Silent Mode)
    print("\n[*] Synchronizing new data (Silent Mode) in background...")
    raw_data_dir = os.path.join(DATA_DIR, "data", "raw")
    if os.path.exists(raw_data_dir):
        sync_folder_task = asyncio.create_task(
            asyncio.to_thread(global_agent.process_folder, raw_data_dir, "SimpSkill", True)
        )

    # 5. WeChat Sync (if available)
    try:
        from core.wechat_sync import WechatSync
        app.state.sync_service = WechatSync(global_agent)
        app.state.sync_task = asyncio.create_task(app.state.sync_service.start())
    except ImportError:
        print("[!] core.wechat_sync not found, skipping real-time sync.")
    except Exception as e:
        print(f"[!] Failed to start WeChat sync: {e}")

    yield

    # Cleanup
    if sync_folder_task and not sync_folder_task.done():
        sync_folder_task.cancel()
    if hasattr(app.state, 'sync_service'):
        app.state.sync_service.stop()
        if hasattr(app.state, 'sync_task') and not app.state.sync_task.done():
            app.state.sync_task.cancel()

app = FastAPI(lifespan=lifespan)

# API Endpoint for chat
@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    if not global_agent:
        return {"response": "Agent is not fully initialized yet. Please try again in a moment."}
    
    user_input = request.message.strip()
    if not user_input:
        return {"response": "Empty message."}
        
    try:
        # 预先清理队列中的旧思考信息
        while not thought_queue.empty():
            try:
                thought_queue.get_nowait()
            except:
                break
                
        result = await global_agent.chat(user_input)
        return {"response": str(result)}
    except Exception as e:
        return {"response": f"**[!] Error:** {e}"}

# API Endpoint for SSE streaming thoughts
@app.get("/api/thoughts/stream")
async def thoughts_stream(request: Request):
    async def event_generator():
        try:
            while True:
                # If client disconnected, break
                if await request.is_disconnected():
                    break
                
                # Get thought from queue, waiting up to 1s
                try:
                    message = await asyncio.wait_for(thought_queue.get(), timeout=1.0)
                    yield {
                        "event": "thought",
                        "data": message
                    }
                except asyncio.TimeoutError:
                    # Send a ping to keep connection alive
                    yield {
                        "event": "ping",
                        "data": "keepalive"
                    }
        except asyncio.CancelledError:
            pass

    return EventSourceResponse(event_generator())

# Mount static files (CSS, JS)
app.mount("/static", StaticFiles(directory=os.path.join(APP_DIR, "gui")), name="static")

# Serve the HTML UI
@app.get("/", response_class=HTMLResponse)
async def serve_gui():
    with open(os.path.join(APP_DIR, "gui", "index.html"), "r", encoding="utf-8") as f:
        return f.read()

def open_browser():
    # Wait a tiny bit for the server to start before opening browser
    import time
    time.sleep(1.5)
    webbrowser.open("http://127.0.0.1:8000")

def main():
    print("="*40)
    print("Starting AI 情感军师 Local GUI Server...")
    print("UI will open automatically in your default browser.")
    print("="*40)
    
    # Start browser opener in a separate thread
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Start FastAPI server
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")

if __name__ == "__main__":
    main()