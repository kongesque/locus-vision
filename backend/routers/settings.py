import logging
import os
import shutil
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from auth import (
    hash_password,
    verify_password,
    decode_access_token,
)
from database import get_db, get_app_setting, set_app_setting
from models import (
    AccountUpdate,
    PasswordChange,
    RoleUpdate,
    AppSettingsUpdate,
    UserResponse,
    MessageResponse,
    AppSettingsResponse,
    SessionResponse,
)

router = APIRouter(tags=["settings"])

_bearer = HTTPBearer(auto_error=False)


# ── Dependency: get current user ─────────────────────────

async def _require_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    """Require a valid authenticated user."""
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
        if not user or not user[4]:
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


async def _require_admin(user: dict = Depends(_require_user)) -> dict:
    """Require an authenticated admin user."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# ══════════════════════════════════════════════════════════
# ACCOUNT SETTINGS (any authenticated user)
# ══════════════════════════════════════════════════════════

@router.put("/api/settings/account", response_model=UserResponse)
async def update_account(
    data: AccountUpdate,
    current_user: dict = Depends(_require_user),
):
    """Update own name and/or email."""
    if data.name is None and data.email is None:
        raise HTTPException(status_code=400, detail="No fields to update")

    db = await get_db()
    try:
        # Check email uniqueness
        if data.email and data.email != current_user["email"]:
            cursor = await db.execute(
                "SELECT id FROM users WHERE email = ? AND id != ?",
                (data.email, current_user["id"]),
            )
            if await cursor.fetchone():
                raise HTTPException(status_code=409, detail="Email already in use")

        updates = []
        params = []
        if data.name is not None:
            updates.append("name = ?")
            params.append(data.name)
        if data.email is not None:
            updates.append("email = ?")
            params.append(data.email)
        updates.append("updated_at = datetime('now')")
        params.append(current_user["id"])

        await db.execute(
            f"UPDATE users SET {', '.join(updates)} WHERE id = ?",
            tuple(params),
        )
        await db.commit()

        # Return updated user
        cursor = await db.execute(
            "SELECT id, email, name, role, is_active, created_at FROM users WHERE id = ?",
            (current_user["id"],),
        )
        user = await cursor.fetchone()
        return UserResponse(
            id=user[0], email=user[1], name=user[2],
            role=user[3], is_active=bool(user[4]), created_at=user[5],
        )
    finally:
        await db.close()


@router.put("/api/settings/password", response_model=MessageResponse)
async def change_password(
    data: PasswordChange,
    current_user: dict = Depends(_require_user),
):
    """Change own password (requires current password re-auth)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT password_hash FROM users WHERE id = ?", (current_user["id"],)
        )
        row = await cursor.fetchone()
        if not row or not verify_password(data.current_password, row[0]):
            raise HTTPException(status_code=401, detail="Current password is incorrect")

        new_hash = hash_password(data.new_password)
        await db.execute(
            "UPDATE users SET password_hash = ?, updated_at = datetime('now') WHERE id = ?",
            (new_hash, current_user["id"]),
        )
        # Invalidate all sessions (force re-login)
        await db.execute("DELETE FROM sessions WHERE user_id = ?", (current_user["id"],))
        await db.commit()

        return MessageResponse(message="Password changed successfully")
    finally:
        await db.close()


@router.get("/api/settings/sessions")
async def list_sessions(current_user: dict = Depends(_require_user)):
    """List active sessions for the current user."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT id, created_at, expires_at FROM sessions
               WHERE user_id = ? AND expires_at > datetime('now')
               ORDER BY created_at DESC""",
            (current_user["id"],),
        )
        rows = await cursor.fetchall()
        return [
            SessionResponse(id=r[0], created_at=r[1], expires_at=r[2])
            for r in rows
        ]
    finally:
        await db.close()


@router.delete("/api/settings/sessions", response_model=MessageResponse)
async def revoke_sessions(current_user: dict = Depends(_require_user)):
    """Revoke all sessions for the current user."""
    db = await get_db()
    try:
        await db.execute("DELETE FROM sessions WHERE user_id = ?", (current_user["id"],))
        await db.commit()
        return MessageResponse(message="All sessions revoked")
    finally:
        await db.close()


@router.delete("/api/settings/account", response_model=MessageResponse)
async def delete_own_account(current_user: dict = Depends(_require_user)):
    """Delete own account and all sessions."""
    db = await get_db()
    try:
        # Check if user exists 
        cursor = await db.execute("SELECT id FROM users WHERE id = ?", (current_user["id"],))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="User not found")

        # Delete user (sessions will be deleted via ON DELETE CASCADE in SQLite, but we can do it explicitly anyway)
        await db.execute("DELETE FROM sessions WHERE user_id = ?", (current_user["id"],))
        await db.execute("DELETE FROM users WHERE id = ?", (current_user["id"],))
        await db.commit()
        return MessageResponse(message="Account deleted successfully")
    finally:
        await db.close()


# ══════════════════════════════════════════════════════════
# ADMIN: USER MANAGEMENT
# ══════════════════════════════════════════════════════════

