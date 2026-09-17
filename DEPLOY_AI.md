# Deploying OurBayis to PythonAnywhere

Mirrors the BashertBench setup (same host, same pattern). Free tier works to start; upgrade to a paid plan when you're ready for a custom domain (needed for Amazon Associates approval and to look credible to couples).

## 1. Get the code onto PythonAnywhere
In a PythonAnywhere **Bash console**:
```bash
git clone <your-repo-url> ourbayis      # if the code is in git
# — or —
# upload the OurBayis folder via the Files tab if it isn't in git yet
```
If it's not in git yet, that's worth doing first (even just `git init` + a private GitHub repo) — makes future updates a `git pull` instead of re-uploading files.

## 2. Create a virtualenv and install dependencies
```bash
cd ~/ourbayis
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 3. Create the web app
PythonAnywhere dashboard → **Web** tab → **Add a new web app** → choose **Manual configuration** (not the Flask template — we already have our own WSGI setup) → pick the same Python version as your venv.

## 4. Point it at the code
- **Virtualenv** field: `/home/YOURUSERNAME/ourbayis/venv`
- **WSGI configuration file**: click it, delete everything, paste in the contents of [`passenger_wsgi.py`](passenger_wsgi.py) from this repo — but:
  - fix `project_home` to your real path (`/home/YOURUSERNAME/ourbayis`)
  - replace `OB_SECRET_KEY` with a real random value — generate one locally with `python -c "import secrets; print(secrets.token_hex(32))"` and paste the result in, don't leave the placeholder
  - uncomment and fill in the SMTP lines if you want email notifications (a Gmail **app password**, not your normal password, works well)
- **Static files** section: add a mapping
  - URL: `/static/`
  - Directory: `/home/YOURUSERNAME/ourbayis/static/`

## 5. Reload and check
Click the big green **Reload** button, then open the app's `*.pythonanywhere.com` URL. Check the **Error log** and **Server log** links on the Web tab if anything 500s — importing `app.py` also runs migrations + catalog seed-sync, so the SQLite file, its schema, and its 117 catalog items get created automatically on first load; no manual DB step needed (but you do still need step 5b to create an admin).

## 5b. Create the first admin (v3+, no default admin)
There's no default `admin/changeme123` anymore. In a Bash console, from the project directory with the venv active:
```bash
python manage.py create-admin youradminname
```
It prompts for a password (12+ chars), or set `OB_ADMIN_PASSWORD` in the environment first to script it. `/admin/login` shows a reminder of this command when zero admins exist.

## 6. Before telling anyone the link
- [ ] Created an admin (see 5b) and logged into `/admin/login`.
- [ ] Go through `/admin/catalog` and paste in real affiliate URLs (see the earlier conversation on Amazon Associates + Payoneer) — items without one show no "buy" button.
- [ ] Spot-check a few more catalog prices against real stores (8 big-ticket items are verified as of 2026-07-03; see CHANGELOG_AI.md — the rest are AI estimates).
- [ ] Set `OB_BASE_URL` in `passenger_wsgi.py` to the real domain (used in every email/sitemap link).
- [ ] If the domain is fixed, set `OB_ALLOWED_HOSTS` too, so stray Host headers get a 400 instead of serving.

## Scheduled tasks (PythonAnywhere "Tasks" tab)
v3 phase 1 adds a mail outbox and a claim-expiry sweep; neither runs itself without SMTP configured
or a scheduled task. All commands assume the venv is active (`source venv/bin/activate`) or you
call `venv/bin/python` directly, from `~/ourbayis`:
```bash
# once a day (or more often), only useful once OB_SMTP_* is set:
cd ~/ourbayis && venv/bin/python manage.py send-mail

# once a day: flips reservations past their 14-day hold to 'expired'
cd ~/ourbayis && venv/bin/python manage.py expire-claims

