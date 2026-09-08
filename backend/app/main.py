import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import (
    bearer_token,
    create_device_token,
    decode_device_token,
    validate_enrollment_token,
)
from .config import Settings, get_settings
from .database import Database
from .models import UploadRecord
from .obs import HuaweiObsSigner, build_object_key
from .realtime import proxy_qwen_realtime
from .schemas import (
    DeviceLoginRequest,
    DeviceLoginResponse,
    UploadCompleteRequest,
    UploadCompleteResponse,
    UploadSignRequest,
    UploadSignResponse,
)


def create_app(
    settings: Settings | None = None,
    obs_signer: HuaweiObsSigner | None = None,
) -> FastAPI:
    runtime_settings = settings or get_settings()
    logging.basicConfig(
        level=getattr(logging, runtime_settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    database = Database(runtime_settings.database_url)
    signer = obs_signer or HuaweiObsSigner(runtime_settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await database.create_schema()
        yield
        await database.close()

    application = FastAPI(
        title="Omni Cloud Backend",
        version="0.1.0",
        docs_url="/docs" if runtime_settings.environment != "production" else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    application.state.settings = runtime_settings
    application.state.database = database
    application.state.obs_signer = signer

    async def db_session():
        async for session in database.session():
            yield session

    async def current_device(
        authorization: str | None = Header(default=None),
    ) -> str:
        return decode_device_token(
            bearer_token(authorization),
            runtime_settings,
        )

    @application.get("/health")
    async def health() -> dict:
        return {
            "status": "ok",
            "version": application.version,
            "qwen_configured": runtime_settings.qwen_configured,
            "obs_configured": runtime_settings.obs_configured,
        }

    @application.post(
        "/api/v1/devices/login",
        response_model=DeviceLoginResponse,
    )
    async def device_login(
        payload: DeviceLoginRequest,
    ) -> DeviceLoginResponse:
        validate_enrollment_token(payload.enrollment_token, runtime_settings)
        access_token = create_device_token(payload.device_id, runtime_settings)
        return DeviceLoginResponse(
            access_token=access_token,
            expires_in=runtime_settings.device_token_ttl_seconds,
            realtime_ws_url=_realtime_url(runtime_settings),
        )

    @application.websocket("/api/v1/realtime")
    async def realtime(websocket: WebSocket) -> None:
        try:
            token = bearer_token(websocket.headers.get("authorization"))
            device_id = decode_device_token(token, runtime_settings)
        except HTTPException:
            await websocket.close(code=4401)
            return
        logging.getLogger(__name__).info("Realtime connected device=%s", device_id)
        await proxy_qwen_realtime(websocket, runtime_settings)

    @application.post(
        "/api/v1/uploads/sign",
        response_model=UploadSignResponse,
    )
    async def sign_upload(
        payload: UploadSignRequest,
        device_id: str = Depends(current_device),
        session: AsyncSession = Depends(db_session),
    ) -> UploadSignResponse:
        if payload.size_bytes > runtime_settings.max_upload_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Upload exceeds configured size limit",
            )
        object_key = build_object_key(
            device_id,
            payload.session_id,
            payload.filename,
        )
        try:
            signed = await signer.sign_put(object_key, payload.content_type)
        except Exception as error:
            logging.getLogger(__name__).exception("OBS signing failed")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Object storage is temporarily unavailable",
            ) from error

        record = UploadRecord(
            device_id=device_id,
            session_id=payload.session_id,
            object_key=object_key,
            content_type=payload.content_type,
            expected_size=payload.size_bytes,
        )
        session.add(record)
        await session.commit()
        await session.refresh(record)
        return UploadSignResponse(
            upload_id=record.id,
            object_key=object_key,
            signed_url=signed.url,
            required_headers=signed.headers,
            expires_in=runtime_settings.obs_signed_url_ttl_seconds,
        )

    @application.post(
        "/api/v1/uploads/complete",
        response_model=UploadCompleteResponse,
    )
    async def complete_upload(
        payload: UploadCompleteRequest,
        device_id: str = Depends(current_device),
        session: AsyncSession = Depends(db_session),
    ) -> UploadCompleteResponse:
        record = await session.scalar(
            select(UploadRecord).where(
                UploadRecord.id == payload.upload_id,
                UploadRecord.device_id == device_id,
            )
        )
        if record is None:
            raise HTTPException(status_code=404, detail="Upload record not found")
        record.status = "completed"
        record.etag = payload.etag
        record.sha256 = payload.sha256.lower()
        record.completed_at = datetime.now(timezone.utc)
        await session.commit()
        return UploadCompleteResponse(upload_id=record.id, status=record.status)

    return application


def _realtime_url(settings: Settings) -> str:
    base = settings.public_base_url.rstrip("/")
    if base.startswith("https://"):
        return f"wss://{base.removeprefix('https://')}/api/v1/realtime"
    if base.startswith("http://"):
        return f"ws://{base.removeprefix('http://')}/api/v1/realtime"
    raise HTTPException(
        status_code=500,
        detail="OMNI_PUBLIC_BASE_URL must start with http:// or https://",
    )


app = create_app()
