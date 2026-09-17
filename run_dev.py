"""Dev-server wrapper for the Browser-tool preview (.claude/launch.json).

Forces a throwaway database in %TEMP% so the preview can never touch the
repo's ourbayis.db, whatever the pane's environment contains."""
import os

os.environ["OB_DB_PATH"] = r"C:\Users\aharo\AppData\Local\Temp\ourbayis-dev.db"
os.environ.setdefault("OB_SECRET_KEY", "dev-only-key")
os.environ.setdefault("OB_RATES", '{"USD":3.7}')
os.environ.setdefault("OB_RATES_DATE", "2026-09-01")

import app  # noqa: E402

if __name__ == "__main__":
    app.app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.app.run(host="127.0.0.1", port=5001, debug=False)
