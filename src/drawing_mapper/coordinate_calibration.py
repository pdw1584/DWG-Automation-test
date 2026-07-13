from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AffineTransform:
    floor: str
    latitude_coefficients: tuple[float, float, float]
    longitude_coefficients: tuple[float, float, float]
    point_count: int

    def apply(self, drawing_x: float, drawing_y: float) -> tuple[float, float]:
        lat_a, lat_b, lat_c = self.latitude_coefficients
        lon_a, lon_b, lon_c = self.longitude_coefficients
        latitude = lat_a * drawing_x + lat_b * drawing_y + lat_c
        longitude = lon_a * drawing_x + lon_b * drawing_y + lon_c
        return latitude, longitude


def apply_coordinate_calibration(
    locations_path: Path,
    calibration_path: Path,
    output_path: Path,
    report_path: Path,
) -> dict:
    locations = _read_csv(locations_path)
    calibration_rows = _read_csv(calibration_path)
    transforms = build_affine_transforms(calibration_rows)

    calibrated_count = 0
    skipped_count = 0
    coordinate_source_counts: dict[str, int] = {}
    for location in locations:
        floor = str(location.get("floor") or "")
        transform = transforms.get(floor)
        if not transform:
            skipped_count += 1
            continue

        coordinate_pair = _calibration_coordinate_pair(location)
        if coordinate_pair is None:
            skipped_count += 1
            continue
        drawing_x, drawing_y, coordinate_source = coordinate_pair

        latitude, longitude = transform.apply(drawing_x, drawing_y)
        location["latitude"] = f"{latitude:.8f}"
        location["longitude"] = f"{longitude:.8f}"
        location["calibration_coordinate_source"] = coordinate_source
        location["source_status"] = _append_status(
            str(location.get("source_status") or ""),
            "coordinate_calibrated",
        )
        coordinate_source_counts[coordinate_source] = (
            coordinate_source_counts.get(coordinate_source, 0) + 1
        )
        calibrated_count += 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_csv(output_path, _fieldnames(locations), locations)

    report = {
        "location_count": len(locations),
        "calibrated_count": calibrated_count,
        "skipped_count": skipped_count,
        "transform_count": len(transforms),
        "coordinate_source_counts": dict(sorted(coordinate_source_counts.items())),
        "transforms": {
            floor: {
                "method": "affine",
                "point_count": transform.point_count,
                "latitude_coefficients": list(transform.latitude_coefficients),
                "longitude_coefficients": list(transform.longitude_coefficients),
            }
            for floor, transform in sorted(transforms.items())
        },
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _calibration_coordinate_pair(location: dict) -> tuple[float, float, str] | None:
    if str(location.get("basis_status") or "") == "mapped":
        basis_x = _to_float(location.get("basis_x"))
        basis_y = _to_float(location.get("basis_y"))
        if basis_x is not None and basis_y is not None:
            return basis_x, basis_y, "basis"

    drawing_x = _to_float(location.get("drawing_x"))
    drawing_y = _to_float(location.get("drawing_y"))
    if drawing_x is not None and drawing_y is not None:
        return drawing_x, drawing_y, "drawing"
    return None


def build_affine_transforms(calibration_rows: list[dict]) -> dict[str, AffineTransform]:
    rows_by_floor: dict[str, list[dict]] = {}
    for row in calibration_rows:
        floor = str(row.get("floor") or "").strip()
        if not floor:
            continue
        if not _has_complete_control_point(row):
            continue
        rows_by_floor.setdefault(floor, []).append(row)

    transforms = {}
    for floor, rows in rows_by_floor.items():
        if len(rows) < 3:
            continue
        x_values = []
        y_lat_values = []
        y_lon_values = []
        for row in rows:
            drawing_x = float(row["drawing_x"])
            drawing_y = float(row["drawing_y"])
            x_values.append((drawing_x, drawing_y, 1.0))
            y_lat_values.append(float(row["latitude"]))
            y_lon_values.append(float(row["longitude"]))

        transforms[floor] = AffineTransform(
            floor=floor,
            latitude_coefficients=tuple(_least_squares_3(x_values, y_lat_values)),
            longitude_coefficients=tuple(_least_squares_3(x_values, y_lon_values)),
            point_count=len(rows),
        )
    return transforms


def _has_complete_control_point(row: dict) -> bool:
    for field in ["drawing_x", "drawing_y", "latitude", "longitude"]:
        value = str(row.get(field) or "").strip()
        if not value:
            return False
        try:
            float(value)
        except ValueError:
            return False
    return True


def _to_float(value: object) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _least_squares_3(rows: list[tuple[float, float, float]], targets: list[float]) -> list[float]:
    normal_matrix = [[0.0, 0.0, 0.0] for _ in range(3)]
    normal_vector = [0.0, 0.0, 0.0]

    for row, target in zip(rows, targets, strict=True):
        for i in range(3):
            normal_vector[i] += row[i] * target
            for j in range(3):
                normal_matrix[i][j] += row[i] * row[j]

    return _solve_3x3(normal_matrix, normal_vector)


def _solve_3x3(matrix: list[list[float]], vector: list[float]) -> list[float]:
    augmented = [matrix[i][:] + [vector[i]] for i in range(3)]
    for column in range(3):
        pivot_row = max(range(column, 3), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot_row][column]) < 1e-12:
            raise ValueError("Calibration control points are collinear or insufficient.")
        augmented[column], augmented[pivot_row] = augmented[pivot_row], augmented[column]

        pivot = augmented[column][column]
        for index in range(column, 4):
            augmented[column][index] /= pivot

        for row in range(3):
            if row == column:
                continue
            factor = augmented[row][column]
            for index in range(column, 4):
                augmented[row][index] -= factor * augmented[column][index]

    return [augmented[row][3] for row in range(3)]


def _append_status(current: str, status: str) -> str:
    parts = [part for part in current.split("|") if part]
    if status not in parts:
        parts.append(status)
    return "|".join(parts)


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
