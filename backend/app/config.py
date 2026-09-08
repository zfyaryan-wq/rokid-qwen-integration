from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="OMNI_",
        case_sensitive=False,
        extra="ignore",
    )

    environment: str = "development"
    log_level: str = "INFO"
    public_base_url: str = "http://10.8.0.1"

    jwt_secret: str = ""
    jwt_issuer: str = "omni-cloud-backend"
    jwt_audience: str = "rokid-glass3"
    device_token_ttl_seconds: int = Field(default=43_200, ge=300, le=604_800)
    device_enrollment_token: str = ""

    database_url: str = "sqlite+aiosqlite:///./omni.db"

    dashscope_api_key: str = ""
    dashscope_workspace_id: str = ""
    dashscope_endpoint_host: str = "cn-beijing.maas.aliyuncs.com"
    dashscope_model: str = "qwen3.5-omni-flash-realtime"

    obs_endpoint: str = ""
    obs_data_bucket: str = ""
    obs_release_bucket: str = ""
    obs_access_key: str = ""
    obs_secret_key: str = ""
    obs_security_token: str = ""
    obs_signed_url_ttl_seconds: int = Field(default=900, ge=60, le=86_400)
    ecs_metadata_url: str = "http://169.254.169.254/openstack/latest/securitykey"

    max_upload_bytes: int = Field(default=536_870_912, ge=1_048_576)

    @property
    def qwen_configured(self) -> bool:
        return bool(self.dashscope_api_key and self.dashscope_workspace_id)

    @property
    def obs_configured(self) -> bool:
        return bool(self.obs_endpoint and self.obs_data_bucket)


@lru_cache
def get_settings() -> Settings:
    return Settings()