@router.get("/api/admin/users")
async def list_users(admin: dict = Depends(_require_admin)):
    """List all users (admin only)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, email, name, role, is_active, created_at FROM users ORDER BY id"
        )
        rows = await cursor.fetchall()
        return [
            UserResponse(
                id=r[0], email=r[1], name=r[2],
                role=r[3], is_active=bool(r[4]), created_at=r[5],
            )
            for r in rows
        ]
    finally:
        await db.close()


@router.put("/api/admin/users/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: int,
    data: RoleUpdate,
    admin: dict = Depends(_require_admin),
):
    """Change a user's role (admin only)."""
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="Cannot change your own role")

    db = await get_db()
    try:
        cursor = await db.execute("SELECT id FROM users WHERE id = ?", (user_id,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="User not found")

        await db.execute(
            "UPDATE users SET role = ?, updated_at = datetime('now') WHERE id = ?",
            (data.role, user_id),
        )
        await db.commit()

        cursor = await db.execute(
            "SELECT id, email, name, role, is_active, created_at FROM users WHERE id = ?",
            (user_id,),
        )
        user = await cursor.fetchone()
        return UserResponse(
            id=user[0], email=user[1], name=user[2],
            role=user[3], is_active=bool(user[4]), created_at=user[5],
        )
    finally:
        await db.close()


@router.put("/api/admin/users/{user_id}/active", response_model=UserResponse)
async def toggle_user_active(
    user_id: int,
    admin: dict = Depends(_require_admin),
):
    """Activate or deactivate a user (admin only)."""
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")

    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, is_active FROM users WHERE id = ?", (user_id,)
        )
        user = await cursor.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        new_active = 0 if user[1] else 1
        await db.execute(
            "UPDATE users SET is_active = ?, updated_at = datetime('now') WHERE id = ?",
            (new_active, user_id),
        )
        # If deactivating, revoke their sessions
        if new_active == 0:
            await db.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        await db.commit()

        cursor = await db.execute(
            "SELECT id, email, name, role, is_active, created_at FROM users WHERE id = ?",
            (user_id,),
        )
        u = await cursor.fetchone()
        return UserResponse(
            id=u[0], email=u[1], name=u[2],
            role=u[3], is_active=bool(u[4]), created_at=u[5],
        )
    finally:
        await db.close()


@router.delete("/api/admin/users/{user_id}", response_model=MessageResponse)
async def delete_user(
    user_id: int,
    admin: dict = Depends(_require_admin),
):
    """Delete a user account (admin only)."""
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    db = await get_db()
    try:
        cursor = await db.execute("SELECT id FROM users WHERE id = ?", (user_id,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="User not found")

        await db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        await db.commit()
        return MessageResponse(message="User deleted successfully")
    finally:
        await db.close()


# ══════════════════════════════════════════════════════════
# ADMIN: APP SETTINGS
# ══════════════════════════════════════════════════════════

@router.get("/api/admin/app-settings", response_model=AppSettingsResponse)
async def get_app_settings(admin: dict = Depends(_require_admin)):
    """Get app-level settings (admin only)."""
    allow_signup = await get_app_setting("allow_signup", "false")
    return AppSettingsResponse(allow_signup=allow_signup == "true")


@router.put("/api/admin/app-settings", response_model=AppSettingsResponse)
async def update_app_settings(
    data: AppSettingsUpdate,
    admin: dict = Depends(_require_admin),
):
    """Update app-level settings (admin only)."""
    if data.allow_signup is not None:
        await set_app_setting("allow_signup", "true" if data.allow_signup else "false")

    allow_signup = await get_app_setting("allow_signup", "false")
    return AppSettingsResponse(allow_signup=allow_signup == "true")

@router.get("/api/admin/system/storage")
async def get_storage_stats(admin: dict = Depends(_require_admin)):
    """Admin only: Get system storage stats."""
    try:
        # We check the disk usage of the data directory where videos/models are stored
        target_dir = "data"
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)
            
        total, used, free = shutil.disk_usage(target_dir)
        return {
            "total": total,
            "used": used,
            "free": free,
            "percent_used": (used / total) * 100 if total > 0 else 0
        }
    except Exception as e:
        logging.error(f"Error getting storage stats: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve storage statistics."
        )

@router.delete("/api/admin/media", response_model=MessageResponse)
async def delete_all_media(admin: dict = Depends(_require_admin)):
    """Admin only: Delete all video tasks and physical media files."""
    db = await get_db()
    try:
        # 1. Clear database tables
        await db.execute("DELETE FROM video_tasks")
        await db.execute("DELETE FROM cameras")
        await db.commit()

        # 2. Clear physical files in data/videos
        # Note: Do not delete data/models
        video_dir = "data/videos"
        if os.path.exists(video_dir):
            for filename in os.listdir(video_dir):
                file_path = os.path.join(video_dir, filename)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    logging.error(f"Failed to delete {file_path}. Reason: {e}")
                    
        return MessageResponse(message="All videos and streams have been permanently deleted.")
    except Exception as e:
        logging.error(f"Error deleting media: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to delete media files and database records."
        )
    finally:
        await db.close()
