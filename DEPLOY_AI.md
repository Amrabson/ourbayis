# Deploying OurBayis to PythonAnywhere

> **This account also hosts BashertBench (live).** The PythonAnywhere username is `bashertbench`, so
> `/home/bashertbench` is the home folder *and* BashertBench's site — its `app.py`, `static/` and
> `templates/` sit loose there. OurBayis must live only in its own subfolder, **`/home/bashertbench/ourbayis`**. Every path
> below is written out in full; don't shorten to `~/`, and never unzip or clone OurBayis into the home
> folder itself. A second web app needs a plan with room for it — check the Web tab shows
> "Add a new web app" before starting.

Mirrors the BashertBench setup (same host, same pattern). Free tier works to start; upgrade to a paid plan when you're ready for a custom domain (needed for Amazon Associates approval and to look credible to couples).

## 1. Get the code onto PythonAnywhere
In a PythonAnywhere **Bash console**:
```bash
cd /home/bashertbench
git clone <your-repo-url> ourbayis      # if the code is in git -> creates /home/bashertbench/ourbayis
# — or —
# upload the OurBayis folder via the Files tab into /home/bashertbench/ourbayis (create that folder first)
```
If it's not in git yet, that's worth doing first (even just `git init` + a private GitHub repo) — makes future updates a `git pull` instead of re-uploading files.

## 2. Create a virtualenv and install dependencies
```bash
cd /home/bashertbench/ourbayis
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 3. Create the web app
PythonAnywhere dashboard → **Web** tab → **Add a new web app** → choose **Manual configuration** (not the Flask template — we already have our own WSGI setup) → pick the same Python version as your venv.

## 4. Point it at the code
- **Virtualenv** field: `/home/bashertbench/ourbayis/venv`
- **WSGI configuration file**: click it, delete everything, paste in the contents of [`passenger_wsgi.py`](passenger_wsgi.py) from this repo — but:
  - fix `project_home` to your real path (`/home/bashertbench/ourbayis`)
  - replace `OB_SECRET_KEY` with a real random value — generate one locally with `python -c "import secrets; print(secrets.token_hex(32))"` and paste the result in, don't leave the placeholder
  - put email (SMTP) settings in `instance/ob.env`, not here — see **4b** below, so the scheduled tasks get them too
- **Static files** section: add a mapping
  - URL: `/static/`
  - Directory: `/home/bashertbench/ourbayis/static/`

## 4b. Email (SMTP) — `instance/ob.env`
Without this, password-reset links, guest "save this link" emails, reminders and lead
notifications are queued in `mail_outbox` but never sent. Settings go in one private file that
the web app **and** `manage.py` (scheduled tasks) both read:

1. **Gmail app password** — on the Google account that will send the mail: turn on
   2-Step Verification, then open https://myaccount.google.com/apppasswords, create one
   named "OurBayis", and copy the 16-letter code (your normal Gmail password will not work).
2. **Create the file** — in the PythonAnywhere Files tab, open the project folder, then the
   `instance` folder (create it if missing), and add a new file `ob.env`. Paste the contents of
   [`ob.env.example`](ob.env.example) and fill in your address, the app password, your domain
   (`OB_BASE_URL`) and where leads should go (`OB_NOTIFY_EMAIL`). `instance/` is gitignored, so
   the password never goes into git.
3. **Test it** — Bash console in the project folder, venv active:
   `python manage.py test-mail you@gmail.com` → prints `Sent to …`, or the exact SMTP error
   (`SMTPAuthenticationError` = wrong app password / 2-Step not on).
4. **Reload** the web app (Web tab) so the site picks up the file, and add the `send-mail`
   scheduled task below so anything that failed to send is retried.

Gmail allows roughly 500 messages a day, plenty for launch. For mail from your own domain
later (e.g. hello@ourbayis.com), a provider like Zoho Mail works the same way (host
`smtp.zoho.com`, port 465) — check that your plan includes SMTP access; free tiers often do not.

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
or a scheduled task. Paste each command into the Tasks tab exactly as written — full paths, so they
work from anywhere (manage.py finds the database and `instance/ob.env` next to itself):
```bash
# once a day (or more often), only useful once OB_SMTP_* is set:
/home/bashertbench/ourbayis/venv/bin/python /home/bashertbench/ourbayis/manage.py send-mail

# once a day: flips reservations past their 14-day hold to 'expired'
/home/bashertbench/ourbayis/venv/bin/python /home/bashertbench/ourbayis/manage.py expire-claims

# weekly, before any deploy that touches the schema, or just as a habit
# (keeps the newest 14 copies in backups/ and deletes older ones; --keep N to change, 0 = keep all):
/home/bashertbench/ourbayis/venv/bin/python /home/bashertbench/ourbayis/manage.py backup
```
`manage.py check` is worth running after any deploy — it checks DB integrity, foreign keys, that at least one admin exists, and secret-key/cookie config sanity; exits 1 if anything's wrong (including email half set up). It also prints WARNING lines for settings that fail quietly: email off, `OB_BASE_URL` / `OB_NOTIFY_EMAIL` missing, failed emails in the outbox, stale exchange rates. Read them before going live.

### Catalog maintenance commands (v3 phase 3, run manually — not scheduled)
```bash
# after editing seed_catalog.json: adopt/insert new items, never overwrites existing DB rows
/home/bashertbench/ourbayis/venv/bin/python /home/bashertbench/ourbayis/manage.py seed-sync            # dry run, prints a diff table
/home/bashertbench/ourbayis/venv/bin/python /home/bashertbench/ourbayis/manage.py seed-sync --apply    # actually writes

# explicit overwrite of specific fields from the seed by seed_key (dry run by default)
/home/bashertbench/ourbayis/venv/bin/python /home/bashertbench/ourbayis/manage.py seed-sync --fields price_nis,url --apply

# after editing catalog items in /admin/catalog: push url/image/store/brand/model/notes and the
# stock flag (availability) out to registry_items that came from the catalog; fields the couple
# edited themselves are skipped (availability is always refreshed); claims are never touched
# daily, after expire-claims: one bilingual nudge to guests who reserved 5+ days ago with an
# email and haven't reported; never sends twice (claims.reminded_at). Needs SMTP to actually go out.
/home/bashertbench/ourbayis/venv/bin/python /home/bashertbench/ourbayis/manage.py remind-claims

# daily: refresh the ≈ conversion rates (ECB reference rates via frankfurter.app, no key needed);
# writes instance/rates.json, the web app re-reads it on the next request — no Reload needed
/home/bashertbench/ourbayis/venv/bin/python /home/bashertbench/ourbayis/manage.py fetch-rates

/home/bashertbench/ourbayis/venv/bin/python /home/bashertbench/ourbayis/manage.py refresh-registry-links           # dry run
/home/bashertbench/ourbayis/venv/bin/python /home/bashertbench/ourbayis/manage.py refresh-registry-links --apply
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
cd /home/bashertbench/ourbayis
git pull            # or re-upload changed files
source venv/bin/activate
pip install -r requirements.txt   # only if requirements.txt changed
```
Then **Reload** the web app from the Web tab — that's it, no restart command needed.

## A note on the SQLite file
`ourbayis.db` lives next to `app.py` and is created automatically. **Back it up before any deploy that touches the schema** — PythonAnywhere's Files tab lets you download it directly, or `cp ourbayis.db ourbayis.db.bak` in a console. It holds every couple's registry and every guest claim, so treat it like the real data it is.
