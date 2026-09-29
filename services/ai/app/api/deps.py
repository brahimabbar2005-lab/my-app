"""Request-scoped dependencies."""
from __future__ import annotations

from typing import Iterator

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session as OrmSession

from app.config import get_settings
from app.db.repo import session_scope


def get_db() -> Iterator[OrmSession]:
    db = session_scope()
    try:
        yield db
    finally:
        db.close()


def client_ip(request: Request) -> str | None:
    """Real client address behind a proxy.

    Only the first hop of X-Forwarded-For is trusted, and only when the app is
    actually deployed behind a proxy that sets it.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def require_widget_key(x_widget_key: str | None = Header(default=None)) -> None:
    """Shared secret between the WordPress plugin and this API.

    Not a security boundary on its own — the key ships to the browser — but it
    keeps casual scripted abuse off the endpoint and lets the key be rotated
    without changing CORS.
    """
    settings = get_settings()
    if not settings.widget_key:
        return  # unset in development
    if x_widget_key != settings.widget_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid widget key")


def require_admin_key(x_admin_key: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if not settings.admin_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="admin endpoints are disabled: ADMIN_KEY is not set",
        )
    if x_admin_key != settings.admin_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid admin key")


DbSession = Depends(get_db)
WidgetAuth = Depends(require_widget_key)
AdminAuth = Depends(require_admin_key)
