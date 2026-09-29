import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))
# Tests never touch the network or the developer's local DB.
os.environ["GEMINI_MODE"] = "off"
os.environ["DB_BACKEND"] = "sqlite"
os.environ["STORAGE_BACKEND"] = "local"
os.environ["EVENTS_BACKEND"] = "local"
os.environ["SEARCH_BACKEND"] = "local"
_TMP = Path(os.environ.get("PYTEST_TMP", "/tmp")) / f"wiw-test-{os.getpid()}"
os.environ["SQLITE_PATH"] = str(_TMP / "test.db")
os.environ["MEDIA_DIR"] = str(_TMP / "media")
