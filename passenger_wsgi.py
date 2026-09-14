# -*- coding: utf-8 -*-
"""PythonAnywhere WSGI entry point.

On PythonAnywhere: Web tab -> your app -> WSGI configuration file -> replace
its contents with this file's contents (adjust the path and secrets below).
Everything here is safe to keep in git EXCEPT real secret values — this file
ships with placeholders, not real keys.
"""
import os
import sys

# Path to the project on PythonAnywhere, e.g. /home/yourusername/ourbayis
project_home = "/home/YOURUSERNAME/ourbayis"
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# --- required in production ---
os.environ.setdefault("OB_SECRET_KEY", "REPLACE-WITH-A-LONG-RANDOM-SECRET")
os.environ.setdefault("OB_SECURE_COOKIES", "1")

# --- optional: email notifications (leave unset to disable) ---
# os.environ.setdefault("OB_SMTP_HOST", "smtp.gmail.com")
# os.environ.setdefault("OB_SMTP_PORT", "587")
# os.environ.setdefault("OB_SMTP_USER", "you@gmail.com")
# os.environ.setdefault("OB_SMTP_PASS", "your-gmail-app-password")
# os.environ.setdefault("OB_NOTIFY_EMAIL", "you@gmail.com")

# --- optional: contact WhatsApp number, USD estimate rate ---
# os.environ.setdefault("OB_WHATSAPP", "972501234567")
# os.environ.setdefault("OB_ILS_PER_USD", "3.7")

from app import app as application  # noqa: E402
