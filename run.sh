#!/bin/bash
pip install -r requirements.txt
gunicorn -w 1 app:app
