#!/bin/bash
set -e

# Start the chdb server wrapper in the background
python3 main.py &
SERVER_PID=$!

# Wait for the server to be ready
for i in {1..10}; do
  if curl -s http://localhost:8123/ping | grep -q 'Ok'; then
    break
  fi
  sleep 1
done

# Test the chdb server wrapper
curl -G --data-urlencode "query=SELECT version(), now()" http://test:test@localhost:8123

# Stop the server
kill $SERVER_PID
wait $SERVER_PID 2>/dev/null || true 