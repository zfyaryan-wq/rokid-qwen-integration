from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.obs import SignedUpload


class FakeObsSigner:
    async def sign_put(self, object_key: str, content_type: str) -> SignedUpload:
        return SignedUpload(
            url=f"https://obs.example.test/{object_key}?signature=test",
            headers={"Content-Type": content_type},
        )


def test_health_login_and_upload_flow(tmp_path: Path) -> None:
    settings = Settings(
        jwt_secret="test-secret-that-is-at-least-32-bytes-long",
        device_enrollment_token="enroll-test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        public_base_url="http://10.8.0.1",
        dashscope_api_key="dashscope-test",
        dashscope_workspace_id="workspace-test",
        obs_endpoint="https://obs.example.test",
        obs_data_bucket="test-bucket",
    )
    app = create_app(settings, FakeObsSigner())

    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["qwen_configured"] is True
        assert health.json()["obs_configured"] is True

        login = client.post(
            "/api/v1/devices/login",
            json={
                "device_id": "glass3-test-01",
                "enrollment_token": "enroll-test",
            },
        )
        assert login.status_code == 200
        body = login.json()
        assert body["realtime_ws_url"] == "ws://10.8.0.1/api/v1/realtime"
        headers = {"Authorization": f"Bearer {body['access_token']}"}

        signed = client.post(
            "/api/v1/uploads/sign",
            headers=headers,
            json={
                "session_id": "session-01",
                "filename": "../sample.pcm",
                "content_type": "audio/L16",
                "size_bytes": 3200,
            },
        )
        assert signed.status_code == 200
        signed_body = signed.json()
        assert "/glass3-test-01/session-01/" in signed_body["object_key"]
        assert ".." not in signed_body["object_key"]
        assert signed_body["required_headers"]["Content-Type"] == "audio/L16"

        completed = client.post(
            "/api/v1/uploads/complete",
            headers=headers,
            json={
                "upload_id": signed_body["upload_id"],
                "etag": "etag-test",
                "sha256": "a" * 64,
            },
        )
        assert completed.status_code == 200
        assert completed.json()["status"] == "completed"


def test_login_rejects_invalid_enrollment_token(tmp_path: Path) -> None:
    settings = Settings(
        jwt_secret="test-secret",
        device_enrollment_token="correct-token",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
    )
    app = create_app(settings, FakeObsSigner())

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/devices/login",
            json={"device_id": "glass3-test-01", "enrollment_token": "wrong"},
        )
        assert response.status_code == 401
