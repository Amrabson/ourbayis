"""Dev-server wrapper: sets env vars for the Browser-tool preview since
.claude/launch.json's runtimeArgs don't support inline env on this setup."""
import os

os.environ.setdefault("OB_DB_PATH", r"C:\Users\aharo\AppData\Local\Temp\ourbayis-dev.db")
os.environ.setdefault("OB_SECRET_KEY", "dev-phase2-key")

import app  # noqa: E402

if __name__ == "__main__":
    app.app.run(host="127.0.0.1", port=5001, debug=False)
