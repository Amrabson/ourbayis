# -*- coding: utf-8 -*-
"""OurBayis ops CLI. Run with `python manage.py <command>`.

create-admin   -- interactively (or via OB_ADMIN_PASSWORD) create an admin user
backup         -- online backup of the live DB with an integrity check
send-mail      -- flush the mail outbox (run this on a schedule if SMTP is set)
expire-claims  -- flip reserved claims past expires_at to 'expired'
check          -- integrity check + basic config sanity, exit 1 on problems
stats          -- print basic counts (no PII)
seed-sync      -- adopt/insert catalog rows from seed_catalog.json by seed_key;
                  with --fields, explicitly overwrite those fields from the seed
                  (both default to a dry run printing a diff table; pass --apply to write)
refresh-registry-links -- copy url/image/store/brand from catalog to registry_items
                  that came from the catalog, skipping any field the couple overrode
                  (dry run by default; pass --apply to write)
"""
import argparse
import getpass
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import ob_db
import ob_mail
from werkzeug.security import generate_password_hash

BASE = Path(__file__).resolve().parent


def _db_path():
    return Path(os.environ.get("OB_DB_PATH") or (BASE / "ourbayis.db"))


def _open(migrate=True):
    db = ob_db.connect(_db_path())
    if migrate:
        ob_db.migrate(db)
    return db


def cmd_create_admin(args):
    db = _open()
    username = args.username
    pw = os.environ.get("OB_ADMIN_PASSWORD") or getpass.getpass("Password (12+ chars): ")
    if len(pw) < 12:
        print("Password must be at least 12 characters.", file=sys.stderr)
        return 1
    existing = db.execute("SELECT 1 FROM admins WHERE username=?", (username,)).fetchone()
    if existing:
        print(f"Admin '{username}' already exists.", file=sys.stderr)
        return 1
    with ob_db.write_txn(db):
        db.execute("INSERT INTO admins (username, pw_hash) VALUES (?,?)",
                   (username, generate_password_hash(pw)))
    print(f"Admin '{username}' created.")
    return 0


def cmd_backup(args):
    dst = args.dest or str(BASE / "backups" / f"ourbayis-{datetime.utcnow():%Y-%m-%d-%H%M%S}.db")
    path = ob_db.backup(_db_path(), dst)
    print(f"Backup written and verified: {path}")
    return 0


def cmd_send_mail(args):
    db = _open()
    n = ob_mail.flush(db, limit=args.limit)
    print(f"Processed {n} due message(s).")
    return 0


def cmd_expire_claims(args):
    db = _open()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with ob_db.write_txn(db):
        rows = db.execute(
            "SELECT id FROM claims WHERE status='reserved' AND expires_at IS NOT NULL"
            " AND expires_at<=?", (now,)).fetchall()
        for r in rows:
            db.execute("UPDATE claims SET status='expired', cancelled_by='system' WHERE id=?",
                       (r["id"],))
            db.execute(
                "INSERT INTO claim_events (claim_id, event, actor, note) VALUES (?,?,?,?)",
                (r["id"], "expired", "system", ""))
    print(f"Expired {len(rows)} claim(s).")
    return 0


REMIND_AFTER_DAYS = 5   # reservation age before the single nudge
REMIND_LIMIT = 200       # per run, so a backlog never floods the outbox


