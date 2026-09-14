# CLAUDE.md

Read `PROJECT_KNOWLEDGE.md` first — it explains the architecture, money model, and flows. Don't re-scan the repo.

Rules:
- Keep PROJECT_KNOWLEDGE.md, CHANGELOG_AI.md and TODO_AI.md updated with every change.
- All public-facing text must exist in both `T_EN` and `T_HE` in i18n.py; bilingual DB fields use the `*_he` suffix and the `pick()` helper.
- Write "Shabbos", never "Shabbat", in English content.
- The site must never process payments (owner can't use Stripe). Cash gifts = couple's own PayPal link; store gifts = external store links.
- No build step, no new dependencies without a strong reason. Single-file app.py, server-rendered Jinja2.
- Local run: `python app.py` → http://127.0.0.1:5001 (admin: /admin/login)
