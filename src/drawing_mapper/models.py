from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class DrawingStatus(str, Enum):
    discovered = "discovered"
    downloaded = "downloaded"
    parsed = "parsed"
    failed = "failed"


class Building(BaseModel):
    id: str
    name: str
    address: str
    latitude: float | None = None
    longitude: float | None = None


class DrawingFile(BaseModel):
    id: str
    building_id: str
    name: str
    mime_type: str
    source_path: str | None = None
    drive_file_id: str | None = None
    status: DrawingStatus = DrawingStatus.discovered


class DrawingText(BaseModel):
    text: str
    x: float
    y: float
    width: float
    height: float


class DrawingPath(BaseModel):
    d: str
    bbox: tuple[float, float, float, float] | None = None
    layer: str | None = None
    entity_type: str | None = None


class DrawingPage(BaseModel):
    page_number: int
    width: float
    height: float
    unit: str = "pt"
    floor_hint: str | None = None
    texts: list[DrawingText] = Field(default_factory=list)
    paths: list[DrawingPath] = Field(default_factory=list)


class ParsedDrawing(BaseModel):
    drawing_file_id: str
    source_path: str | None = None
    source_format: str | None = None
    status: str = "parsed"
    message: str | None = None
    pages: list[DrawingPage] = Field(default_factory=list)


class Floor(BaseModel):
    id: str
    building_id: str
    label: str
    level: int
    drawing_page_id: str | None = None


class EquipmentLocation(BaseModel):
    id: str
    equipment_id: str
    floor_id: str
    drawing_x: float
    drawing_y: float
    latitude: float | None = None
    longitude: float | None = None
    confidence: float = 0.0
    source: str = "parser_candidate"


class CalibrationPoint(BaseModel):
    drawing_x: float
    drawing_y: float
    latitude: float
    longitude: float


class CoordinateCalibration(BaseModel):
    id: str
    floor_id: str
    method: str = "affine"
    points: list[CalibrationPoint] = Field(default_factory=list)
    transform: list[float] | None = None
