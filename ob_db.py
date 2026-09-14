# -*- coding: utf-8 -*-
"""OurBayis database layer — connection, versioned migrations, transactions.

Design (see SPEC_V3.md "Module layout" + "Schema v3"):
- `connect(path)` opens a sqlite3 connection tuned for a small server-rendered
  site sharing one file on disk: short busy timeout + retrying writers instead
  of WAL (OneDrive/PythonAnywhere filesystems don't like WAL).
- `MIGRATIONS` is an ordered list of idempotent functions, tracked in
  `schema_migrations`. `migrate(db)` applies whichever haven't run yet.
- `write_txn(db)` is the only place multi-statement writes should happen:
  BEGIN IMMEDIATE + bounded retry on SQLITE_BUSY, commit/rollback for you.
- `backup(src, dst)` makes an online backup and verifies it.
"""
import contextlib
import json
import sqlite3
import time
import unicodedata
import re
from pathlib import Path

from werkzeug.security import generate_password_hash

BASE = Path(__file__).resolve().parent


def connect(path):
    """Open a tuned connection: Row factory, autocommit (isolation_level=None)
    so callers explicitly opt into transactions via write_txn(), FK enforcement,
    and a generous busy timeout so concurrent readers/writers don't fail fast."""
    db = sqlite3.connect(str(path), timeout=10, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA busy_timeout = 10000")
    return db


def has_column(db, table, col):
    rows = db.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r["name"] == col for r in rows)


def has_table(db, table):
    return db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def _add_column(db, table, coldef):
    """coldef e.g. 'archived INTEGER DEFAULT 0' — idempotent via has_column."""
    col = coldef.split()[0]
    if not has_column(db, table, col):
        db.execute(f"ALTER TABLE {table} ADD COLUMN {coldef}")


def _slugify(text):
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return text or "item"


# ------------------------------------------------------------------ migrations
def _exec_statements(db, script):
    """Run each ';'-terminated statement in `script` via db.execute() instead of
    executescript() — executescript() implicitly commits any open transaction,
    which breaks the manual BEGIN IMMEDIATE ... COMMIT that write_txn() manages."""
    for stmt in script.split(";"):
        stmt = stmt.strip()
        if stmt:
            db.execute(stmt)


