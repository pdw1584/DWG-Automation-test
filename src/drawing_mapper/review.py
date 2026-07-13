from __future__ import annotations

import csv
import hashlib
from pathlib import Path


REVIEW_FIELDNAMES = [
    "review_status",
    "review_note",
    "canonical_equipment_name",
    "review_id",
    "floor",
    "discipline",
    "equipment_category",
    "keyword",
    "label",
    "drawing_x",
    "drawing_y",
    "confidence",
    "source_count",
    "primary_source_path",
    "source_paths",
]


def build_location_review_csv(input_path: Path, output_path: Path) -> list[dict]:
    rows = _read_csv(input_path)
    review_rows = [_to_review_row(row) for row in rows]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_review_csv(output_path, review_rows)
    return review_rows


def _read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def _to_review_row(row: dict) -> dict:
    source_paths = str(row.get("source_paths") or "")
    primary_source_path = _first_source_path(source_paths)
    review_id = _build_review_id(row, primary_source_path)

    return {
        "review_status": "",
        "review_note": "",
        "canonical_equipment_name": "",
        "review_id": review_id,
        "floor": row.get("floor") or "",
        "discipline": row.get("discipline") or "",
        "equipment_category": row.get("equipment_category") or "",
        "keyword": row.get("keyword") or "",
        "label": row.get("label") or "",
        "drawing_x": row.get("drawing_x") or "",
        "drawing_y": row.get("drawing_y") or "",
        "confidence": row.get("confidence") or "",
        "source_count": row.get("source_count") or "",
        "primary_source_path": primary_source_path,
        "source_paths": source_paths,
    }


def _first_source_path(source_paths: str) -> str:
    if not source_paths:
        return ""
    return source_paths.split(" | ")[0].strip()


def _build_review_id(row: dict, primary_source_path: str) -> str:
    value = "|".join(
        [
            str(row.get("floor") or ""),
            str(row.get("discipline") or ""),
            str(row.get("equipment_category") or ""),
            str(row.get("label") or ""),
            str(row.get("drawing_x") or ""),
            str(row.get("drawing_y") or ""),
            primary_source_path,
        ]
    )
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]


def _write_review_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=REVIEW_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
