#!/bin/bash
# Install dependencies
pip install -r requirements.txt

# Run the Flask app with Gunicorn, binding to the PORT environment variable
gunicorn -w 1 -b 0.0.0.0:$PORT app:app --worker-class eventlet