def _m001_initial_schema(db):
    """The original tables, as CREATE TABLE IF NOT EXISTS — safe on a fresh DB
    and a no-op on an existing one (columns added later live in later migrations)."""
    _exec_statements(db, """
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      email TEXT UNIQUE NOT NULL,
      pw_hash TEXT NOT NULL,
      name TEXT DEFAULT '',
      created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS registries (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      slug TEXT UNIQUE NOT NULL,
      title TEXT NOT NULL,
      title_he TEXT DEFAULT '',
      couple_names TEXT NOT NULL,
      couple_names_he TEXT DEFAULT '',
      event_type TEXT DEFAULT 'wedding',
      event_date TEXT DEFAULT '',
      city TEXT DEFAULT '',
      message TEXT DEFAULT '',
      message_he TEXT DEFAULT '',
      paypal_url TEXT DEFAULT '',
      stripe_url TEXT DEFAULT '',
      bit_url TEXT DEFAULT '',
      is_public INTEGER DEFAULT 1,
      views INTEGER DEFAULT 0,
      created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS registry_items (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      registry_id INTEGER NOT NULL REFERENCES registries(id) ON DELETE CASCADE,
      catalog_id INTEGER,
      name TEXT NOT NULL,
      name_he TEXT DEFAULT '',
      brand TEXT DEFAULT '',
      category TEXT DEFAULT 'home',
      price_nis INTEGER DEFAULT 0,
      store TEXT DEFAULT '',
      url TEXT DEFAULT '',
      image TEXT DEFAULT '',
      qty_wanted INTEGER DEFAULT 1,
      priority INTEGER DEFAULT 0,
      created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS claims (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      registry_id INTEGER NOT NULL REFERENCES registries(id) ON DELETE CASCADE,
      item_id INTEGER REFERENCES registry_items(id) ON DELETE CASCADE,
      guest_name TEXT NOT NULL,
      guest_email TEXT DEFAULT '',
      message TEXT DEFAULT '',
      qty INTEGER DEFAULT 1,
      kind TEXT DEFAULT 'item',
      amount TEXT DEFAULT '',
      thanked INTEGER DEFAULT 0,
      created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS catalog_items (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      name_he TEXT DEFAULT '',
      brand TEXT DEFAULT '',
      category TEXT DEFAULT 'home',
      price_nis INTEGER DEFAULT 0,
      store TEXT DEFAULT '',
      url TEXT DEFAULT '',
      image TEXT DEFAULT '',
      active INTEGER DEFAULT 1,
      featured INTEGER DEFAULT 0,
      sort INTEGER DEFAULT 0,
      created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS bundles (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      slug TEXT UNIQUE NOT NULL,
      name TEXT NOT NULL,
      name_he TEXT DEFAULT '',
      tier TEXT DEFAULT 'basic',
      price_from INTEGER DEFAULT 0,
      description TEXT DEFAULT '',
      description_he TEXT DEFAULT '',
      items_text TEXT DEFAULT '',
      items_text_he TEXT DEFAULT '',
      active INTEGER DEFAULT 1,
      sort INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS shana_requests (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      email TEXT DEFAULT '',
      whatsapp TEXT DEFAULT '',
      arrival TEXT DEFAULT '',
      city TEXT DEFAULT '',
      address TEXT DEFAULT '',
      bundle_slug TEXT DEFAULT '',
      notes TEXT DEFAULT '',
      status TEXT DEFAULT 'new',
      created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS messages (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT DEFAULT '',
      email TEXT DEFAULT '',
      topic TEXT DEFAULT '',
      body TEXT NOT NULL,
      resolved INTEGER DEFAULT 0,
      created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS ads (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT NOT NULL,
      body TEXT DEFAULT '',
      image TEXT DEFAULT '',
      link_url TEXT DEFAULT '',
      active INTEGER DEFAULT 1,
      created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS admins (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT UNIQUE NOT NULL,
      pw_hash TEXT NOT NULL,
      created_at TEXT DEFAULT (datetime('now'))
    );
    """)
    # columns that used to be bolted on via try/except ALTER in old init_db()
    for coldef in ("stripe_url TEXT DEFAULT ''", "bit_url TEXT DEFAULT ''",
                   "views INTEGER DEFAULT 0"):
        _add_column(db, "registries", coldef)
    _add_column(db, "catalog_items", "brand TEXT DEFAULT ''")
    _add_column(db, "registry_items", "brand TEXT DEFAULT ''")


def _m002_brand_backfill(db):
    """Carried over from the old init_db(): fill catalog brand from the seed
    file, then backfill registry_items that were copied before `brand` existed."""
    seed_path = BASE / "seed_catalog.json"
    if seed_path.exists():
        seed = json.loads(seed_path.read_text(encoding="utf-8"))
        for it in seed.get("items", []):
            if it.get("brand"):
                db.execute("UPDATE catalog_items SET brand=? WHERE name=? AND brand=''",
                           (it["brand"], it["name"]))
    db.execute("""
        UPDATE registry_items SET brand = (
            SELECT brand FROM catalog_items WHERE catalog_items.id = registry_items.catalog_id
        )
        WHERE (brand IS NULL OR brand = '') AND catalog_id IS NOT NULL
    """)


def _m003_session_versioning(db):
    _add_column(db, "users", "session_ver INTEGER DEFAULT 1")
    _add_column(db, "users", "deleted_at TEXT")
    _add_column(db, "admins", "session_ver INTEGER DEFAULT 1")


def _m004_registry_visibility(db):
    _add_column(db, "registries", "visibility TEXT DEFAULT 'unlisted'")
    if has_column(db, "registries", "is_public"):
        db.execute("UPDATE registries SET visibility='public' WHERE is_public=1"
                   " AND (visibility IS NULL OR visibility='')")
        db.execute("UPDATE registries SET visibility='unlisted' WHERE is_public=0"
                   " AND (visibility IS NULL OR visibility='')")
        db.execute("UPDATE registries SET visibility='unlisted' WHERE visibility IS NULL OR visibility=''")
    for coldef in ("paypal_provider TEXT DEFAULT ''", "stripe_provider TEXT DEFAULT ''",
                   "bit_provider TEXT DEFAULT ''", "display_currency TEXT DEFAULT 'ILS'",
                   "delivery_note TEXT DEFAULT ''", "delivery_note_he TEXT DEFAULT ''",
                   "preferences_json TEXT DEFAULT '{}'"):
        _add_column(db, "registries", coldef)


