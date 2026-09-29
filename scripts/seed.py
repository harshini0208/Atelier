"""Start fresh: delete ALL shopper data and load the store catalog (local SQLite + media by default).

    python scripts/seed.py            # local
    DB_BACKEND=cloudsql STORAGE_BACKEND=gcs python scripts/seed.py   # (use `make load-cloud` instead)
"""
from __future__ import annotations

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

    out = seed_all()
    print(f"seeded: {out}")


if __name__ == "__main__":
    main()
