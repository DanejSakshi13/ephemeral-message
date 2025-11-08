import time, threading, secrets
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles


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

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
        <head>
            <title>Ephemeral Message Relay</title>
            <style>
                body {
                    font-family: system-ui;
                    background: #f9fafb;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    height: 100vh;
                }
                textarea {
                    width: 300px;
                    height: 100px;
                    margin: 10px 0;
                    font-size: 1rem;
                }
                button {
                    background-color: #2563eb;
                    color: white;
                    border: none;
                    padding: 10px 20px;
                    border-radius: 8px;
                    cursor: pointer;
                }
                button:hover {
                    background-color: #1d4ed8;
                }
                #output {
                    margin-top: 20px;
                    word-wrap: break-word;
                }
            </style>
        </head>
        <body>
            <h1>🔐 Ephemeral Message</h1>
            <textarea id="msg" placeholder="Type your message here..."></textarea><br/>
            <button onclick="sendMessage()">Send</button>

            <div id="output"></div>

            <script>
                async function sendMessage() {
                    const msg = document.getElementById("msg").value;
                    const res = await fetch('/send', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ text: msg })
                    });
                    const data = await res.json();
                    document.getElementById("output").innerHTML = 
                        '<p>✅ Message stored for 1 minute.</p>' +
                        '<p>Share this link:</p>' +
                        '<a href="' + data.link + '" target="_blank">' + window.location.origin + data.link + '</a>';
                    document.getElementById("msg").value = '';
                }
            </script>
        </body>
    </html>
    """

@app.get("/recv/{msg_id}/view", response_class=HTMLResponse)
def view_message(msg_id: str):
    return f"""
    <html>
        <head>
            <title>View Message</title>
            <style>
                body {{
                    font-family: system-ui;
                    background: #f9fafb;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    height: 100vh;
                }}
                #msg {{
                    background: white;
                    padding: 20px;
                    border-radius: 12px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    width: 300px;
                    text-align: center;
                }}
            </style>
        </head>
        <body>
            <div id="msg">Loading...</div>
            <script>
                async function fetchMsg() {{
                    const res = await fetch('/recv/{msg_id}');
                    const data = await res.json();
                    document.getElementById("msg").innerText = data.text;
                }}
                fetchMsg();
            </script>
        </body>
    </html>
    """


