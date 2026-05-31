from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from admin_auth.core.config import settings

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from admin_auth.models import user_minimal  # noqa: F401
    from admin_auth.models import audit_log  # noqa: F401
    from admin_auth.models import document_record  # noqa: F401
    from admin_auth.models import chat_log  # noqa: F401
    from admin_auth.models import chat_session  # noqa: F401
    from admin_auth.models import token_session  # noqa: F401

    Base.metadata.create_all(bind=engine)
