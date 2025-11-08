import time, threading, secrets
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Ephemeral Message Relay")

TTL_SECONDS = 60
store = {}  # {id: {"data": str, "expires": float, "views_left": int}}

class MessageIn(BaseModel):
    text: str
    ttl: int | None = None
    max_views: int | None = 1

@app.on_event("startup")
def start_cleanup_thread():
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
        "link": f"/recv/{msg_id}"
    }

@app.get("/recv/{msg_id}")
def recv(msg_id: str):
    entry = store.get(msg_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Message not found or expired")
    entry["views_left"] -= 1
    msg = entry["data"]
    if entry["views_left"] <= 0:
        del store[msg_id]
    return {"text": msg}

@app.get("/health")
def health():
    return {"status": "ok", "messages": len(store)}
