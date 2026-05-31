from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# demo/.env
load_dotenv(Path(__file__).resolve().parents[2] / ".env")


DEFAULT_DEV_SECRET = "kma-dev-secret-key-min-32-characters-long!"


class Settings(BaseSettings):
    DATABASE_URL: str

    SECRET_KEY: str = DEFAULT_DEV_SECRET
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_EMAIL: str = ""
    SMTP_PASSWORD: str = ""

    OTP_EXPIRE_MINUTES: int = 10
    OTP_LENGTH: int = 6
    OTP_RESEND_COOLDOWN_SECONDS: int = 60
    PENDING_LOGIN_EXPIRE_MINUTES: int = 15

    # Public POST /auth/register (default off — dùng create_admin_account.py)
    ALLOW_PUBLIC_REGISTER: bool = False

    # Rate limits (in-memory, per process)
    AUTH_LOGIN_MAX_ATTEMPTS: int = 10
    AUTH_LOGIN_WINDOW_SEC: int = 900
    AUTH_OTP_SEND_MAX: int = 5
    AUTH_OTP_SEND_WINDOW_SEC: int = 900
    AUTH_OTP_VERIFY_MAX: int = 30
    AUTH_OTP_VERIFY_WINDOW_SEC: int = 900

    ADMIN_MAX_UPLOAD_MB: int = 50
    ADMIN_UPLOAD_MAX_PER_HOUR: int = 20
    ADMIN_BENCHMARK_MAX_CASES: int = 10

    # ClamAV — tắt nếu chưa cài (upload vẫn chạy)
    CLAMAV_ENABLED: bool = False
    CLAMAV_SOCKET: str = "/var/run/clamav/clamd.avi"
    CLAMAV_BIN: str = "clamscan"

    # Google OAuth (SSO admin)
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://127.0.0.1:8000/auth/google/callback"
    GOOGLE_ALLOWED_EMAIL_DOMAIN: str = ""  # vd actvn.edu.vn — để trống = chỉ email có trong DB

    # LDAP (SSO admin)
    LDAP_ENABLED: bool = False
    LDAP_SERVER: str = ""
    LDAP_PORT: int = 389
    LDAP_USE_SSL: bool = False
    LDAP_BIND_DN: str = ""
    LDAP_BIND_PASSWORD: str = ""
    LDAP_USER_BASE: str = ""
    LDAP_USER_FILTER: str = "(uid={username})"
    LDAP_EMAIL_ATTR: str = "mail"

    METRICS_ENABLED: bool = True

    # Không còn in OTP ra console; giữ biến để tương thích .env cũ (bị bỏ qua khi gửi OTP)
    KMA_OTP_DEV_LOG: bool = False

    def uses_default_secret(self) -> bool:
        return self.SECRET_KEY == DEFAULT_DEV_SECRET

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
