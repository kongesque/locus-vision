"""
Pydantic Models for API Request/Response
"""
from pydantic import BaseModel
from typing import Optional


class ZonePoint(BaseModel):
    x: float
    y: float


class Zone(BaseModel):
    id: str
    points: list[ZonePoint]
    classIds: list[int]  # Support multiple classes per zone
    color: list[int]
    label: str


class TrackerConfig(BaseModel):
    track_high_thresh: float = 0.45
    track_low_thresh: float = 0.1
    match_thresh: float = 0.8
    track_buffer: int = 30


class ProcessRequest(BaseModel):
    zones: list[Zone]
    confidence: int = 35
    model: str = "yolo11n.pt"
    trackerConfig: Optional[TrackerConfig] = None


class UpdateZonesRequest(BaseModel):
    zones: list[Zone]


class RenameRequest(BaseModel):
    name: str


class CameraRequest(BaseModel):
    stream_url: str
    source_type: str = "rtsp"


class TestConnectionRequest(BaseModel):
    stream_url: str


class JobResponse(BaseModel):
    id: str
    name: Optional[str]
    filename: Optional[str]
    videoPath: Optional[str]
    framePath: Optional[str]
    frameWidth: Optional[int]
    frameHeight: Optional[int]
    status: str
    progress: int
    zones: list
    confidence: int
    model: str
    trackerConfig: Optional[dict]
    detectionData: list
    dwellData: list
    lineCrossingData: dict
    processTime: float
    sourceType: str
    streamUrl: Optional[str]
    createdAt: Optional[str]
