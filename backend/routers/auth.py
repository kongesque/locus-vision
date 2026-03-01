"""Auth API router with all authentication endpoints."""

from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, Response, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from auth import (
    hash_password,
    verify_password,
    needs_rehash,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
)
from database import get_db, has_users, get_app_setting
from models import (
    UserCreate,
    UserLogin,
    UserResponse,
    TokenResponse,
    SetupStatusResponse,
    MessageResponse,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

_bearer = HTTPBearer(auto_error=False)

# ── Simple in-memory rate limiter ────────────────────────
_login_attempts: dict[str, list[float]] = {}


def _check_rate_limit(ip: str, max_attempts: int = 5, window: int = 300) -> bool:
    """Returns True if request is allowed, False if rate limited."""
    now = datetime.now(timezone.utc).timestamp()
    attempts = _login_attempts.get(ip, [])
    # Remove old attempts outside the window
    attempts = [t for t in attempts if now - t < window]
    _login_attempts[ip] = attempts
    return len(attempts) < max_attempts


def _record_attempt(ip: str):
    """Record a login attempt for rate limiting."""
    now = datetime.now(timezone.utc).timestamp()
    if ip not in _login_attempts:
        _login_attempts[ip] = []
    _login_attempts[ip].append(now)


# ── Dependencies ─────────────────────────────────────────

async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
):
    """Extract and validate the current user from Bearer token."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id = int(payload["sub"])
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, email, name, role, is_active, created_at FROM users WHERE id = ?",
            (user_id,),
        )
        user = await cursor.fetchone()
        if not user or not user[4]:  # is_active check
            raise HTTPException(status_code=401, detail="User not found or inactive")
        return {
            "id": user[0],
            "email": user[1],
            "name": user[2],
            "role": user[3],
            "is_active": bool(user[4]),
            "created_at": user[5],
        }
    finally:
        await db.close()


# ── Endpoints ────────────────────────────────────────────

@router.get("/setup-status", response_model=SetupStatusResponse)
async def setup_status():
    """Check if initial setup is needed (no users exist)."""
    users_exist = await has_users()
    return SetupStatusResponse(needs_setup=not users_exist)


@router.get("/signup-status")
async def signup_status():
    """Check if public signup is allowed (public endpoint)."""
    allow_signup = await get_app_setting("allow_signup", "false")
    return {"allow_signup": allow_signup == "true"}


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    data: UserCreate,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
):
    """
    Register a new user.
    - If no users exist: creates the first admin (no auth required).
    - If signup is enabled: public registration as viewer.
    - Otherwise: requires an authenticated admin.
    """
    users_exist = await has_users()

    current_user = None
    if users_exist:
        allow_signup = await get_app_setting("allow_signup", "false")

        if credentials:
            # Admin creating a user
            payload = decode_access_token(credentials.credentials)
            if not payload:
                raise HTTPException(status_code=401, detail="Invalid or expired token")
            user_id = int(payload["sub"])
            db = await get_db()
            try:
                cursor = await db.execute(
                    "SELECT id, email, name, role, is_active, created_at FROM users WHERE id = ?",
                    (user_id,),
                )
                user_row = await cursor.fetchone()
                if not user_row or not user_row[4]:
                    raise HTTPException(status_code=401, detail="User not found or inactive")
                current_user = {"id": user_row[0], "role": user_row[3]}
            finally:
                await db.close()
        elif allow_signup != "true":
            # No auth and signup disabled
            raise HTTPException(status_code=403, detail="Public registration is disabled")

    role = "admin" if not users_exist else "viewer"

    db = await get_db()
    try:
        # Check for duplicate email
        cursor = await db.execute(
            "SELECT id FROM users WHERE email = ?", (data.email,)
        )
        if await cursor.fetchone():
            raise HTTPException(status_code=409, detail="Email already registered")

        password_hash = hash_password(data.password)
        cursor = await db.execute(
            """INSERT INTO users (email, name, password_hash, role)
               VALUES (?, ?, ?, ?)""",
            (data.email, data.name, password_hash, role),
        )
        await db.commit()
        user_id = cursor.lastrowid

        cursor = await db.execute(
            "SELECT id, email, name, role, is_active, created_at FROM users WHERE id = ?",
            (user_id,),
        )
        user = await cursor.fetchone()
        return UserResponse(
            id=user[0],
            email=user[1],
            name=user[2],
            role=user[3],
            is_active=bool(user[4]),
            created_at=user[5],
        )
    finally:
        await db.close()


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, request: Request):
    """Authenticate user and return JWT tokens."""
    client_ip = request.client.host if request.client else "unknown"

    # Rate limiting
    if not _check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Please try again later.",
        )

    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, email, name, password_hash, role, is_active FROM users WHERE email = ?",
            (data.email,),
        )
        user = await cursor.fetchone()

        if not user or not verify_password(data.password, user[3]):
            _record_attempt(client_ip)
            raise HTTPException(status_code=401, detail="Invalid email or password")

        if not user[5]:  # is_active
            raise HTTPException(status_code=403, detail="Account is deactivated")

        user_id = user[0]
        role = user[4]

        # Rehash password if Argon2 params have changed
        if needs_rehash(user[3]):
            new_hash = hash_password(data.password)
            await db.execute(
                "UPDATE users SET password_hash = ?, updated_at = datetime('now') WHERE id = ?",
                (new_hash, user_id),
            )
            await db.commit()

        # Create tokens
        access_token = create_access_token(user_id, role)
        refresh_token = create_refresh_token(user_id)

        # Store refresh token hash in sessions
        refresh_hash = hash_password(refresh_token)
        await db.execute(
            """INSERT INTO sessions (user_id, refresh_token_hash, expires_at)
               VALUES (?, ?, datetime('now', '+7 days'))""",
            (user_id, refresh_hash),
        )
        await db.commit()

        return TokenResponse(access_token=access_token, refresh_token=refresh_token)
    finally:
        await db.close()


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: Request):
    """Refresh access token using a valid refresh token."""
    body = await request.json()
    token = body.get("refresh_token")
    if not token:
        raise HTTPException(status_code=400, detail="Refresh token required")

    payload = decode_refresh_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    user_id = int(payload["sub"])

    db = await get_db()
    try:
        # Verify user exists and is active
        cursor = await db.execute(
            "SELECT id, role, is_active FROM users WHERE id = ?", (user_id,)
        )
        user = await cursor.fetchone()
        if not user or not user[2]:
            raise HTTPException(status_code=401, detail="User not found or inactive")

        # Create new tokens (rotation)
        new_access = create_access_token(user[0], user[1])
        new_refresh = create_refresh_token(user[0])

        # Clean old sessions and store new one
        await db.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        refresh_hash = hash_password(new_refresh)
        await db.execute(
            """INSERT INTO sessions (user_id, refresh_token_hash, expires_at)
               VALUES (?, ?, datetime('now', '+7 days'))""",
            (user_id, refresh_hash),
        )
        await db.commit()

        return TokenResponse(access_token=new_access, refresh_token=new_refresh)
    finally:
        await db.close()


@router.post("/logout", response_model=MessageResponse)
async def logout(current_user: dict = Depends(get_current_user)):
    """Logout by invalidating all sessions for the user."""
    db = await get_db()
    try:
        await db.execute("DELETE FROM sessions WHERE user_id = ?", (current_user["id"],))
        await db.commit()
        return MessageResponse(message="Logged out successfully")
    finally:
        await db.close()


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get current authenticated user info."""
    return UserResponse(**current_user)

