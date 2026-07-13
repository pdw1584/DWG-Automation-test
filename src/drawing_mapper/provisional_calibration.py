from __future__ import annotations

import csv
import json
import math
from html import escape
from pathlib import Path


EARTH_RADIUS_M_PER_DEGREE_LAT = 111_320.0


def apply_provisional_anchor_calibration(
    locations_path: Path,
    output_path: Path,
    report_path: Path,
    anchor_x: float,
    anchor_y: float,
    anchor_latitude: float,
    anchor_longitude: float,
    unit: str = "mm",
    rotation_degrees: float = 0.0,
    kml_output_path: Path | None = None,
) -> dict:
    rows = _read_csv(locations_path)
    meters_per_unit = _meters_per_unit(unit)
    lon_meter_degree = EARTH_RADIUS_M_PER_DEGREE_LAT * math.cos(math.radians(anchor_latitude))
    theta = math.radians(rotation_degrees)
    cos_theta = math.cos(theta)
    sin_theta = math.sin(theta)

    calibrated_count = 0
    skipped_count = 0
    source_counts: dict[str, int] = {}
    basis_counts: dict[str, int] = {}

    for row in rows:
        coordinate_pair = _coordinate_pair(row)
        if coordinate_pair is None:
            row["provisional_status"] = "skipped_missing_coordinate"
            skipped_count += 1
            continue

        x, y, source = coordinate_pair
        dx = (x - anchor_x) * meters_per_unit
        dy = (y - anchor_y) * meters_per_unit
        east_m = dx * cos_theta - dy * sin_theta
        north_m = dx * sin_theta + dy * cos_theta

        latitude = anchor_latitude + north_m / EARTH_RADIUS_M_PER_DEGREE_LAT
        longitude = anchor_longitude + east_m / lon_meter_degree

        row["latitude"] = f"{latitude:.8f}"
        row["longitude"] = f"{longitude:.8f}"
        row["provisional_status"] = "provisional_anchor_calibrated"
        row["provisional_coordinate_source"] = source
        row["provisional_anchor_x"] = f"{anchor_x:.12g}"
        row["provisional_anchor_y"] = f"{anchor_y:.12g}"
        row["provisional_anchor_latitude"] = f"{anchor_latitude:.8f}"
        row["provisional_anchor_longitude"] = f"{anchor_longitude:.8f}"
        row["provisional_unit"] = unit
        row["provisional_rotation_degrees"] = f"{rotation_degrees:.12g}"
        row["provisional_note"] = (
            "Single-anchor estimate only; scale, rotation, and survey control are not verified."
        )
        row["source_status"] = _append_status(
            str(row.get("source_status") or ""),
            "provisional_anchor_calibrated",
        )

        source_counts[source] = source_counts.get(source, 0) + 1
        basis = str(row.get("coordinate_basis") or "")
        if basis:
            basis_counts[basis] = basis_counts.get(basis, 0) + 1
        calibrated_count += 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_csv(output_path, _fieldnames(rows), rows)

    if kml_output_path:
        kml_output_path.parent.mkdir(parents=True, exist_ok=True)
        kml_output_path.write_text(_to_kml(rows), encoding="utf-8")

    report = {
        "method": "single_anchor_equirectangular_estimate",
        "location_count": len(rows),
        "calibrated_count": calibrated_count,
        "skipped_count": skipped_count,
        "coordinate_source_counts": dict(sorted(source_counts.items())),
        "basis_counts": dict(sorted(basis_counts.items())),
        "anchor": {
            "x": anchor_x,
            "y": anchor_y,
            "latitude": anchor_latitude,
            "longitude": anchor_longitude,
            "unit": unit,
            "rotation_degrees": rotation_degrees,
        },
        "assumptions": [
            "The anchor drawing coordinate matches the supplied latitude and longitude.",
            "Drawing units are interpreted using the selected unit.",
            "Rotation is manually supplied and defaults to 0 degrees.",
            "This is not a survey-grade affine calibration.",
        ],
        "output_csv": str(output_path),
        "output_kml": str(kml_output_path) if kml_output_path else "",
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _coordinate_pair(row: dict) -> tuple[float, float, str] | None:
    if str(row.get("basis_status") or "") == "mapped":
        basis_x = _to_float(row.get("basis_x"))
        basis_y = _to_float(row.get("basis_y"))
        if basis_x is not None and basis_y is not None:
            return basis_x, basis_y, "basis"

    drawing_x = _to_float(row.get("drawing_x"))
    drawing_y = _to_float(row.get("drawing_y"))
    if drawing_x is not None and drawing_y is not None:
        return drawing_x, drawing_y, "drawing"
    return None


def _meters_per_unit(unit: str) -> float:
    normalized = unit.strip().casefold()
    if normalized in {"mm", "millimeter", "millimeters"}:
        return 0.001
    if normalized in {"cm", "centimeter", "centimeters"}:
        return 0.01
    if normalized in {"m", "meter", "meters"}:
        return 1.0
    raise ValueError(f"Unsupported unit: {unit}. Use mm, cm, or m.")


def _to_float(value: object) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _append_status(current: str, status: str) -> str:
    parts = [part for part in current.split("|") if part]
    if status not in parts:
        parts.append(status)
    return "|".join(parts)


def _to_kml(rows: list[dict]) -> str:
    placemarks = []
    for row in rows:
        latitude = str(row.get("latitude") or "").strip()
        longitude = str(row.get("longitude") or "").strip()
        if not latitude or not longitude:
            continue
        name = str(row.get("equipment_name") or row.get("raw_label") or "facility")
        description = " | ".join(
            part
            for part in [
                f"floor={row.get('floor') or ''}",
                f"basis={row.get('coordinate_basis') or ''}",
                f"source={row.get('provisional_coordinate_source') or ''}",
                f"confidence={row.get('confidence') or ''}",
            ]
            if part
        )
        placemarks.append(
            "  <Placemark>\n"
            f"    <name>{escape(name)}</name>\n"
            f"    <description>{escape(description)}</description>\n"
            "    <Point>\n"
            f"      <coordinates>{escape(longitude)},{escape(latitude)},0</coordinates>\n"
            "    </Point>\n"
            "  </Placemark>"
        )

    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<kml xmlns=\"http://www.opengis.net/kml/2.2\">\n"
        "<Document>\n"
        "  <name>Facility Locations Provisional</name>\n"
        + "\n".join(placemarks)
        + "\n</Document>\n"
        "</kml>\n"
    )


def _read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _fieldnames(rows: list[dict]) -> list[str]:
    fieldnames: list[str] = []
    for row in rows:
        for field in row.keys():
            if field not in fieldnames:
                fieldnames.append(field)
    return fieldnames
