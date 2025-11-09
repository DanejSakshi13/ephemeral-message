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
                select, button {
                    margin-top: 8px;
                    font-size: 1rem;
                    padding: 8px 12px;
                    border-radius: 8px;
                }
                button {
                    background-color: #2563eb;
                    color: white;
                    border: none;
                    cursor: pointer;
                }
                button:hover {
                    background-color: #1d4ed8;
                }
                #output {
                    margin-top: 20px;
                    word-wrap: break-word;
                    text-align: center;
                }
                #copyBtn {
                    background-color: #10b981;
                    margin-top: 8px;
                }
                #copyBtn:hover {
                    background-color: #059669;
                }
            </style>
        </head>
        <body>
            <h1>🔐 Ephemeral Message</h1>

            <textarea id="msg" placeholder="Type your message here..."></textarea><br/>

            <label for="ttl">Keep message alive for:</label>
            <select id="ttl">
                <option value="60">1 minute</option>
                <option value="120">2 minutes</option>
                <option value="300">5 minutes</option>
            </select><br/>

            <button onclick="sendMessage()">Send</button>

            <div id="output"></div>

          <script>
    async function sendMessage() {
        const msg = document.getElementById("msg").value.trim();
        if (!msg) {
            alert("Please enter a message!");
            return;
        }

        const ttl = parseInt(document.getElementById("ttl").value);
        const res = await fetch('/send', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: msg, ttl: ttl })
        });
        const data = await res.json();
        const fullLink = window.location.origin + data.link + '/view';
        document.getElementById("output").innerHTML = `
            <p> Message stored for <strong>${ttl / 60}</strong> minute(s).</p>
            <p>Share this link:</p>
            <a id="msgLink" href="${data.link}/view" target="_blank">${fullLink}</a><br/>
            <button id="copyBtn" onclick="copyLink()">Copy Link</button>
            <p id="copyStatus" style="color: gray; font-size: 0.9rem; margin-top: 4px;"></p>
        `;
        document.getElementById("msg").value = '';
    }

    async function copyLink() {
    const link = document.getElementById("msgLink").href;
    try {
        await navigator.clipboard.writeText(link);  
        document.getElementById("copyStatus").innerText = " Link copied to clipboard!";
        setTimeout(() => {
            document.getElementById("copyStatus").innerText = "";
        }, 2000);
    } catch (err) {
        document.getElementById("copyStatus").innerText = " Failed to copy link.";
    }
}

</script>

        </body>
    </html>
    """


@app.get("/recv/{msg_id}/view", response_class=HTMLResponse)
def view_message(msg_id: str):
    ttl_seconds = 0
    entry = store.get(msg_id)
    if entry:
        # Calculate remaining time for countdown
        ttl_seconds = int(entry["expires"] - time.time())
        if ttl_seconds < 0:
            ttl_seconds = 0

    return f"""
    <html>
        <head>
            <title>View Message</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{
                    font-family: system-ui;
                    background: #f9fafb;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    height: 100vh;
                    overflow: hidden;
                    user-select: none;
                    -webkit-user-select: none;
                }}
                #msg {{
                    background: white;
                    padding: 20px;
                    border-radius: 12px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    width: 300px;
                    text-align: center;
                    position: relative;
                }}
                #timer {{
                    margin-top: 10px;
                    color: #ef4444;
                    font-weight: bold;
                }}
                #overlay {{
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background: rgba(0,0,0,0);
                    z-index: 9999;
                    display: none;
                }}
            </style>
        </head>
        <body>
            <div id="msg">Loading message...</div>
            <div id="timer"></div>
            <div id="overlay"></div>
            
            <script>
                async function fetchMsg() {{
                    try {{
                        const res = await fetch('/recv/{msg_id}');
                        if (!res.ok) {{
                            document.getElementById("msg").innerText = "⚠️ Message not found or expired.";
                            return;
                        }}
                        const data = await res.json();
                        document.getElementById("msg").innerText = data.text;
                        startCountdown({ttl_seconds});
                    }} catch (err) {{
                        document.getElementById("msg").innerText = "Error loading message.";
                    }}
                }}

                function startCountdown(seconds) {{
                    let remaining = seconds;
                    const timer = document.getElementById("timer");
                    const interval = setInterval(() => {{
                        if (remaining <= 0) {{
                            clearInterval(interval);
                            timer.innerText = "⏳ Message expired. Refreshing...";
                            setTimeout(() => location.reload(), 1500);
                            return;
                        }}
                        const mins = Math.floor(remaining / 60);
                        const secs = remaining % 60;
                        timer.innerText = `⏰ Disappearing in: ${{mins}}m ${{secs}}s`;
                        remaining--;
                    }}, 1000);
                }}

                // Screenshot prevention (limited, client-side)
                document.addEventListener("keydown", function(e) {{
                    if (e.key === "PrintScreen") {{
                        navigator.clipboard.writeText("Screenshots are disabled for this message.");
                        alert(" Screenshots disabled for this message.");
                        e.preventDefault();
                    }}
                    if ((e.ctrlKey || e.metaKey) && (e.key === "s" || e.key === "p")) {{
                        e.preventDefault();
                        alert(" Saving/Printing disabled.");
                    }}
                }});

                document.addEventListener("visibilitychange", function() {{
                    if (document.hidden) {{
                        alert(" Please do not switch tabs while viewing this message.");
                        location.reload();
                    }}
                }});

                // Attempt to block context menu (right-click)
                document.addEventListener("contextmenu", e => e.preventDefault());

                fetchMsg();
            </script>
        </body>
    </html>
    """



