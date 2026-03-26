"""
System API Routes
"""
from fastapi import APIRouter

from app.services.gpu_utils import get_gpu_info
from app.services.coco_classes import COCO_CLASSES

router = APIRouter()


@router.get("/system-info")
async def system_info():
    """Get system information including GPU status."""
    gpu_info = get_gpu_info()
    return {
        "gpu": gpu_info,
        "version": "0.2.0"
    }


@router.get("/coco-classes")
async def coco_classes():
    """Get COCO class names."""
    return COCO_CLASSES