# weekly, before any deploy that touches the schema, or just as a habit:
cd ~/ourbayis && venv/bin/python manage.py backup
```
`manage.py check` is worth running after any deploy — it checks DB integrity, foreign keys, that at least one admin exists, and secret-key/cookie config sanity; exits 1 if anything's wrong.

### Catalog maintenance commands (v3 phase 3, run manually — not scheduled)
```bash
# after editing seed_catalog.json: adopt/insert new items, never overwrites existing DB rows
cd ~/ourbayis && venv/bin/python manage.py seed-sync            # dry run, prints a diff table
cd ~/ourbayis && venv/bin/python manage.py seed-sync --apply    # actually writes

# explicit overwrite of specific fields from the seed by seed_key (dry run by default)
cd ~/ourbayis && venv/bin/python manage.py seed-sync --fields price_nis,url --apply

# after editing catalog items in /admin/catalog: push url/image/store/brand/model/notes and the
# stock flag (availability) out to registry_items that came from the catalog; fields the couple
# edited themselves are skipped (availability is always refreshed); claims are never touched
# daily: refresh the ≈ conversion rates (ECB reference rates via frankfurter.app, no key needed);
# writes instance/rates.json, the web app re-reads it on the next request — no Reload needed
cd ~/ourbayis && venv/bin/python manage.py fetch-rates

cd ~/ourbayis && venv/bin/python manage.py refresh-registry-links           # dry run
cd ~/ourbayis && venv/bin/python manage.py refresh-registry-links --apply
```
The web app also runs `seed_sync()`/`bundle_sync()` automatically on every import (i.e. every
`Reload`), so a `seed_catalog.json` edit that only *adds new items* (new `seed_key`s) needs no
manual command at all — reload the web app and it's picked up. The `--fields`/`--apply` commands
above are only for the two cases the app never does on its own: overwriting an existing row's
value from the seed, and pushing catalog edits out to registries.

## Backup / restore
- **Backup**: `python manage.py backup` writes a verified online copy (via SQLite's own backup API + `PRAGMA integrity_check`) to `backups/ourbayis-<timestamp>.db`. `backups/` is gitignored — download copies off the server periodically. An admin can also download one on demand from `/admin/backup.db` (streamed, deleted from the server immediately after).
- **Restore**: stop the web app (or at least don't rely on it not writing), copy the backup file over `ourbayis.db` (or point `OB_DB_PATH` at it), then `python manage.py check` before reloading.
- **2026-09-17 deploy note**: migration 18 (`registry_items.model/availability/notes/notes_he`) applies
  itself on the first import after deploy and backfills from the catalog. Run
  `manage.py refresh-registry-links` (dry run, then `--apply`) afterwards so existing registries pick up
  the stock flags, and edit the three bundles in `/admin/bundles` to the new wording (bundle sync is
  insert-only). New public route: `/sample` (in the sitemap).
- **Rollback after a bad migration/deploy**: restore the most recent `backups/ourbayis-*.db` copy from *before* the deploy (see above), `git checkout` (or re-upload) the previous commit's code, `python manage.py check`, then Reload. Migrations in `ob_db.py` are additive and idempotent (`ALTER TABLE ... ADD COLUMN`, `CREATE TABLE IF NOT EXISTS`) — there is no automatic down-migration, so a schema rollback always means restoring a pre-deploy DB backup, never rolling the schema back in place.

## 7. Custom domain (when ready)
PythonAnywhere requires a **paid plan** for custom domains (same tier BashertBench is on). Once upgraded: Web tab → add the domain → PythonAnywhere gives you a CNAME/A record to set at your domain registrar → **Force HTTPS** once the cert issues.

## Updating the live site later
```bash
cd ~/ourbayis
git pull            # or re-upload changed files
source venv/bin/activate
pip install -r requirements.txt   # only if requirements.txt changed
```
Then **Reload** the web app from the Web tab — that's it, no restart command needed.

## A note on the SQLite file
`ourbayis.db` lives next to `app.py` and is created automatically. **Back it up before any deploy that touches the schema** — PythonAnywhere's Files tab lets you download it directly, or `cp ourbayis.db ourbayis.db.bak` in a console. It holds every couple's registry and every guest claim, so treat it like the real data it is.
