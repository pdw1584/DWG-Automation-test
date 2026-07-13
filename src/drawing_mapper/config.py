from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel


class GoogleDriveConfig(BaseModel):
    folder_id: str
    allowed_mime_types: list[str] = []
    allowed_extensions: list[str] = []
    excluded_folder_name_contains: list[str] = []
    excluded_folder_names: list[str] = []
    service_account_file: str | None = None
    include_shared_drives: bool = True
    recursive: bool = True
    preserve_drive_paths: bool = True


class BuildingConfig(BaseModel):
    name: str
    address: str
    floors: list[int]


class StorageConfig(BaseModel):
    raw_dir: str
    parsed_dir: str
    metadata_dir: str = "data/metadata"
    converted_dir: str = "data/converted"


class DwgConversionConfig(BaseModel):
    oda_executable: str | None = None
    output_version: str = "ACAD2018"
    output_type: str = "DXF"
    recurse: bool = True
    audit: bool = True
    priority_drive_path_prefixes: list[str] = [
        "04_설계도서/01_건축_구조/",
        "04_설계도서/02_전기/",
        "04_설계도서/03_기계/",
        "04_설계도서/04_통신/",
    ]


class ProjectConfig(BaseModel):
    google_drive: GoogleDriveConfig
    building: BuildingConfig
    storage: StorageConfig
    dwg_conversion: DwgConversionConfig = DwgConversionConfig()


def load_project_config(path: str | Path) -> ProjectConfig:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as file:
        return ProjectConfig.model_validate(json.load(file))
