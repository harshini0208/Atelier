"""Generate all synthetic data and load it into the configured backends (local SQLite + media by default).

    python scripts/seed.py            # local
    DB_BACKEND=cloudsql STORAGE_BACKEND=gcs python scripts/seed.py   # (use `make load-cloud` instead)
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def main() -> None:
    subprocess.run([sys.executable, str(ROOT / "data/generate.py")], check=True)
    if not (ROOT / "demo/inspo/generated/truth.json").exists():
        subprocess.run([sys.executable, str(ROOT / "scripts/make_inspo.py")], check=True)
    from wiw.seed import seed_all

    has = lambda mod: importlib.util.find_spec(f"wiw.{mod}") is not None  # noqa: E731
    out = seed_all(with_inspo=has("seed_inspo"), with_history=has("seed_history"))
    print(f"seeded: {out}")


if __name__ == "__main__":
    main()
