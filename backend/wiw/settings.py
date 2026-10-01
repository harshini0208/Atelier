"""Runtime settings: env vars select local vs cloud backends; resource names come from config/cloud.yaml."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv() -> None:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.split("#", 1)[0].strip())


_load_dotenv()


class Settings:
    def __init__(self) -> None:
        cloud = yaml.safe_load((ROOT / "config/cloud.yaml").read_text())
        self.cloud = cloud
        self.project = os.getenv("GCP_PROJECT", cloud["project"])
        self.region = cloud["region"]
        self.gemini_mode = os.getenv("GEMINI_MODE", "replay").lower()
        self.gemini_model = os.getenv("GEMINI_MODEL", cloud["gemini"]["model"])
        self.gemini_location = os.getenv("GEMINI_LOCATION", cloud["gemini"]["location"])
        self.db_backend = os.getenv("DB_BACKEND", "sqlite")
        self.sqlite_path = Path(os.getenv("SQLITE_PATH", str(ROOT / "local/wiw.db")))
        self.storage_backend = os.getenv("STORAGE_BACKEND", "local")
        self.events_backend = os.getenv("EVENTS_BACKEND", "local")
        self.search_backend = os.getenv("SEARCH_BACKEND", "local")
        self.media_dir = Path(os.getenv("MEDIA_DIR", str(ROOT / "local/media")))
        self.cache_dir = Path(os.getenv("GEMINI_CACHE_DIR", str(ROOT / "cache/gemini")))
        self.bucket = cloud["bucket"]
        self.bq_dataset = cloud["bq_dataset"]
        self.bq_location = cloud["bq_location"]
        self.sql = cloud["cloudsql"]
        self.search = cloud["search"]
        self.frontend_dist = ROOT / "frontend/dist"
        self.matching = yaml.safe_load((ROOT / "config/matching.yaml").read_text())

    @property
    def cloudsql_connection_name(self) -> str:
        return f"{self.project}:{self.region}:{self.sql['instance']}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
