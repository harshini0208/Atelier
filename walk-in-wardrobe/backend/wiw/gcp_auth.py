"""Google credentials: Application Default Credentials, falling back to the local gcloud user token.

On Cloud Run, ADC resolves to the wiw-run service account. Locally, if `gcloud auth application-default
login` has not been run, we borrow the gcloud CLI's user token (refreshed on demand) so live mode and the
cloud loaders work without extra setup.
"""
from __future__ import annotations

import datetime as dt
import shutil
import subprocess
from functools import lru_cache

import google.auth
import google.auth.transport.requests
from google.auth import credentials as ga_credentials
from google.auth.exceptions import DefaultCredentialsError, RefreshError

from .settings import get_settings

SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


class GcloudUserCredentials(ga_credentials.Credentials):
    def __init__(self, quota_project: str) -> None:
        super().__init__()
        self._quota_project_id = quota_project

    @property
    def quota_project_id(self) -> str:  # type: ignore[override]
        return self._quota_project_id

    def refresh(self, request) -> None:  # noqa: ANN001
        out = subprocess.run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True, check=True)
        self.token = out.stdout.strip().splitlines()[-1]
        self.expiry = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) + dt.timedelta(minutes=45)

    def apply(self, headers, token=None) -> None:  # noqa: ANN001
        super().apply(headers, token)
        headers["x-goog-user-project"] = self._quota_project_id


@lru_cache(maxsize=1)
def credentials() -> ga_credentials.Credentials:
    project = get_settings().project
    try:
        creds, _ = google.auth.default(scopes=SCOPES)
        # user credentials need a quota project; service accounts (Cloud Run) must NOT send one, or every call
        # requires serviceusage.services.use on the project
        if hasattr(creds, "with_quota_project") and getattr(creds, "refresh_token", None):
            creds = creds.with_quota_project(project)
        creds.refresh(google.auth.transport.requests.Request())  # stale ADC files fail here, not later
        return creds
    except (DefaultCredentialsError, RefreshError):
        if shutil.which("gcloud") is None:
            raise
        return GcloudUserCredentials(project)