def _m005_registry_items_extra(db):
    for coldef in ("archived INTEGER DEFAULT 0", "note TEXT DEFAULT ''",
                   "note_he TEXT DEFAULT ''", "variant TEXT DEFAULT ''",
                   "overrides TEXT DEFAULT ''", "kind TEXT DEFAULT 'product'"):
        _add_column(db, "registry_items", coldef)


def _m006_claims_lifecycle(db):
    for coldef in (
        "status TEXT DEFAULT 'reserved'",
        "amount_minor INTEGER",
        "currency TEXT",
        "price_snapshot_minor INTEGER",
        "price_snapshot_currency TEXT",
        "token_hash TEXT",
        "token_created_at TEXT",
        "idempotency_key TEXT",
        "expires_at TEXT",
        "reported_at TEXT",
        "confirmed_at TEXT",
        "cancelled_at TEXT",
        "cancelled_by TEXT DEFAULT ''",
        "late INTEGER DEFAULT 0",
        "legacy INTEGER DEFAULT 0",
    ):
        _add_column(db, "claims", coldef)

    # migrate pre-lifecycle rows exactly once (legacy=0 marks "not yet migrated";
    # this whole block is idempotent because it only touches legacy=0 rows and
    # sets legacy=1 at the end of each branch)
    from ob_money import parse_legacy_amount  # local import: avoid a cycle at module load

    legacy_item_rows = db.execute(
        "SELECT id FROM claims WHERE legacy=0 AND kind='item'").fetchall()
    for r in legacy_item_rows:
        db.execute("UPDATE claims SET status='reserved', legacy=1, expires_at=NULL WHERE id=?",
                   (r["id"],))

    legacy_cash_rows = db.execute(
        "SELECT id, amount FROM claims WHERE legacy=0 AND kind='cash'").fetchall()
    for r in legacy_cash_rows:
        parsed = parse_legacy_amount(r["amount"] or "")
        if parsed:
            minor, code = parsed
            db.execute(
                "UPDATE claims SET status='reported', legacy=1, amount_minor=?, currency=? WHERE id=?",
                (minor, code, r["id"]))
        else:
            db.execute("UPDATE claims SET status='reported', legacy=1 WHERE id=?", (r["id"],))


def _m007_claim_events(db):
    db.execute("""
    CREATE TABLE IF NOT EXISTS claim_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      claim_id INTEGER NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
      event TEXT NOT NULL,
      actor TEXT DEFAULT '',
      note TEXT DEFAULT '',
      created_at TEXT DEFAULT (datetime('now'))
    );
    """)


def _m008_password_resets(db):
    db.execute("""
    CREATE TABLE IF NOT EXISTS password_resets (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      token_hash TEXT NOT NULL,
      expires_at TEXT NOT NULL,
      used_at TEXT,
      created_at TEXT DEFAULT (datetime('now'))
    );
    """)


def _m009_rate_events(db):
    db.execute("""
    CREATE TABLE IF NOT EXISTS rate_events (
      bucket TEXT NOT NULL,
      key TEXT NOT NULL,
      ts REAL NOT NULL
    );
    """)


def _m010_mail_outbox(db):
    db.execute("""
    CREATE TABLE IF NOT EXISTS mail_outbox (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      to_addr TEXT NOT NULL,
      subject TEXT NOT NULL,
      body TEXT NOT NULL,
      status TEXT DEFAULT 'queued',
      attempts INTEGER DEFAULT 0,
      last_error TEXT DEFAULT '',
      next_attempt_at TEXT DEFAULT (datetime('now')),
      created_at TEXT DEFAULT (datetime('now')),
      sent_at TEXT
    );
    """)


def _m011_funnel_events(db):
    db.execute("""
    CREATE TABLE IF NOT EXISTS funnel_events (
      day TEXT NOT NULL,
      name TEXT NOT NULL,
      n INTEGER DEFAULT 0,
      PRIMARY KEY (day, name)
    );
    """)


