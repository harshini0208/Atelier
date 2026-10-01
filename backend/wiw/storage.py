"""Media storage: a local folder or a private Cloud Storage bucket. The API serves both at /media/<path>."""
from __future__ import annotations

import mimetypes
from functools import lru_cache
from typing import Protocol

from .settings import get_settings

mimetypes.add_type("image/svg+xml", ".svg")


class Storage(Protocol):
    def put(self, path: str, data: bytes, content_type: str | None = None) -> str: ...
    def get(self, path: str) -> bytes | None: ...
    def exists(self, path: str) -> bool: ...
    def delete_prefix(self, prefix: str) -> int: ...


def url_for(path: str) -> str:
    return f"/media/{path}"


def content_type(path: str) -> str:
    return mimetypes.guess_type(path)[0] or "application/octet-stream"


class LocalStorage:
    def __init__(self) -> None:
        self.root = get_settings().media_dir
        self.root.mkdir(parents=True, exist_ok=True)

    def _p(self, path: str):  # noqa: ANN202
        p = (self.root / path).resolve()
        if self.root.resolve() not in p.parents:
            raise ValueError("path escapes media root")
        return p

    def put(self, path: str, data: bytes, content_type: str | None = None) -> str:
        p = self._p(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return url_for(path)

    def get(self, path: str) -> bytes | None:
        try:
            p = self._p(path)
        except ValueError:
            return None
        return p.read_bytes() if p.is_file() else None

    def exists(self, path: str) -> bool:
        return self._p(path).is_file()

    def delete_prefix(self, prefix: str) -> int:
        import shutil

        d = self._p(prefix.rstrip("/"))
        n = sum(1 for f in d.rglob("*") if f.is_file()) if d.is_dir() else 0
        shutil.rmtree(d, ignore_errors=True)
        return n


class GcsStorage:
    def __init__(self) -> None:
        from google.cloud import storage as gcs

        from .gcp_auth import credentials

        s = get_settings()
        self.bucket = gcs.Client(project=s.project, credentials=credentials()).bucket(s.bucket)
        self._cache: dict[str, bytes] = {}

    def put(self, path: str, data: bytes, content_type: str | None = None) -> str:
        blob = self.bucket.blob(path)
        blob.cache_control = "public, max-age=3600"
        blob.upload_from_string(data, content_type=content_type or globals()["content_type"](path))
        self._cache[path] = data
        return url_for(path)

    def get(self, path: str) -> bytes | None:
        if path in self._cache:
            return self._cache[path]
        blob = self.bucket.blob(path)
        try:
            data = blob.download_as_bytes()
        except Exception:  # noqa: BLE001  (NotFound and transient errors both mean "not available")
            return None
        if len(self._cache) < 2000:
            self._cache[path] = data
        return data

    def exists(self, path: str) -> bool:
        return path in self._cache or self.bucket.blob(path).exists()

    def delete_prefix(self, prefix: str) -> int:
        blobs = list(self.bucket.list_blobs(prefix=prefix))
        for b in blobs:
            b.delete()
            self._cache.pop(b.name, None)
        return len(blobs)


@lru_cache(maxsize=1)
def storage() -> Storage:
    return GcsStorage() if get_settings().storage_backend == "gcs" else LocalStorage()
