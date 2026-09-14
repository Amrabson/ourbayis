# OurBayis

Gift registry for couples building a home in Israel — bilingual (English / Hebrew), built for
guests abroad. Couples pick what an Israeli home actually needs; guests buy from a linked Israeli
store or send money directly to the couple. OurBayis never holds gift money.

Flask 3 + SQLite + Jinja2, no build step. See `PROJECT_KNOWLEDGE.md` for the architecture and
`SPEC_V3.md` for the design decisions.

## Static preview (GitHub Pages)
`docs/` is a read-only export of the public pages with a synthetic sample registry — forms and
gifting are disabled there. Enable Pages on this repo (Settings → Pages → Deploy from branch →
`/docs`) to share it. Regenerate after changes:

```bash
python tools/export_static.py
```

## Run it for real
```bash
pip install -r requirements.txt
python manage.py create-admin admin      # there is no default admin
python app.py                            # http://127.0.0.1:5001
```
`python -m pytest -q` runs the test suite on a temporary database. Deployment (PythonAnywhere)
is documented in `DEPLOY_AI.md`. The SQLite file `ourbayis.db` is gitignored — never commit it.
