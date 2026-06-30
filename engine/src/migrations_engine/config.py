from functools import lru_cache
from pathlib import Path
from urllib.parse import unquote

from pydantic import field_validator
from sqlalchemy.engine import URL
from pydantic_settings import BaseSettings, SettingsConfigDict


ENGINE_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="KATANA_",
        extra="ignore",
        env_file=ENGINE_ENV_FILE,
        env_file_encoding="utf-8",
    )

    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_database: str = "katana"
    mysql_username: str = "katana"
    mysql_password: str = ""
    bootstrap_admin_email: str = ""
    bootstrap_admin_password: str = ""
    bootstrap_admin_display_name: str = "Administrator"
    jwt_secret: str = "dev-only-change-me"
    jwt_access_token_hours: int = 8
    password_reset_token_hours: int = 1
    password_min_length: int = 8
    sqlalchemy_url_override: str | None = None

    @field_validator("mysql_password", "bootstrap_admin_password", mode="before")
    @classmethod
    def decode_password(cls, value: object) -> object:
        if isinstance(value, str):
            return unquote(value)
        return value

    @property
    def sqlalchemy_url(self) -> URL | str:
        if self.sqlalchemy_url_override:
            return self.sqlalchemy_url_override
        return URL.create(
            "mysql+pymysql",
            username=self.mysql_username,
            password=self.mysql_password,
            host=self.mysql_host,
            port=self.mysql_port,
            database=self.mysql_database,
        )

    @property
    def database_url(self) -> str:
        if isinstance(self.sqlalchemy_url, str):
            return self.sqlalchemy_url
        return self.sqlalchemy_url.render_as_string(hide_password=False)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
