#!/bin/bash
# Holy Chip War Room Launcher
PORT=8888
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Kill any existing instance
pkill -f "python3 $SCRIPT_DIR/server.py" 2>/dev/null
sleep 0.3

# Start server
cd "$SCRIPT_DIR"
python3 server.py &>/tmp/warroom.log &
echo $! > /tmp/warroom.pid
sleep 1

# Open browser
open "http://localhost:$PORT"
echo "⚡ WAR ROOM running at http://localhost:$PORT"
echo "   PID: $(cat /tmp/warroom.pid)"
echo "   Log: tail -f /tmp/warroom.log"