def _m012_catalog_extra(db):
    for coldef in (
        "seed_key TEXT", "kind TEXT DEFAULT 'product'", "model TEXT DEFAULT ''",
        "variant TEXT DEFAULT ''", "image_credit TEXT DEFAULT ''",
        "price_status TEXT DEFAULT 'estimate'", "price_checked_at TEXT DEFAULT ''",
        "price_source TEXT DEFAULT ''", "availability TEXT DEFAULT 'unknown'",
        "notes TEXT DEFAULT ''", "notes_he TEXT DEFAULT ''",
        "starter_group TEXT DEFAULT ''", "clicks INTEGER DEFAULT 0",
        "updated_at TEXT",
    ):
        _add_column(db, "catalog_items", coldef)
    # one-time seed_key adoption for existing rows (by exact name), then a
    # unique index — later duplicates get a numeric suffix so the index holds
    rows = db.execute("SELECT id, name FROM catalog_items WHERE seed_key IS NULL").fetchall()
    used = {r["seed_key"] for r in db.execute(
        "SELECT seed_key FROM catalog_items WHERE seed_key IS NOT NULL")}
    for r in rows:
        base = _slugify(r["name"])
        key = base
        n = 2
        while key in used:
            key = f"{base}-{n}"
            n += 1
        used.add(key)
        db.execute("UPDATE catalog_items SET seed_key=? WHERE id=?", (key, r["id"]))
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_catalog_seed_key ON catalog_items(seed_key)")


def _m013_shana_extra(db):
    for coldef in (
        "neighborhood TEXT DEFAULT ''", "furnishing TEXT DEFAULT 'unknown'",
        "budget TEXT DEFAULT ''", "notes_internal TEXT DEFAULT ''",
        "next_action TEXT DEFAULT ''", "next_action_date TEXT DEFAULT ''",
        "quote_json TEXT DEFAULT '{}'",
    ):
        _add_column(db, "shana_requests", coldef)
    db.execute("UPDATE shana_requests SET status='completed' WHERE status='done'")


def _m015_registry_items_price_status(db):
    """Registry items copied from the catalog carry the catalog's price
    confidence forward (SPEC_V3 "Card rules": "checked 2026-07-05" vs
    "estimate"), and clicks for the /go/ handoff-click funnel."""
    for coldef in ("price_status TEXT DEFAULT 'estimate'", "price_checked_at TEXT DEFAULT ''",
                   "clicks INTEGER DEFAULT 0"):
        _add_column(db, "registry_items", coldef)
    db.execute("""
        UPDATE registry_items SET price_status = (
            SELECT price_status FROM catalog_items WHERE catalog_items.id = registry_items.catalog_id
        ), price_checked_at = (
            SELECT price_checked_at FROM catalog_items WHERE catalog_items.id = registry_items.catalog_id
        )
        WHERE catalog_id IS NOT NULL AND (price_status IS NULL OR price_status = 'estimate')
    """)


def _m016_registry_preview_flag(db):
    """`preferences_json` already exists on registries (m004) — used to store
    the dashboard checklist's visibility_reviewed_at / previewed flags. No
    schema change needed; this migration is a documented no-op placeholder so
    future readers of MIGRATIONS see the decision recorded (see PROJECT_KNOWLEDGE.md)."""
    pass


def _m017_account_deletion_index(db):
    db.execute("CREATE INDEX IF NOT EXISTS ix_users_deleted_at ON users(deleted_at)")


def _m014_indexes(db):
    db.execute("CREATE INDEX IF NOT EXISTS ix_claims_reg_item_status ON claims(registry_id, item_id, status)")
    db.execute("CREATE INDEX IF NOT EXISTS ix_claims_token_hash ON claims(token_hash)")
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_claims_idempotency ON claims(idempotency_key) WHERE idempotency_key IS NOT NULL")
    db.execute("CREATE INDEX IF NOT EXISTS ix_registry_items_reg_archived ON registry_items(registry_id, archived)")
    db.execute("CREATE INDEX IF NOT EXISTS ix_rate_events_bucket_key_ts ON rate_events(bucket, key, ts)")
    db.execute("CREATE INDEX IF NOT EXISTS ix_mail_outbox_status_next ON mail_outbox(status, next_attempt_at)")
    db.execute("CREATE INDEX IF NOT EXISTS ix_catalog_active_cat_sort ON catalog_items(active, category, sort)")


# ------------------------------------------------------------------ catalog seed sync
# Metadata columns that "adoption" (matching a legacy no-seed_key row by exact
# name) is allowed to fill in — ONLY when the DB row still holds the column's
# schema default, so a manual admin edit is never clobbered. Never includes
# name/price/url/store/brand/active/featured — those are the couple/admin's.
_ADOPT_FIELDS = {
    "kind": "product",
    "starter_group": "",
    "price_status": "estimate",
    "price_checked_at": "",
    "price_source": "",
}


