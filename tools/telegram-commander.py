#!/usr/bin/env python3
"""
Telegram Commander -- polls Telegram for messages, executes them as Claude Code tasks.
Send a message to your bot, it runs `claude` CLI and replies with the result.

Usage: python3 telegram-commander.py
Runs forever, checks every 30 seconds.
"""
import os
import sys
import json
import time
import subprocess
import requests

# Flush output immediately for logging
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# Load creds
def load_env():
    env_file = os.path.expanduser("~/claude-agent/.env")
    env = {}
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                key, val = line.split("=", 1)
                env[key] = val.strip('"').strip("'")
    return env

ENV = load_env()
BOT_TOKEN = ENV["TELEGRAM_BOT_TOKEN"]
CHAT_ID = ENV["TELEGRAM_HOME_CHANNEL"]
API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Track last processed message
OFFSET_FILE = os.path.expanduser("~/.telegram-commander-offset")

def get_offset():
    if os.path.exists(OFFSET_FILE):
        with open(OFFSET_FILE) as f:
            return int(f.read().strip())
    return 0

def save_offset(offset):
    with open(OFFSET_FILE, "w") as f:
        f.write(str(offset))

def get_updates(offset):
    try:
        resp = requests.get(f"{API}/getUpdates", params={
            "offset": offset,
            "timeout": 10,
            "allowed_updates": json.dumps(["message"])
        }, timeout=15)
        data = resp.json()
        if data.get("ok"):
            return data.get("result", [])
    except Exception as e:
        print(f"Error fetching updates: {e}")
    return []

def send_message(text, reply_to=None):
    # Telegram max message length is 4096
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
    for chunk in chunks:
        params = {
            "chat_id": CHAT_ID,
            "text": chunk,
            "parse_mode": "Markdown"
        }
        if reply_to:
            params["reply_to_message_id"] = reply_to
        try:
            requests.post(f"{API}/sendMessage", json=params, timeout=10)
        except:
            # Retry without markdown if it fails
            params.pop("parse_mode", None)
            requests.post(f"{API}/sendMessage", json=params, timeout=10)

def run_claude(prompt):
    """Run claude CLI with the prompt and return the output."""
    try:
        result = subprocess.run(
            ["claude", "--print", "--dangerously-skip-permissions", prompt],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute max
            cwd=os.path.expanduser("~")
        )
        output = result.stdout.strip()
        if result.stderr.strip():
            output += f"\n\nSTDERR: {result.stderr.strip()}"
        return output if output else "(no output)"
    except subprocess.TimeoutExpired:
        return "Task timed out after 5 minutes."
    except FileNotFoundError:
        return "Error: `claude` CLI not found. Make sure it's in PATH."
    except Exception as e:
        return f"Error running claude: {e}"

def main():
    print("Telegram Commander started")
    print(f"Bot: {BOT_TOKEN[:10]}...")
    print(f"Chat: {CHAT_ID}")
    print("Waiting for messages...\n")

    offset = get_offset()

    while True:
        updates = get_updates(offset)

        for update in updates:
            offset = update["update_id"] + 1
            save_offset(offset)

            msg = update.get("message", {})
            chat_id = str(msg.get("chat", {}).get("id", ""))
            text = msg.get("text", "")
            msg_id = msg.get("message_id")

            # Only process messages from our chat
            if chat_id != CHAT_ID:
                continue

            # Skip commands to the bot itself
            if not text or text.startswith("/start"):
                continue

            # Skip if it looks like a bot message (from ourselves)
            if msg.get("from", {}).get("is_bot", False):
                continue

            print(f"Task received: {text[:80]}...")
            send_message("⏳ Working on it...", reply_to=msg_id)

            # Run claude
            result = run_claude(text)

            print(f"Done. Response: {len(result)} chars")
            send_message(result, reply_to=msg_id)

        time.sleep(5)

if __name__ == "__main__":
    main()
