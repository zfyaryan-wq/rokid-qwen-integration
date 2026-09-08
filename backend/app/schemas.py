from pydantic import BaseModel, Field, field_validator


class DeviceLoginRequest(BaseModel):
    device_id: str = Field(min_length=3, max_length=128)
    enrollment_token: str = Field(min_length=1, max_length=512)

    @field_validator("device_id")
    @classmethod
    def validate_device_id(cls, value: str) -> str:
        if not all(character.isalnum() or character in "-_.:" for character in value):
            raise ValueError("device_id contains unsupported characters")
        return value


class DeviceLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    realtime_ws_url: str


class UploadSignRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=128)
    size_bytes: int = Field(ge=1)


class UploadSignResponse(BaseModel):
    upload_id: str
    object_key: str
    signed_url: str
    required_headers: dict[str, str]
    expires_in: int


class UploadCompleteRequest(BaseModel):
    upload_id: str
    etag: str = Field(min_length=1, max_length=256)
    sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")


class UploadCompleteResponse(BaseModel):
    upload_id: str
    status: str
