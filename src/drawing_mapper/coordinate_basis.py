from __future__ import annotations

import csv
import json
import math
from pathlib import Path


BASIS_FIELDNAMES = [
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
    "basis_x",
    "basis_y",
    "coordinate_basis",
    "basis_status",
    "basis_confidence",
    "basis_reason",
    "xref_name",
    "xref_path",
    "xref_insert_x",
    "xref_insert_y",
    "xref_xscale",
    "xref_yscale",
    "xref_rotation",
    "latitude",
    "longitude",
    "confidence",
    "source_status",
    "source_count",
    "primary_source_path",
    "source_paths",
]


def map_facility_coordinate_basis(
    locations_path: Path,
    xref_inventory_path: Path,
    output_path: Path,
    report_path: Path,
) -> dict:
    locations = _read_csv(locations_path)
    xrefs = _read_csv(xref_inventory_path)
    xrefs_by_path = _group_xrefs_by_drawing_path(xrefs)

    output_rows = []
    status_counts: dict[str, int] = {}
    basis_counts: dict[str, int] = {}

    for location in locations:
        source_path = str(location.get("primary_source_path") or "")
        source_xrefs = xrefs_by_path.get(_normalize_path_key(source_path), [])
        basis = _select_basis_xref(location, source_xrefs)
        output = _map_location(location, basis)
        output_rows.append(output)

        status = str(output.get("basis_status") or "")
        coordinate_basis = str(output.get("coordinate_basis") or "")
        status_counts[status] = status_counts.get(status, 0) + 1
        if coordinate_basis:
            basis_counts[coordinate_basis] = basis_counts.get(coordinate_basis, 0) + 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_csv(output_path, BASIS_FIELDNAMES, output_rows)

    report = {
        "location_count": len(locations),
        "mapped_count": sum(1 for row in output_rows if row.get("basis_status") == "mapped"),
        "unmapped_count": sum(1 for row in output_rows if row.get("basis_status") != "mapped"),
        "status_counts": dict(sorted(status_counts.items())),
        "basis_counts": dict(sorted(basis_counts.items())),
        "output_csv": str(output_path),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _group_xrefs_by_drawing_path(xrefs: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for row in xrefs:
        if str(row.get("status") or "") != "parsed":
            continue
        key = _normalize_path_key(str(row.get("drawing_path") or ""))
        if not key:
            continue
        grouped.setdefault(key, []).append(row)
    return grouped


def _select_basis_xref(location: dict, xrefs: list[dict]) -> dict | None:
    usable = [row for row in xrefs if _has_insert_transform(row) and _is_plan_like_xref(row)]
    if not usable:
        return None

    floor = str(location.get("floor") or "")
    ranked = sorted(
        usable,
        key=lambda row: (
            -_basis_score(row, floor),
            str(row.get("xref_name") or ""),
            str(row.get("xref_path") or ""),
        ),
    )
    best = ranked[0]
    if _basis_score(best, floor) <= 0:
        return None
    return best


def _basis_score(row: dict, floor: str) -> int:
    name = str(row.get("xref_name") or "").casefold()
    path = str(row.get("xref_path") or "").casefold()
    text = f"{name} {path}"
    row_floor = str(row.get("floor_hint") or "")
    identity_bonus = 30 if _is_truthy(row.get("is_identity_insert")) else 0
    floor_bonus = 20 if floor and row_floor == floor else 0

    if "xr-plan" in text:
        return 100 + identity_bonus + floor_bonus
    if "xr-\uc7a5\ube44" in text:
        return 90 + identity_bonus + floor_bonus
    if "x-site" in text or "xr-\ubc30\uce58" in text:
        return 80 + identity_bonus + floor_bonus
    if "plan" in text and floor and floor.casefold() in text:
        return 70 + identity_bonus + floor_bonus
    if "plan" in text:
        return 60 + identity_bonus + floor_bonus
    if "site" in text:
        return 50 + identity_bonus + floor_bonus
    return 0


def _map_location(location: dict, basis: dict | None) -> dict:
    output = {field: location.get(field, "") for field in BASIS_FIELDNAMES}
    output["basis_x"] = ""
    output["basis_y"] = ""
    output["coordinate_basis"] = ""
    output["basis_status"] = "unmapped"
    output["basis_confidence"] = "0"
    output["basis_reason"] = "no usable plan xref found"
    output["xref_name"] = ""
    output["xref_path"] = ""
    output["xref_insert_x"] = ""
    output["xref_insert_y"] = ""
    output["xref_xscale"] = ""
    output["xref_yscale"] = ""
    output["xref_rotation"] = ""

    if basis is None:
        return output

    drawing_x = _to_float(location.get("drawing_x"))
    drawing_y = _to_float(location.get("drawing_y"))
    if drawing_x is None or drawing_y is None:
        output["basis_reason"] = "missing drawing coordinates"
        return output

    basis_x, basis_y = _to_basis_coordinates(drawing_x, drawing_y, basis)
    output["basis_x"] = _format_float(basis_x)
    output["basis_y"] = _format_float(basis_y)
    output["coordinate_basis"] = str(basis.get("xref_name") or basis.get("xref_file") or "")
    output["basis_status"] = "mapped"
    output["basis_confidence"] = _basis_confidence(basis)
    output["basis_reason"] = _basis_reason(basis)
    output["xref_name"] = str(basis.get("xref_name") or "")
    output["xref_path"] = str(basis.get("xref_path") or "")
    output["xref_insert_x"] = str(basis.get("insert_x") or "")
    output["xref_insert_y"] = str(basis.get("insert_y") or "")
    output["xref_xscale"] = str(basis.get("xscale") or "")
    output["xref_yscale"] = str(basis.get("yscale") or "")
    output["xref_rotation"] = str(basis.get("rotation") or "")
    return output


def _to_basis_coordinates(drawing_x: float, drawing_y: float, basis: dict) -> tuple[float, float]:
    insert_x = _to_float(basis.get("insert_x")) or 0.0
    insert_y = _to_float(basis.get("insert_y")) or 0.0
    xscale = _to_float(basis.get("xscale")) or 1.0
    yscale = _to_float(basis.get("yscale")) or 1.0
    rotation_degrees = _to_float(basis.get("rotation")) or 0.0

    translated_x = drawing_x - insert_x
    translated_y = drawing_y - insert_y
    theta = math.radians(-rotation_degrees)
    cos_theta = math.cos(theta)
    sin_theta = math.sin(theta)
    rotated_x = translated_x * cos_theta - translated_y * sin_theta
    rotated_y = translated_x * sin_theta + translated_y * cos_theta
    return rotated_x / xscale, rotated_y / yscale


def _is_plan_like_xref(row: dict) -> bool:
    text = f"{row.get('xref_name') or ''} {row.get('xref_path') or ''}".casefold()
    if str(row.get("xref_name") or "").startswith(("*D", "*U")):
        return False
    return any(token in text for token in ["plan", "site", "\ubc30\uce58", "\uc7a5\ube44"])


def _has_insert_transform(row: dict) -> bool:
    return _to_float(row.get("insert_x")) is not None and _to_float(row.get("insert_y")) is not None


def _basis_confidence(row: dict) -> str:
    if _is_truthy(row.get("is_identity_insert")):
        return "0.95"
    rotation = abs(_to_float(row.get("rotation")) or 0.0)
    xscale = _to_float(row.get("xscale")) or 1.0
    yscale = _to_float(row.get("yscale")) or 1.0
    if math.isclose(rotation, 0.0, abs_tol=1e-9) and math.isclose(xscale, yscale, abs_tol=1e-9):
        return "0.85"
    return "0.7"


def _basis_reason(row: dict) -> str:
    if _is_truthy(row.get("is_identity_insert")):
        return "identity plan xref"
    return "inverse xref insert transform"


def _normalize_path_key(value: str) -> str:
    return value.replace("/", "\\").casefold().strip()


def _to_float(value: object) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_float(value: float) -> str:
    return f"{value:.12g}"


def _is_truthy(value: object) -> bool:
    return str(value).strip().casefold() == "true"


def _read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
