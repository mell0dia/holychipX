#!/usr/bin/env python3
"""Send the War Room bundle to Telegram."""
import os, json, urllib.request

# Load env
with open(os.path.expanduser("~/.hermes/.env")) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

token = os.environ.get("TELEGRAM_BOT_TOKEN")
chat_id = "8359108685"

url = f"https://api.telegram.org/bot{token}/sendDocument"
boundary = "----BundleBoundary7MA4YWxkTrZu0gW"

file_path = os.path.expanduser("~/holy-chip/warroom/warroom-mobile.html")
with open(file_path, "rb") as f:
    file_data = f.read()

body = (
    f"--{boundary}\r\n"
    f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{chat_id}\r\n'
    f"--{boundary}\r\n"
    f'Content-Disposition: form-data; name="caption"\r\n\r\n⚡ War Room — Offline Snapshot\r\n'
    f"--{boundary}\r\n"
    f'Content-Disposition: form-data; name="document"; filename="warroom-mobile.html"\r\n'
    f"Content-Type: text/html\r\n\r\n"
).encode() + file_data + f"\r\n--{boundary}--\r\n".encode()

req = urllib.request.Request(url, data=body, method="POST")
req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")

resp = urllib.request.urlopen(req, timeout=30)
result = json.loads(resp.read())
print("✅ Sent to Telegram!" if result.get("ok") else f"❌ Failed: {result}")
