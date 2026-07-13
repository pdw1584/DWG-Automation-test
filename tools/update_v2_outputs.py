from __future__ import annotations

import csv
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V2_DIR = ROOT / "v2"
CURRENT_CSVS = [
    V2_DIR / "facility-locations-xr-plan-final-deduped.csv",
    V2_DIR / "facility-locations-xr-plan-import.csv",
]
HTML_PATH = V2_DIR / "facility-locations-xr-plan-review.html"
REFRESH_CSV = V2_DIR / "refresh-equipment" / "facility-location-high-confidence.csv"

IT_POWER_RE = re.compile(
    r"(MCPU|ATS|GIMAC\s*DC|DIESEL\s+GENERATOR|EMERGENCY\s+GENERATOR|GENERATOR|(?<![A-Z0-9])GEN(?![A-Z0-9])|UPS|PDU|RPP)",
    re.IGNORECASE,
)
COOLING_RE = re.compile(r"(CWU|BUFFER\s*TANK|버퍼탱크|RADIATOR|RAD\b|COIL\s+WALL\s+UNIT)", re.IGNORECASE)


def main() -> None:
    current_rows = _read_csv(CURRENT_CSVS[0])
    refresh_rows = _read_csv(REFRESH_CSV)

    updated_rows = []
    existing_keys: set[tuple[str, str, int, int]] = set()
    for row in current_rows:
        row = dict(row)
        _reclassify_row(row)
        updated_rows.append(row)
        existing_keys.add(_row_key(row))

    appended = 0
    for row in refresh_rows:
        new_row = _refresh_to_current_schema(row)
        key = _row_key(new_row)
        if key in existing_keys:
            continue
        updated_rows.append(new_row)
        existing_keys.add(key)
        appended += 1

    updated_rows = sorted(
        updated_rows,
        key=lambda row: (
            str(row.get("floor") or ""),
            str(row.get("equipment_category") or ""),
            str(row.get("label") or ""),
            float(row.get("drawing_x") or 0),
            float(row.get("drawing_y") or 0),
        ),
    )

    for path in CURRENT_CSVS:
        _write_csv(path, updated_rows)

    payload = _load_payload(HTML_PATH)
    payload["locations"] = [_row_to_payload(row) for row in updated_rows]
    payload["floorOrder"] = _floor_order(payload.get("floorOrder") or [], payload["locations"])
    payload["floorCounts"] = _count_by(payload["locations"], "floor")
    payload["categoryCounts"] = _count_by(payload["locations"], "equipment_category")
    payload["categories"] = sorted(payload["categoryCounts"], key=lambda cat: (-payload["categoryCounts"][cat], cat))
    _write_payload(HTML_PATH, payload)

    print(f"Updated {len(updated_rows)} CSV rows; appended {appended} new rows from refresh output.")


