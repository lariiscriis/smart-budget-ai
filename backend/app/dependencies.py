from collections.abc import Generator

from sqlalchemy.orm import Session

from app.database import engine
from app import ownership  # registers the financial ownership policy


def get_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        session.info["http_request"] = True
        yield session
