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
# PythonAnywhere sits behind a proxy — tell Flask to trust its X-Forwarded-* headers
# (rate-limit keys still use request.remote_addr only, never a client-supplied header).
os.environ.setdefault("OB_TRUST_PROXY", "1")
# Canonical site URL, used for every link in emails/sitemap/robots (works even if
# OB_TRUST_PROXY is off, and keeps links correct behind PythonAnywhere's proxy).
os.environ.setdefault("OB_BASE_URL", "https://REPLACE-WITH-YOUR-DOMAIN")
# os.environ.setdefault("OB_ALLOWED_HOSTS", "ourbayis.com,www.ourbayis.com")

# --- optional: email notifications (leave unset to disable — mail still queues
#     in mail_outbox and is visible via `python manage.py stats`, just unsent) ---
# os.environ.setdefault("OB_SMTP_HOST", "smtp.gmail.com")
# os.environ.setdefault("OB_SMTP_PORT", "587")
# os.environ.setdefault("OB_SMTP_USER", "you@gmail.com")
# os.environ.setdefault("OB_SMTP_PASS", "your-gmail-app-password")
# os.environ.setdefault("OB_NOTIFY_EMAIL", "you@gmail.com")

# --- optional: contact WhatsApp number, USD estimate rate ---
# os.environ.setdefault("OB_WHATSAPP", "972501234567")
# os.environ.setdefault("OB_ILS_PER_USD", "3.7")

# --- optional: currency estimates for cash gifts other than ILS/USD ---
# os.environ.setdefault("OB_RATES", '{"USD": 3.7, "GBP": 4.75}')
# os.environ.setdefault("OB_RATES_DATE", "2026-09-01")

# NOTE: there is no default admin anymore. After first deploy, run in a Bash
# console: `python manage.py create-admin <username>` (OB_DB_PATH + this file's
# env vars apply automatically if you run it via `python -m` inside the venv
# with the same working directory — otherwise export OB_DB_PATH first).

from app import app as application  # noqa: E402
