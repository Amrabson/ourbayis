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
Click the big green **Reload** button, then open the app's `*.pythonanywhere.com` URL. Check the **Error log** and **Server log** links on the Web tab if anything 500s — importing `app.py` also runs `init_db()`, so the SQLite file and its 117 catalog items get created automatically on first load; no manual DB step needed.

## 6. Before telling anyone the link
- [ ] Log into `/admin/login` (admin / changeme123) and **change the password** immediately — it's the same default in every fresh install.
- [ ] Go through `/admin/catalog` and paste in real affiliate URLs (see the earlier conversation on Amazon Associates + Payoneer) — items without one show no "buy" button.
- [ ] Spot-check a few more catalog prices against real stores (8 big-ticket items are verified as of 2026-07-03; see CHANGELOG_AI.md — the rest are AI estimates).

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
