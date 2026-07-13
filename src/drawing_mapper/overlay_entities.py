from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


ENTITY_TYPES = {"INSERT", "TEXT", "MTEXT", "LWPOLYLINE", "POLYLINE", "LINE", "CIRCLE", "ARC"}

FIELDNAMES = [
    "status",
    "basis_name",
    "basis_alignment",
    "drawing_name",
    "drawing_path",
    "source_path",
    "entity_type",
    "layer",
    "handle",
    "block_name",
    "text",
    "x",
    "y",
    "z",
    "rotation",
    "xscale",
    "yscale",
    "color",
    "lineweight",
    "bbox_min_x",
    "bbox_min_y",
    "bbox_max_x",
    "bbox_max_y",
]


def extract_confirmed_overlay_entities(
    confirmed_drawings_path: Path,
    output_csv_path: Path,
    report_path: Path,
    entity_types: set[str] | None = None,
) -> dict[str, Any]:
    entity_types = entity_types or ENTITY_TYPES
    rows = _read_csv(confirmed_drawings_path)
    output_csv_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    entities: list[dict[str, Any]] = []
    drawing_reports: list[dict[str, Any]] = []

    for row in rows:
        drawing_path = Path(str(row.get("v2_path") or ""))
        drawing_report = {
            "drawing_name": str(row.get("drawing_name") or drawing_path.name),
            "drawing_path": str(drawing_path),
            "status": "skipped",
            "entity_count": 0,
            "message": "",
        }

        if drawing_path.suffix.casefold() != ".dxf":
            drawing_report["message"] = "Only DXF drawings can be parsed; convert this drawing to DXF."
            drawing_reports.append(drawing_report)
            continue
        if not drawing_path.exists():
            drawing_report["status"] = "missing"
            drawing_report["message"] = "Drawing file was not found."
            drawing_reports.append(drawing_report)
            continue

        try:
            extracted = _extract_dxf_entities(drawing_path, row, entity_types)
        except Exception as exc:  # pragma: no cover - defensive per-drawing isolation
            drawing_report["status"] = "failed"
            drawing_report["message"] = str(exc)
            drawing_reports.append(drawing_report)
            continue

        entities.extend(extracted)
        drawing_report["status"] = "parsed"
        drawing_report["entity_count"] = len(extracted)
        drawing_reports.append(drawing_report)

    _write_csv(output_csv_path, entities)
    report = {
        "confirmed_drawings": str(confirmed_drawings_path),
        "output_csv": str(output_csv_path),
        "drawing_count": len(rows),
        "parsed_drawing_count": sum(1 for item in drawing_reports if item["status"] == "parsed"),
        "skipped_drawing_count": sum(1 for item in drawing_reports if item["status"] == "skipped"),
        "missing_drawing_count": sum(1 for item in drawing_reports if item["status"] == "missing"),
        "failed_drawing_count": sum(1 for item in drawing_reports if item["status"] == "failed"),
        "entity_count": len(entities),
        "entity_type_counts": _count_by(entities, "entity_type"),
        "drawing_reports": drawing_reports,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _extract_dxf_entities(
    drawing_path: Path,
    drawing_row: dict[str, str],
    entity_types: set[str],
) -> list[dict[str, Any]]:
    try:
        import ezdxf
    except ImportError as exc:
        message = "DXF entity extraction requires `pip install -e .[parser]`."
        raise RuntimeError(message) from exc

    document = ezdxf.readfile(drawing_path)
    entities: list[dict[str, Any]] = []
    for entity in document.modelspace():
        entity_type = entity.dxftype()
        if entity_type not in entity_types:
            continue
        entities.append(_entity_row(entity, entity_type, drawing_path, drawing_row))
    return entities


def _entity_row(
    entity: object,
    entity_type: str,
    drawing_path: Path,
    drawing_row: dict[str, str],
) -> dict[str, Any]:
    insert = _entity_point(entity, entity_type)
    bbox = _entity_bbox(entity)
    dxf = entity.dxf
    return {
        "status": "parsed",
        "basis_name": drawing_row.get("basis_name") or "XR-PLAN",
        "basis_alignment": drawing_row.get("basis_alignment") or "same_origin_identity",
        "drawing_name": drawing_row.get("drawing_name") or drawing_path.name,
        "drawing_path": str(drawing_path),
        "source_path": drawing_row.get("source_path") or "",
        "entity_type": entity_type,
        "layer": str(getattr(dxf, "layer", "") or ""),
        "handle": str(getattr(dxf, "handle", "") or getattr(entity, "dxfhandle", "") or ""),
        "block_name": _block_name(entity, entity_type),
        "text": _entity_text(entity, entity_type),
        "x": insert[0],
        "y": insert[1],
        "z": insert[2],
        "rotation": _number(getattr(dxf, "rotation", "")),
        "xscale": _number(getattr(dxf, "xscale", "")),
        "yscale": _number(getattr(dxf, "yscale", "")),
        "color": str(getattr(dxf, "color", "") or ""),
        "lineweight": str(getattr(dxf, "lineweight", "") or ""),
        "bbox_min_x": bbox[0] if bbox else "",
        "bbox_min_y": bbox[1] if bbox else "",
        "bbox_max_x": bbox[2] if bbox else "",
        "bbox_max_y": bbox[3] if bbox else "",
    }


def _entity_point(entity: object, entity_type: str) -> tuple[float | str, float | str, float | str]:
    dxf = entity.dxf
    point = None
    if entity_type in {"INSERT", "TEXT", "MTEXT"}:
        point = getattr(dxf, "insert", None)
    elif entity_type == "LINE":
        point = getattr(dxf, "start", None)
    elif entity_type in {"CIRCLE", "ARC"}:
        point = getattr(dxf, "center", None)
    elif entity_type in {"LWPOLYLINE", "POLYLINE"}:
        point = _first_polyline_point(entity, entity_type)
    if point is None:
        return "", "", ""
    return _number(getattr(point, "x", "")), _number(getattr(point, "y", "")), _number(getattr(point, "z", 0))


def _first_polyline_point(entity: object, entity_type: str) -> Any:
    try:
        if entity_type == "LWPOLYLINE":
            first = next(iter(entity.get_points("xy")))
            return _Point(first[0], first[1], 0)
        first = next(iter(entity.points()))
        return _Point(first[0], first[1], first[2] if len(first) > 2 else 0)
    except Exception:
        return None


class _Point:
    def __init__(self, x: float, y: float, z: float) -> None:
        self.x = x
        self.y = y
        self.z = z


def _block_name(entity: object, entity_type: str) -> str:
    if entity_type != "INSERT":
        return ""
    return str(getattr(entity.dxf, "name", "") or "")


def _entity_text(entity: object, entity_type: str) -> str:
    if entity_type == "MTEXT":
        return str(entity.plain_text() or "").strip()
    if entity_type == "TEXT":
        return str(getattr(entity.dxf, "text", "") or "").strip()
    return ""


def _entity_bbox(entity: object) -> tuple[float, float, float, float] | None:
    try:
        extmin, extmax = entity.bbox()
    except Exception:
        return None
    return (_number(extmin.x), _number(extmin.y), _number(extmax.x), _number(extmax.y))


def _number(value: Any) -> float | str:
    if value == "":
        return ""
    try:
        return float(value)
    except (TypeError, ValueError):
        return ""


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def _count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))
