from __future__ import annotations

import csv
import hashlib
from pathlib import Path


FINAL_LOCATION_FIELDNAMES = [
    "facility_location_id",
    "building_name",
    "building_address",
    "floor",
    "discipline",
    "equipment_category",
    "equipment_name",
    "raw_label",
    "keyword",
    "drawing_x",
    "drawing_y",
    "latitude",
    "longitude",
    "confidence",
    "source_status",
    "source_count",
    "primary_source_path",
    "source_paths",
]

CALIBRATION_FIELDNAMES = [
    "floor",
    "control_point_name",
    "drawing_x",
    "drawing_y",
    "latitude",
    "longitude",
    "note",
]


def export_auto_facility_locations(
    input_path: Path,
    output_path: Path,
    building_name: str,
    building_address: str,
) -> list[dict]:
    rows = _read_csv(input_path)
    locations = [
        _to_final_location(
            row=row,
            building_name=building_name,
            building_address=building_address,
            source_status="auto_high_confidence",
        )
        for row in rows
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_csv(output_path, FINAL_LOCATION_FIELDNAMES, locations)
    return locations


def write_calibration_template(
    output_path: Path,
    floors: list[int],
    extra_floor_labels: list[str] | None = None,
) -> list[dict]:
    rows = []
    floor_labels = [f"{floor}F" for floor in floors]
    for floor_label in extra_floor_labels or []:
        if floor_label and floor_label not in floor_labels and floor_label != "unknown":
            floor_labels.append(floor_label)

    for floor_label in floor_labels:
        for index in range(1, 4):
            rows.append(
                {
                    "floor": floor_label,
                    "control_point_name": f"{floor_label}-P{index}",
                    "drawing_x": "",
                    "drawing_y": "",
                    "latitude": "",
                    "longitude": "",
                    "note": "",
                }
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_csv(output_path, CALIBRATION_FIELDNAMES, rows)
    return rows


def _read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def _to_final_location(
    row: dict,
    building_name: str,
    building_address: str,
    source_status: str,
) -> dict:
    raw_label = str(row.get("label") or "").strip()
    equipment_name = str(row.get("canonical_equipment_name") or "").strip() or raw_label
    primary_source_path = str(row.get("primary_source_path") or "").strip()
    source_paths = str(row.get("source_paths") or "").strip()
    if not primary_source_path and source_paths:
        primary_source_path = source_paths.split(" | ")[0].strip()

    item = {
        "building_name": building_name,
        "building_address": building_address,
        "floor": row.get("floor") or "",
        "discipline": row.get("discipline") or "",
        "equipment_category": row.get("equipment_category") or "",
        "equipment_name": equipment_name,
        "raw_label": raw_label,
        "keyword": row.get("keyword") or "",
        "drawing_x": row.get("drawing_x") or "",
        "drawing_y": row.get("drawing_y") or "",
        "latitude": "",
        "longitude": "",
        "confidence": row.get("confidence") or "",
        "source_status": source_status,
        "source_count": row.get("source_count") or "",
        "primary_source_path": primary_source_path,
        "source_paths": source_paths,
    }
    item["facility_location_id"] = _build_location_id(item)
    return item


def _build_location_id(item: dict) -> str:
    value = "|".join(
        [
            str(item.get("building_name") or ""),
            str(item.get("floor") or ""),
            str(item.get("equipment_category") or ""),
            str(item.get("equipment_name") or ""),
            str(item.get("drawing_x") or ""),
            str(item.get("drawing_y") or ""),
            str(item.get("primary_source_path") or ""),
        ]
    )
    return f"fl_{hashlib.sha1(value.encode('utf-8')).hexdigest()[:12]}"


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
