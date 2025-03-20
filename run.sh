#!/bin/bash
echo "Using Python at: $(which python3)"
gunicorn --worker-class eventlet --workers 1 --bind 0.0.0.0:5000 app:app
