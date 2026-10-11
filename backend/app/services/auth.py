"""Account registration, login, and server-side session management.

Design: opaque random session tokens (not JWTs). The browser receives the
token in an ``HttpOnly; SameSite=Lax`` cookie; API clients may send it as a
``Bearer`` token. Only the SHA-256 of the token is stored, sessions expire,
and logout deletes the row — so revocation is immediate, which stateless JWTs
cannot offer without a denylist.
"""

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthenticationError, ConflictError, InvalidRequestError
from app.core.security import (
    hash_password,
    hash_token,
    needs_rehash,
    new_session_token,
    verify_password,
)
from app.db.models import User, UserSession

_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,189}\.[^@\s]{2,}$")
MIN_PASSWORD_LENGTH = 10


def normalize_email(email: str) -> str:
    value = email.strip().lower()
    if not _EMAIL.match(value):
        raise InvalidRequestError("Enter a valid email address.")
    return value


def validate_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise InvalidRequestError(f"Passwords must be at least {MIN_PASSWORD_LENGTH} characters.")
    if len(password) > 256:
        raise InvalidRequestError("Passwords must be at most 256 characters.")


@dataclass(frozen=True)
class IssuedSession:
    token: str
    user: User
    expires_at: datetime


class AuthService:
    def __init__(self, session: AsyncSession, session_ttl: timedelta) -> None:
        self._db = session
        self._ttl = session_ttl

    async def signup(
        self, email: str, password: str, display_name: str | None, user_agent: str | None
    ) -> IssuedSession:
        email = normalize_email(email)
        validate_password(password)
        user = User(
            email=email,
            password_hash=hash_password(password),
            display_name=(display_name or "").strip()[:80] or None,
        )
        self._db.add(user)
        try:
            await self._db.flush()
        except IntegrityError as exc:
            await self._db.rollback()
            raise ConflictError("An account with this email already exists.") from exc
        issued = await self._issue(user, user_agent)
        await self._db.commit()
        return issued

    async def login(self, email: str, password: str, user_agent: str | None) -> IssuedSession:
        try:
            email = normalize_email(email)
        except InvalidRequestError:
            email = ""
        user = (
            await self._db.scalars(select(User).where(User.email == email))
        ).first() if email else None
        # verify_password runs even when the user is missing to equalize timing.
        if not verify_password(user.password_hash if user else None, password) or user is None:
            raise AuthenticationError("Incorrect email or password.")
        if needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)
        await self._db.execute(
            delete(UserSession).where(
                UserSession.user_id == user.id, UserSession.expires_at < datetime.now(UTC)
            )
        )
        issued = await self._issue(user, user_agent)
        await self._db.commit()
        return issued

    async def logout(self, token: str) -> None:
        await self._db.execute(delete(UserSession).where(UserSession.token_hash == hash_token(token)))
        await self._db.commit()

    async def resolve(self, token: str) -> User | None:
        record = await self._db.get(UserSession, hash_token(token))
        if record is None:
            return None
        if record.expires_at <= datetime.now(UTC):
            await self._db.delete(record)
            await self._db.commit()
            return None
        return record.user

    async def _issue(self, user: User, user_agent: str | None) -> IssuedSession:
        token = new_session_token()
        expires_at = datetime.now(UTC) + self._ttl
        self._db.add(
            UserSession(
                token_hash=hash_token(token),
                user_id=user.id,
                expires_at=expires_at,
                user_agent=(user_agent or "")[:255] or None,
            )
        )
        await self._db.flush()
        return IssuedSession(token, user, expires_at)
