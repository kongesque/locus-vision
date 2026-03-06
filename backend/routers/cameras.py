"""CRUD router for camera management."""

import uuid
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from typing import List
from database import get_db
from models import CameraCreate, CameraUpdate, CameraResponse

router = APIRouter(
    prefix="/api/cameras",
    tags=["cameras"],
    responses={404: {"description": "Not found"}},
)


@router.get("", response_model=List[CameraResponse])
async def list_cameras():
    """List all cameras."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM cameras ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        return [CameraResponse(**dict(row)) for row in rows]
    finally:
        await db.close()


@router.get("/{camera_id}", response_model=CameraResponse)
async def get_camera(camera_id: str):
    """Get a single camera by ID."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM cameras WHERE id = ?", (camera_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Camera not found")
        return CameraResponse(**dict(row))
    finally:
        await db.close()


@router.post("", response_model=CameraResponse)
async def create_camera(camera: CameraCreate):
    """Create a new camera."""
    camera_id = camera.id or str(uuid.uuid4())
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO cameras (id, name, type, url, device_id, model_name, fps, zones, classes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                camera_id,
                camera.name,
                camera.type,
                camera.url,
                camera.device_id,
                camera.model_name,
                camera.fps,
                camera.zones,
                camera.classes,
            ),
        )
        await db.commit()

        cursor = await db.execute("SELECT * FROM cameras WHERE id = ?", (camera_id,))
        row = await cursor.fetchone()
        return CameraResponse(**dict(row))
    finally:
        await db.close()


@router.put("/{camera_id}", response_model=CameraResponse)
async def update_camera(camera_id: str, update: CameraUpdate):
    """Update a camera's configuration."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM cameras WHERE id = ?", (camera_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Camera not found")

        # Build dynamic SET clause for non-None fields
        existing = dict(row)
        updates = update.model_dump(exclude_none=True)
        if not updates:
            return CameraResponse(**existing)

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        set_clause += ", updated_at = datetime('now')"
        values = list(updates.values()) + [camera_id]

        await db.execute(
            f"UPDATE cameras SET {set_clause} WHERE id = ?",
            values,
        )
        await db.commit()

        cursor = await db.execute("SELECT * FROM cameras WHERE id = ?", (camera_id,))
        row = await cursor.fetchone()
        return CameraResponse(**dict(row))
    finally:
        await db.close()


@router.delete("/{camera_id}")
async def delete_camera(camera_id: str):
    """Delete a camera."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM cameras WHERE id = ?", (camera_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Camera not found")

        await db.execute("DELETE FROM cameras WHERE id = ?", (camera_id,))
        await db.commit()
        return JSONResponse({"message": "Camera deleted"})
    finally:
        await db.close()
