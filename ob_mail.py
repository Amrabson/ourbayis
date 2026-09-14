# -*- coding: utf-8 -*-
"""OurBayis mail outbox — persistent queue backed by `mail_outbox`, so a send
survives a process restart and is visible even without SMTP configured.
See SPEC_V3.md "Module layout" / ob_mail.py. Never logs message bodies."""
import os
import smtplib
import threading
from datetime import datetime, timedelta
from email.message import EmailMessage

import ob_db

BACKOFF_MINUTES = [1, 5, 30, 120, 720]  # 1m, 5m, 30m, 2h, 12h
MAX_ATTEMPTS = 6


def _smtp_config():
    host = os.environ.get("OB_SMTP_HOST", "")
    user = os.environ.get("OB_SMTP_USER", "")
    pw = os.environ.get("OB_SMTP_PASS", "")
    port = int(os.environ.get("OB_SMTP_PORT", "587"))
    return host, port, user, pw


def _now_iso():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def enqueue(db, to, subject, body, db_path=None):
    """Insert a queued row and, if SMTP is configured, kick off a best-effort
    background attempt on its own connection. Always returns the row id."""
    if not to:
        return None
    with ob_db.write_txn(db):
        cur = db.execute(
            "INSERT INTO mail_outbox (to_addr, subject, body, status, next_attempt_at)"
            " VALUES (?,?,?, 'queued', ?)",
            (to, subject, body, _now_iso()))
        row_id = cur.lastrowid
    host, port, user, pw = _smtp_config()
    if host and user and pw:
        path = db_path or db.execute("PRAGMA database_list").fetchone()[2]

        def _bg():
            conn = ob_db.connect(path)
            try:
                attempt(conn, row_id)
            finally:
                conn.close()
        threading.Thread(target=_bg, daemon=True).start()
    return row_id


def attempt(db, row_id):
    """Try to send one queued row now. Marks sent on success; on failure bumps
    attempts, schedules the next try with backoff, records last_error (never
    the body), and marks 'failed' after MAX_ATTEMPTS."""
    row = db.execute("SELECT * FROM mail_outbox WHERE id=?", (row_id,)).fetchone()
    if not row or row["status"] == "sent":
        return
    host, port, user, pw = _smtp_config()
    if not (host and user and pw):
        return  # stays queued — nothing to do without SMTP
    try:
        msg = EmailMessage()
        msg["From"] = user
        msg["To"] = row["to_addr"]
        msg["Subject"] = row["subject"]
        msg.set_content(row["body"])
        with smtplib.SMTP(host, port, timeout=15) as s:
            s.starttls()
            s.login(user, pw)
            s.send_message(msg)
        with ob_db.write_txn(db):
            db.execute("UPDATE mail_outbox SET status='sent', sent_at=?, last_error='' WHERE id=?",
                       (_now_iso(), row_id))
    except Exception as e:  # noqa: BLE001 — smtplib/socket errors of many types
        attempts = row["attempts"] + 1
        status = "failed" if attempts >= MAX_ATTEMPTS else "queued"
        idx = min(attempts - 1, len(BACKOFF_MINUTES) - 1)
        next_at = (datetime.utcnow() + timedelta(minutes=BACKOFF_MINUTES[idx])).strftime("%Y-%m-%d %H:%M:%S")
        err = type(e).__name__  # error class only — never body content, and no secrets
        with ob_db.write_txn(db):
            db.execute(
                "UPDATE mail_outbox SET attempts=?, status=?, next_attempt_at=?, last_error=? WHERE id=?",
                (attempts, status, next_at, err, row_id))


def flush(db, limit=50):
    """Process every due queued row synchronously — used by `manage.py send-mail`
    (a scheduled task) since there's no SMTP daemon thread without SMTP config."""
    rows = db.execute(
        "SELECT id FROM mail_outbox WHERE status='queued' AND next_attempt_at<=?"
        " ORDER BY next_attempt_at LIMIT ?", (_now_iso(), limit)).fetchall()
    for r in rows:
        attempt(db, r["id"])
    return len(rows)


def outbox_counts(db):
    rows = db.execute("SELECT status, COUNT(*) AS n FROM mail_outbox GROUP BY status").fetchall()
    return {r["status"]: r["n"] for r in rows}