def seed_sync(db, seed_items, dry_run=False):
    """Sync `catalog_items` from the seed file's items (each with a stable
    `seed_key`). Three cases per seed row:
      1. seed_key already present in DB -> untouched (admin owns it now).
      2. No row has this seed_key, but a legacy row (seed_key IS NULL) has an
         exact name match -> "adopt": set its seed_key, and fill ONLY the
         metadata fields in _ADOPT_FIELDS that are still at their default.
         Never touches name/price/url/store/brand/active/featured.
      3. No row has this seed_key and no legacy name match -> INSERT a new
         row (including featured/starter_group, so a fresh install gets a
         working starter pack).
    Retired items (active=0) are matched by seed_key like any other row, so
    they are never re-inserted. Returns a dict of counters."""
    counters = dict(adopted=0, inserted=0, unchanged=0)
    have_keys = {r["seed_key"] for r in
                 db.execute("SELECT seed_key FROM catalog_items WHERE seed_key IS NOT NULL")}
    legacy_by_name = {r["name"]: r["id"] for r in
                      db.execute("SELECT id, name FROM catalog_items WHERE seed_key IS NULL")}
    for i, it in enumerate(seed_items):
        key = it["seed_key"]
        if key in have_keys:
            counters["unchanged"] += 1
            continue
        legacy_id = legacy_by_name.get(it["name"])
        if legacy_id is not None:
            counters["adopted"] += 1
            if dry_run:
                continue
            row = db.execute("SELECT * FROM catalog_items WHERE id=?", (legacy_id,)).fetchone()
            sets, params = ["seed_key=?"], [key]
            for field, default in _ADOPT_FIELDS.items():
                if field in row.keys() and row[field] == default and field in it:
                    sets.append(f"{field}=?")
                    params.append(it[field])
            params.append(legacy_id)
            db.execute(f"UPDATE catalog_items SET {', '.join(sets)} WHERE id=?", params)
        else:
            counters["inserted"] += 1
            if dry_run:
                continue
            db.execute(
                "INSERT INTO catalog_items (name, name_he, brand, category, price_nis, store,"
                " url, sort, seed_key, kind, featured, starter_group, price_status,"
                " price_checked_at, price_source) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (it["name"], it.get("name_he", ""), it.get("brand", ""),
                 it.get("category", "home"), it.get("price_nis", 0), it.get("store", ""),
                 it.get("url", ""), i, key, it.get("kind", "product"),
                 1 if it.get("featured") else 0, it.get("starter_group", ""),
                 it.get("price_status", "estimate"), it.get("price_checked_at", ""),
                 it.get("price_source", "")))
    return counters


def seed_overwrite(db, seed_items, fields, dry_run=False):
    """Explicit admin-requested overwrite: for each seed item with a matching
    seed_key in the DB, set `fields` (a list like ['price_nis','url']) from
    the seed value if different. Returns a list of (seed_key, name, field,
    old, new) diff rows (always computed, even in dry-run)."""
    diffs = []
    by_key = {it["seed_key"]: it for it in seed_items if it.get("seed_key")}
    for row in db.execute("SELECT * FROM catalog_items WHERE seed_key IS NOT NULL"):
        it = by_key.get(row["seed_key"])
        if not it:
            continue
        sets, params = [], []
        for field in fields:
            if field not in it:
                continue
            new_val = it[field]
            old_val = row[field] if field in row.keys() else None
            if old_val != new_val:
                diffs.append((row["seed_key"], row["name"], field, old_val, new_val))
                sets.append(f"{field}=?")
                params.append(new_val)
        if sets and not dry_run:
            params.append(row["id"])
            db.execute(f"UPDATE catalog_items SET {', '.join(sets)} WHERE id=?", params)
    return diffs


def refresh_registry_links(db, dry_run=False):
    """Copy url/image/store/brand from catalog_items onto registry_items that
    came from the catalog (catalog_id set), for any of those fields the
    couple has NOT overridden (registry_items.overrides is a comma list).
    Never touches name/price/qty/priority/note or any claim. Returns a list
    of (registry_item_id, field, old, new) diff rows."""
    diffs = []
    fields = ("url", "image", "store", "brand")
    rows = db.execute(
        "SELECT ri.*, c.url AS c_url, c.image AS c_image, c.store AS c_store,"
        " c.brand AS c_brand FROM registry_items ri"
        " JOIN catalog_items c ON c.id = ri.catalog_id"
        " WHERE ri.archived=0").fetchall()
    for row in rows:
        overrides = set(f for f in (row["overrides"] or "").split(",") if f)
        sets, params = [], []
        for field in fields:
            if field in overrides:
                continue
            old_val = row[field]
            new_val = row["c_" + field]
            if old_val != new_val:
                diffs.append((row["id"], field, old_val, new_val))
                sets.append(f"{field}=?")
                params.append(new_val)
        if sets and not dry_run:
            params.append(row["id"])
            db.execute(f"UPDATE registry_items SET {', '.join(sets)} WHERE id=?", params)
    return diffs


