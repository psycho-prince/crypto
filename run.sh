#!/bin/bash
# Install dependencies
pip install -r requirements.txt

# Run the Flask app with Gunicorn
gunicorn -w 1 -b 0.0.0.0:5000 app:app --worker-class eventlet