def _read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def _write_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = [
        "status",
        "coordinate_basis",
        "floor",
        "equipment_category",
        "label",
        "drawing_x",
        "drawing_y",
        "confidence",
        "location_count",
        "evidence_row_count",
        "evidence_drawing_count",
        "source_count",
        "source_drawing_count",
        "source_drawings",
        "source_paths",
        "entity_types",
        "layers",
        "block_names",
        "texts",
        "handles",
        "floor_bbox_ids",
        "nearby_name",
        "display_label",
        "nearby_name_distance",
        "nearby_name_layer",
        "nearby_name_handle",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _reclassify_row(row: dict) -> None:
    label = str(row.get("label") or "")
    if IT_POWER_RE.search(label):
        row["equipment_category"] = "it_power"
    elif COOLING_RE.search(label):
        row["equipment_category"] = "cooling"
    row["status"] = row.get("status") or "confirmed"
    row["coordinate_basis"] = row.get("coordinate_basis") or "XR-PLAN"
    row["display_label"] = row.get("display_label") or row.get("label") or ""
    row["source_drawings"] = row.get("source_drawings") or ""
    row["source_paths"] = row.get("source_paths") or ""
    row["entity_types"] = row.get("entity_types") or ""
    row["layers"] = row.get("layers") or ""
    row["block_names"] = row.get("block_names") or ""
    row["texts"] = row.get("texts") or ""
    row["handles"] = row.get("handles") or ""
    row["floor_bbox_ids"] = row.get("floor_bbox_ids") or ""
    row["nearby_name"] = row.get("nearby_name") or ""
    row["nearby_name_distance"] = row.get("nearby_name_distance") or ""
    row["nearby_name_layer"] = row.get("nearby_name_layer") or ""
    row["nearby_name_handle"] = row.get("nearby_name_handle") or ""


def _refresh_to_current_schema(row: dict) -> dict:
    label = str(row.get("label") or "").strip()
    source_paths = str(row.get("source_paths") or "")
    source_drawings = " | ".join(
        [part.strip() for part in source_paths.split("|") if part.strip()]
    )
    source_count = str(row.get("source_count") or "1")
    drawing_x = str(row.get("drawing_x") or "")
    drawing_y = str(row.get("drawing_y") or "")
    return {
        "status": "confirmed",
        "coordinate_basis": "XR-PLAN",
        "floor": str(row.get("floor") or ""),
        "equipment_category": str(row.get("equipment_category") or ""),
        "label": label,
        "drawing_x": drawing_x,
        "drawing_y": drawing_y,
        "confidence": str(row.get("confidence") or ""),
        "location_count": "1",
        "evidence_row_count": "1",
        "evidence_drawing_count": "1",
        "source_count": source_count,
        "source_drawing_count": "1",
        "source_drawings": source_drawings,
        "source_paths": source_paths,
        "entity_types": "",
        "layers": "",
        "block_names": "",
        "texts": "",
        "handles": "",
        "floor_bbox_ids": "",
        "nearby_name": "",
        "display_label": label,
        "nearby_name_distance": "",
        "nearby_name_layer": "",
        "nearby_name_handle": "",
    }


def _row_key(row: dict) -> tuple[str, str, int, int]:
    label = _normalize_label(str(row.get("label") or ""))
    floor = str(row.get("floor") or "")
    try:
        x = round(float(row.get("drawing_x") or row.get("x") or 0), 1)
        y = round(float(row.get("drawing_y") or row.get("y") or 0), 1)
    except ValueError:
        x = 0.0
        y = 0.0
    return (floor, label, int(x * 10), int(y * 10))


def _normalize_label(label: str) -> str:
    return re.sub(r"\s+", " ", label.replace("%%U", "").strip()).casefold()


def _load_payload(path: Path) -> dict:
    text = path.read_text(encoding="utf-8-sig")
    match = re.search(
        r'(<script id="payload" type="application/json">)(.*?)(</script>)',
        text,
        re.DOTALL,
    )
    if not match:
        raise RuntimeError("Could not find payload script tag in HTML.")
    return json.loads(match.group(2))


def _write_payload(path: Path, payload: dict) -> None:
    text = path.read_text(encoding="utf-8-sig")
    match = re.search(
        r'(<script id="payload" type="application/json">)(.*?)(</script>)',
        text,
        re.DOTALL,
    )
    if not match:
        raise RuntimeError("Could not find payload script tag in HTML.")
    payload_text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    updated = text[: match.start(2)] + payload_text + text[match.end(2) :]
    path.write_text(updated, encoding="utf-8")


def _row_to_payload(row: dict) -> dict:
    label = str(row.get("label") or "")
    raw_label = str(row.get("display_label") or label).split(" / ")[0].strip() or label
    try:
        x = float(row.get("drawing_x") or 0)
        y = float(row.get("drawing_y") or 0)
    except ValueError:
        x = 0.0
        y = 0.0

    return {
        "status": str(row.get("status") or "confirmed"),
        "coordinate_basis": str(row.get("coordinate_basis") or "XR-PLAN"),
        "floor": str(row.get("floor") or ""),
        "equipment_category": str(row.get("equipment_category") or ""),
        "label": label,
        "raw_label": raw_label,
        "nearby_name": str(row.get("nearby_name") or ""),
        "nearby_name_distance": str(row.get("nearby_name_distance") or ""),
        "nearby_name_layer": str(row.get("nearby_name_layer") or ""),
        "confidence": _as_float(row.get("confidence")),
        "location_count": _as_int(row.get("location_count"), 1),
        "evidence_row_count": _as_int(row.get("evidence_row_count"), 1),
        "evidence_drawing_count": _as_int(row.get("evidence_drawing_count"), 1),
        "source_drawings": str(row.get("source_drawings") or ""),
        "x": x,
        "y": y,
        "source_count": _as_int(row.get("source_count"), 1),
        "source_drawing_count": _as_int(row.get("source_drawing_count"), 1),
    }


def _floor_order(existing: list[str], locations: list[dict]) -> list[str]:
    order = [str(floor) for floor in existing if floor]
    for floor in [str(item.get("floor") or "") for item in locations]:
        if floor and floor not in order:
            order.append(floor)
    return order


def _count_by(locations: list[dict], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in locations:
        key = str(item.get(field) or "")
        if not key:
            continue
        counts[key] = counts.get(key, 0) + 1
    return counts


def _as_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _as_int(value: object, default: int) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


if __name__ == "__main__":
    main()