def bundle_sync(db, bundles):
    """Unchanged behaviour from Phase 1: insert bundles that aren't there yet
    (matched by slug), never overwrite an existing one."""
    for i, b in enumerate(bundles):
        db.execute(
            "INSERT OR IGNORE INTO bundles (slug, name, name_he, tier, price_from,"
            " description, description_he, items_text, items_text_he, sort)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (b["slug"], b["name"], b.get("name_he", ""), b.get("tier", "basic"),
             b.get("price_from", 0), b.get("description", ""), b.get("description_he", ""),
             b.get("items_text", ""), b.get("items_text_he", ""), i))


MIGRATIONS = [
    _m001_initial_schema,
    _m002_brand_backfill,
    _m003_session_versioning,
    _m004_registry_visibility,
    _m005_registry_items_extra,
    _m006_claims_lifecycle,
    _m007_claim_events,
    _m008_password_resets,
    _m009_rate_events,
    _m010_mail_outbox,
    _m011_funnel_events,
    _m012_catalog_extra,
    _m013_shana_extra,
    _m014_indexes,
    _m015_registry_items_price_status,
    _m016_registry_preview_flag,
    _m017_account_deletion_index,
]


def pending_migrations(db):
    """Versions not yet applied — read-only (no table creation), for `manage.py check`."""
    have = db.execute("SELECT 1 FROM sqlite_master WHERE name='schema_migrations'").fetchone()
    applied = {r[0] for r in db.execute("SELECT version FROM schema_migrations")} if have else set()
    return [i for i in range(1, len(MIGRATIONS) + 1) if i not in applied]


def migrate(db):
    """Apply every migration not yet recorded in schema_migrations, in order,
    each in its own transaction so a failure part-way doesn't mark it applied."""
    db.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
          version INTEGER PRIMARY KEY,
          applied_at TEXT DEFAULT (datetime('now'))
        )
    """)
    applied = {r[0] for r in db.execute("SELECT version FROM schema_migrations")}
    for i, fn in enumerate(MIGRATIONS, start=1):
        if i in applied:
            continue
        with write_txn(db):
            fn(db)
            db.execute("INSERT INTO schema_migrations (version) VALUES (?)", (i,))


# ------------------------------------------------------------------ write_txn
@contextlib.contextmanager
def write_txn(db, retries=5, delay=0.2):
    """BEGIN IMMEDIATE ... COMMIT, retrying on SQLITE_BUSY/locked a few times
    with a short sleep. Rolls back on any exception. Connections opened via
    connect() use isolation_level=None (autocommit) so this is the only place
    multi-statement writes should happen.

    Reentrant: if a write_txn is already open on this connection (e.g. a route
    calls track() while inside its own write_txn), this becomes a no-op that
    just yields — only the outermost call manages BEGIN/COMMIT/ROLLBACK."""
    if db.in_transaction:
        yield db
        return
    attempt = 0
    while True:
        try:
            db.execute("BEGIN IMMEDIATE")
            break
        except sqlite3.OperationalError as e:
            msg = str(e).lower()
            if ("locked" in msg or "busy" in msg) and attempt < retries:
                attempt += 1
                time.sleep(delay * attempt)
                continue
            raise
    try:
        yield db
    except Exception:
        db.execute("ROLLBACK")
        raise
    else:
        db.execute("COMMIT")


# ------------------------------------------------------------------ backup
def backup(src_path, dst_path):
    """Online backup via sqlite3's Connection.backup(), then verify the copy
    with PRAGMA integrity_check. Raises RuntimeError if the copy isn't clean."""
    src = sqlite3.connect(str(src_path))
    try:
        Path(dst_path).parent.mkdir(parents=True, exist_ok=True)
        dst = sqlite3.connect(str(dst_path))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    check = sqlite3.connect(str(dst_path))
    try:
        result = check.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        check.close()
    if result != "ok":
        raise RuntimeError(f"backup integrity check failed: {result}")
    return dst_path
