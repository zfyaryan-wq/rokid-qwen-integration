import asyncio
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import PurePath
from uuid import uuid4

import httpx
from obs import ObsClient

from .config import Settings


@dataclass(frozen=True)
class ObsCredentials:
    access_key: str
    secret_key: str
    security_token: str = ""


@dataclass(frozen=True)
class SignedUpload:
    url: str
    headers: dict[str, str]


class HuaweiObsSigner:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._cached_credentials: ObsCredentials | None = None
        self._credentials_refresh_at = datetime.min.replace(tzinfo=timezone.utc)
        self._credential_lock = asyncio.Lock()

    async def sign_put(self, object_key: str, content_type: str) -> SignedUpload:
        if not self.settings.obs_configured:
            raise RuntimeError("OBS endpoint or data bucket is not configured")
        credentials = await self._credentials()
        return await asyncio.to_thread(
            self._sign_put_sync,
            credentials,
            object_key,
            content_type,
        )

    async def _credentials(self) -> ObsCredentials:
        if self.settings.obs_access_key and self.settings.obs_secret_key:
            return ObsCredentials(
                access_key=self.settings.obs_access_key,
                secret_key=self.settings.obs_secret_key,
                security_token=self.settings.obs_security_token,
            )

        now = datetime.now(timezone.utc)
        if self._cached_credentials and now < self._credentials_refresh_at:
            return self._cached_credentials

        async with self._credential_lock:
            now = datetime.now(timezone.utc)
            if self._cached_credentials and now < self._credentials_refresh_at:
                return self._cached_credentials
            async with httpx.AsyncClient(timeout=2.0, trust_env=False) as client:
                response = await client.get(self.settings.ecs_metadata_url)
                response.raise_for_status()
                payload = response.json()
            credentials = ObsCredentials(
                access_key=_required(payload, "access", "accessKey", "Access"),
                secret_key=_required(payload, "secret", "secretKey", "Secret"),
                security_token=_optional(
                    payload,
                    "securitytoken",
                    "securityToken",
                    "SecurityToken",
                ),
            )
            self._cached_credentials = credentials
            # 华为云临时凭证通常有效一小时，提前刷新以避免签名落在过期窗口。
            self._credentials_refresh_at = now + timedelta(minutes=45)
            return credentials

    def _sign_put_sync(
        self,
        credentials: ObsCredentials,
        object_key: str,
        content_type: str,
    ) -> SignedUpload:
        client = ObsClient(
            access_key_id=credentials.access_key,
            secret_access_key=credentials.secret_key,
            security_token=credentials.security_token or None,
            server=self.settings.obs_endpoint,
        )
        try:
            result = client.createSignedUrl(
                method="PUT",
                bucketName=self.settings.obs_data_bucket,
                objectKey=object_key,
                expires=self.settings.obs_signed_url_ttl_seconds,
                headers={"Content-Type": content_type},
            )
            return SignedUpload(
                url=result.signedUrl,
                headers=dict(result.actualSignedRequestHeaders or {}),
            )
        finally:
            client.close()


def build_object_key(device_id: str, session_id: str, filename: str) -> str:
    basename = PurePath(filename).name
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", basename).strip("._")
    if not safe_name:
        safe_name = "media.bin"
    date_prefix = datetime.now(timezone.utc).strftime("%Y/%m/%d")
    return (
        f"raw/{date_prefix}/{device_id}/{session_id}/"
        f"{uuid4().hex}-{safe_name[:160]}"
    )


def _required(payload: dict, *names: str) -> str:
    value = _optional(payload, *names)
    if not value:
        raise RuntimeError(f"ECS metadata response is missing {names[0]}")
    return value


def _optional(payload: dict, *names: str) -> str:
    for name in names:
        value = payload.get(name)
        if value:
            return str(value)
    return ""