def cmd_remind_claims(args):
    """Queue ONE reminder to each guest who reserved a gift with an email,
    hasn't reported it after REMIND_AFTER_DAYS, and hasn't been reminded.
    Idempotent: sets claims.reminded_at, so re-running never sends twice.
    Bodies are bilingual (claims don't record the guest's language)."""
    import i18n
    db = _open()
    cutoff = (datetime.utcnow() - timedelta(days=REMIND_AFTER_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    base = os.environ.get("OB_BASE_URL", "").rstrip("/")
    rows = db.execute(
        "SELECT c.id, c.guest_email, c.token_hash, c.expires_at, c.kind,"
        " ri.name AS item_name, r.title AS reg_title, r.slug FROM claims c"
        " JOIN registries r ON r.id = c.registry_id"
        " LEFT JOIN registry_items ri ON ri.id = c.item_id"
        " WHERE c.status='reserved' AND c.guest_email != '' AND c.reminded_at IS NULL"
        " AND c.created_at <= ? AND (c.expires_at IS NULL OR c.expires_at > ?)"
        " ORDER BY c.created_at LIMIT ?", (cutoff, now, REMIND_LIMIT)).fetchall()
    if args.dry_run:
        print(f"{len(rows)} reminder(s) would be queued.")
        return 0
    sent = 0
    for r in rows:
        # the raw recovery token is never stored, so the reminder points at the
        # registry (the guest's own "save this link" email carried the /g/ link)
        link = f"{base}/r/{r['slug']}" if base else f"/r/{r['slug']}"
        item = r["item_name"] or i18n.t("gift_cash", "en")
        item_he = r["item_name"] or i18n.t("gift_cash", "he")
        subject = i18n.t("mail_remind_subj", "en").format(item=item)
        body = (i18n.t("mail_remind_body", "en").format(item=item, title=r["reg_title"], link=link,
                                                        until=(r["expires_at"] or "")[:10])
                + "\n\n— — —\n\n"
                + i18n.t("mail_remind_body", "he").format(item=item_he, title=r["reg_title"], link=link,
                                                          until=(r["expires_at"] or "")[:10]))
        with ob_db.write_txn(db):
            # mark first, then queue — a crash between the two loses one nudge, never repeats it
            db.execute("UPDATE claims SET reminded_at=? WHERE id=? AND reminded_at IS NULL",
                       (now, r["id"]))
            ob_mail.enqueue(db, r["guest_email"], subject, body)
        sent += 1
    print(f"Queued {sent} reminder(s).")
    return 0


def cmd_check(args):
    """Read-only: never migrates, so it's safe to run against any copy of the DB."""
    problems = []
    db = _open(migrate=False)
    pending = ob_db.pending_migrations(db)
    if pending:
        problems.append(f"{len(pending)} pending migration(s) — they run automatically when the"
                        " app starts (or via any other manage.py command); back up first")
    integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        problems.append(f"integrity_check: {integrity}")
    fk = db.execute("PRAGMA foreign_key_check").fetchall()
    if fk:
        problems.append(f"foreign_key_check found {len(fk)} violation(s)")
    n_admins = db.execute("SELECT COUNT(*) FROM admins").fetchone()[0]
    if n_admins == 0:
        problems.append("no admins exist — run `python manage.py create-admin <username>`")
    secure = os.environ.get("OB_SECURE_COOKIES")
    if secure and not os.environ.get("OB_SECRET_KEY"):
        problems.append("OB_SECURE_COOKIES set but OB_SECRET_KEY missing")
    if problems:
        for p in problems:
            print(f"PROBLEM: {p}")
        return 1
    print("OK — no problems found.")
    return 0


def cmd_stats(args):
    db = _open()
    for label, sql in (
        ("users", "SELECT COUNT(*) FROM users"),
        ("registries", "SELECT COUNT(*) FROM registries"),
        ("claims", "SELECT COUNT(*) FROM claims"),
        ("claims reserved", "SELECT COUNT(*) FROM claims WHERE status='reserved'"),
        ("shana leads", "SELECT COUNT(*) FROM shana_requests"),
        ("mail queued", "SELECT COUNT(*) FROM mail_outbox WHERE status='queued'"),
    ):
        n = db.execute(sql).fetchone()[0]
        print(f"{label}: {n}")
    return 0


def cmd_seed_sync(args):
    import json
    seed_path = BASE / "seed_catalog.json"
    seed = json.loads(seed_path.read_text(encoding="utf-8"))
    db = _open()
    if args.fields:
        fields = [f.strip() for f in args.fields.split(",") if f.strip()]
        with ob_db.write_txn(db):
            diffs = ob_db.seed_overwrite(db, seed.get("items", []), fields, dry_run=(not args.apply))
        if not diffs:
            print("No differences.")
        else:
            print(f"{'seed_key':<30} {'name':<40} {'field':<14} {'old':<20} {'new':<20}")
            for key, name, field, old, new in diffs:
                print(f"{key:<30} {name[:38]:<40} {field:<14} {str(old)[:18]:<20} {str(new)[:18]:<20}")
        print(f"\n{len(diffs)} field(s) would change." if (not args.apply)
              else f"\n{len(diffs)} field(s) changed.")
    else:
        with ob_db.write_txn(db):
            counters = ob_db.seed_sync(db, seed.get("items", []), dry_run=(not args.apply))
            ob_db.bundle_sync(db, seed.get("bundles", []))
        verb = "would be" if (not args.apply) else ""
        print(f"Adopted {counters['adopted']} legacy row(s), inserted {counters['inserted']}"
              f" new row(s) {verb}, {counters['unchanged']} already in sync.")
    return 0


def cmd_refresh_registry_links(args):
    db = _open()
    with ob_db.write_txn(db):
        diffs = ob_db.refresh_registry_links(db, dry_run=(not args.apply))
    if not diffs:
        print("No differences.")
    else:
        print(f"{'item_id':<10} {'field':<10} {'old':<40} {'new':<40}")
        for item_id, field, old, new in diffs:
            print(f"{item_id:<10} {field:<10} {str(old)[:38]:<40} {str(new)[:38]:<40}")
    print(f"\n{len(diffs)} field(s) would change." if (not args.apply)
          else f"\n{len(diffs)} field(s) changed.")
    return 0


def cmd_fetch_rates(args):
    import ob_money
    try:
        rates, date = ob_money.fetch_rates()
    except Exception as exc:  # noqa: BLE001 — a failed fetch must leave the old file alone
        print(f"fetch-rates failed: {exc}")
        return 1
    print(f"rates as of {date} (ILS per unit): " + ", ".join(f"{k} {v}" for k, v in rates.items()))
    print(f"written to {ob_money.RATES_FILE}")
    return 0


def main():
    p = argparse.ArgumentParser(prog="manage.py")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("create-admin")
    sp.add_argument("username")
    sp.set_defaults(fn=cmd_create_admin)

    sp = sub.add_parser("backup")
    sp.add_argument("--dest", default=None)
    sp.set_defaults(fn=cmd_backup)

    sp = sub.add_parser("send-mail")
    sp.add_argument("--limit", type=int, default=50)
    sp.set_defaults(fn=cmd_send_mail)

    sp = sub.add_parser("expire-claims")
    sp.set_defaults(fn=cmd_expire_claims)

    sp = sub.add_parser("remind-claims",
                        help="queue one nudge per stale reservation that has a guest email")
    sp.add_argument("--dry-run", action="store_true")
    sp.set_defaults(fn=cmd_remind_claims)

    sp = sub.add_parser("check")
    sp.set_defaults(fn=cmd_check)

    sp = sub.add_parser("stats")
    sp.set_defaults(fn=cmd_stats)

    sp = sub.add_parser("seed-sync")
    sp.add_argument("--apply", action="store_true",
                     help="write changes (default is a dry run)")
    sp.add_argument("--fields", default="",
                     help="comma list (e.g. price_nis,url,image,store,brand,featured):"
                          " explicitly overwrite these fields from the seed by seed_key."
                          " Without --fields, only adopts/inserts (never overwrites).")
    sp.set_defaults(fn=cmd_seed_sync)

    sp = sub.add_parser("fetch-rates",
                        help="pull ECB reference rates (frankfurter.app) into instance/rates.json")
    sp.set_defaults(fn=cmd_fetch_rates)

    sp = sub.add_parser("refresh-registry-links")
    sp.add_argument("--apply", action="store_true",
                     help="write changes (default is a dry run)")
    sp.set_defaults(fn=cmd_refresh_registry_links)

    args = p.parse_args()
    sys.exit(args.fn(args) or 0)


if __name__ == "__main__":
    main()
