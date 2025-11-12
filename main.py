import time, threading, secrets
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

app = FastAPI(title="Ephemeral Message Relay")

# Serve static assets & templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

TTL_SECONDS = 60
store = {}  # {id: {"data": str, "expires": float, "views_left": int}}

class MessageIn(BaseModel):
    text: str
    ttl: int | None = None
    max_views: int | None = 1


@app.on_event("startup")
def start_cleanup_thread():
    """Delete expired messages every few seconds"""
    def cleanup_loop():
        while True:
            now = time.time()
            expired = [k for k, v in store.items() if v["expires"] < now or v["views_left"] <= 0]
            for k in expired:
                del store[k]
            time.sleep(5)
    threading.Thread(target=cleanup_loop, daemon=True).start()


@app.post("/send")
def send(msg: MessageIn):
    """Store a message temporarily"""
    msg_id = secrets.token_hex(4)
    ttl = msg.ttl or TTL_SECONDS
    store[msg_id] = {
        "data": msg.text,
        "expires": time.time() + ttl,
        "views_left": msg.max_views or 1
    }
    return {
        "id": msg_id,
        "expires_in": ttl,
        "link": f"/recv/{msg_id}/view"
    }


@app.get("/recv/{msg_id}")
def recv(msg_id: str):
    """Retrieve and delete a message"""
    entry = store.get(msg_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Message not found or expired")
    entry["views_left"] -= 1
    msg = entry["data"]
    if entry["views_left"] <= 0:
        del store[msg_id]
    return {"text": msg}


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    """Serve homepage"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/recv/{msg_id}/view", response_class=HTMLResponse)
def view_message(request: Request, msg_id: str):
    """Serve message viewing page with countdown"""
    entry = store.get(msg_id)
    ttl_seconds = 0
    if entry:
        ttl_seconds = max(0, int(entry["expires"] - time.time()))
    return templates.TemplateResponse("view.html", {"request": request, "msg_id": msg_id, "ttl": ttl_seconds})
