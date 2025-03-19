#!/bin/bash
PYTHON_CMD=$(command -v python3 || echo "python3 not found")
if [ "$PYTHON_CMD" = "python3 not found" ]; then
    echo "Error: Python 3 not found"
    exit 1
fi
echo "Using Python at: $PYTHON_CMD"
"$PYTHON_CMD" bot.py &  # Runs in background
"$PYTHON_CMD" webapp.py  # Runs in foreground
