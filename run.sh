#!/bin/bash
PYTHON_CMD="/opt/render/project/src/.venv/bin/python3"
if [ ! -f "$PYTHON_CMD" ]; then
    PYTHON_CMD=$(command -v python3 || echo "python3 not found")
fi
if [ "$PYTHON_CMD" = "python3 not found" ]; then
    echo "Error: Python 3 not found"
    exit 1
fi
echo "Using Python at: $PYTHON_CMD"

if [ ! -f "bot.py" ]; then
    echo "Error: bot.py not found"
    exit 1
fi
if [ ! -f "webapp.py" ]; then
    echo "Error: webapp.py not found"
    exit 1
fi

"$PYTHON_CMD" bot.py &  # Runs bot in background
"$PYTHON_CMD" webapp.py  # Runs Flask in foreground
