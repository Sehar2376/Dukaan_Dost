# Entry point for Vercel: it looks for `app` in app.py at the project root.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "backend"))

from main import app  # noqa: E402,F401
